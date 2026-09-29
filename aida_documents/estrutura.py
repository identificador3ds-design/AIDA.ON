"""Forense estrutural do PDF: o que o arquivo conta sobre como foi feito e mexido.

Nada aqui olha o conteudo visual. Os sinais sao:
- revisoes incrementais: cada edicao salva "por cima" acrescenta um novo xref e um
  %%EOF ao fim do arquivo, e o original continua la dentro;
- assinatura digital: se ha bytes depois do trecho coberto pelo /ByteRange, o arquivo
  foi alterado depois de assinado (pode ser legitimo, ex. segunda assinatura, mas pede
  conferencia). A validade criptografica NAO e verificada aqui;
- metadados: produtor/criador (editor online, editor de imagem, impressora virtual) e
  datas de criacao x modificacao;
- camada de texto: pagina so com imagem precisa de OCR, o que indica print, foto ou
  montagem, e nao um PDF saido direto do sistema emissor;
- fontes: a mesma fonte embutida em dois subconjuntos diferentes (ABCDEF+Arial e
  GHIJKL+Arial) costuma aparecer quando um editor acrescenta texto a um PDF pronto.
"""

from __future__ import annotations

import io
import re
from datetime import datetime

from pypdf import PdfReader

# Produtores que nao sao sistemas emissores. A lista e deliberadamente curta; cada
# entrada e um indicio fraco, nunca prova.
PRODUTORES_EDICAO = {
    "ilovepdf": "editor online (iLovePDF)",
    "smallpdf": "editor online (Smallpdf)",
    "sejda": "editor online (Sejda)",
    "pdfescape": "editor online (PDFescape)",
    "pdf-xchange": "editor de PDF (PDF-XChange)",
    "foxit phantompdf": "editor de PDF (Foxit PhantomPDF)",
    "foxit pdf editor": "editor de PDF (Foxit PDF Editor)",
    "nitro": "editor de PDF (Nitro)",
    "photoshop": "editor de imagem (Photoshop)",
    "gimp": "editor de imagem (GIMP)",
    "canva": "ferramenta de design (Canva)",
    "microsoft: print to pdf": "impressora virtual (Microsoft Print to PDF)",
    "microsoft word": "processador de texto (Word)",
    "libreoffice": "processador de texto (LibreOffice)",
    "google docs": "processador de texto (Google Docs)",
    "skia/pdf": "impressão de navegador (Chrome/Skia)",
    "camscanner": "app de digitalização (CamScanner)",
    # Bibliotecas que um script (ou uma IA escrevendo codigo) usa para montar um PDF do
    # zero. Sistemas emissores costumam usar iText/Jasper, que ficam de fora.
    "reportlab": "biblioteca de programação (ReportLab)",
    "fpdf": "biblioteca de programação (FPDF)",
    "pdfkit": "biblioteca de programação (PDFKit)",
    "jspdf": "biblioteca de programação (jsPDF)",
    "pdf-lib": "biblioteca de programação (pdf-lib)",
    "weasyprint": "biblioteca de programação (WeasyPrint)",
    "wkhtmltopdf": "biblioteca de programação (wkhtmltopdf)",
}
_BYTE_RANGE = re.compile(rb"/ByteRange\s*\[\s*(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*\]")
_OBJETO = re.compile(rb"\d+\s+\d+\s+obj\b")
_SUBSET = re.compile(r"^/?([A-Z]{6})\+(.+)$")
MARCADORES_ATIVOS = {b"/JavaScript": "JavaScript", b"/Launch": "ação /Launch", b"/EmbeddedFile": "arquivo embutido"}


def _contar_revisoes(dados, linearizado):
    """Secoes terminadas em %%EOF que trazem objetos novos. O Word grava um segundo
    trailer vazio ("xref 0 0" + /XRefStm, arquivo hibrido) que nao e edicao; e o PDF
    linearizado tem uma secao extra da primeira pagina."""
    secoes = [s for s in dados.split(b"%%EOF") if s.strip()]
    com_objetos = sum(1 for i, s in enumerate(secoes) if i == 0 or _OBJETO.search(s))
    return max(1, com_objetos - (1 if linearizado and com_objetos > 1 else 0))


def _data_pdf(valor):
    if valor is None:
        return None
    if isinstance(valor, datetime):
        return valor
    m = re.match(r"D?:?(\d{4})(\d{2})?(\d{2})?(\d{2})?(\d{2})?(\d{2})?", str(valor))
    if not m:
        return None
    partes = [int(p) if p else d for p, d in zip(m.groups(), (0, 1, 1, 0, 0, 0))]
    try:
        return datetime(*partes)
    except ValueError:
        return None


def _meta(reader, chave, atributo):
    try:
        return getattr(reader.metadata, atributo) if reader.metadata else None
    except Exception:  # metadados malformados sao comuns
        return reader.metadata.get(chave) if reader.metadata else None


def _fontes_da_pagina(pagina):
    try:
        fontes = pagina["/Resources"]["/Font"]
    except (KeyError, TypeError):
        return []
    nomes = []
    for ref in fontes.values():
        try:
            nomes.append(str(ref.get_object().get("/BaseFont", "")))
        except Exception:
            continue
    return [n for n in nomes if n]


def _tem_imagem(pagina):
    try:
        xobjs = pagina["/Resources"]["/XObject"]
        return any(x.get_object().get("/Subtype") == "/Image" for x in xobjs.values())
    except (KeyError, TypeError, AttributeError):
        return False


def inspecionar_pdf(dados: bytes, max_paginas=30):
    reader = PdfReader(io.BytesIO(dados), strict=False)
    if reader.is_encrypted:
        reader.decrypt("")

    linearizado = b"/Linearized" in dados[:2048]
    revisoes = _contar_revisoes(dados, linearizado)

    fim_util = len(dados.rstrip(b"\r\n\x00 "))
    assinaturas = [tuple(map(int, m)) for m in _BYTE_RANGE.findall(dados)]
    cobertura = max((c + d for _, _, c, d in assinaturas), default=None)
    bytes_apos_assinatura = max(0, fim_util - cobertura) if cobertura else 0

    produtor = _meta(reader, "/Producer", "producer") or ""
    criador = _meta(reader, "/Creator", "creator") or ""
    criado = _data_pdf(_meta(reader, "/CreationDate", "creation_date"))
    modificado = _data_pdf(_meta(reader, "/ModDate", "modification_date"))

    paginas = reader.pages
    textos, sem_texto, fontes = [], 0, []
    for pagina in list(paginas)[:max_paginas]:
        try:
            texto = pagina.extract_text() or ""
        except Exception:
            texto = ""
        textos.append(texto)
        if len(texto.strip()) < 20 and _tem_imagem(pagina):
            sem_texto += 1
        fontes.extend(_fontes_da_pagina(pagina))

    subconjuntos = {}
    for f in set(fontes):
        m = _SUBSET.match(f)
        if m:
            subconjuntos.setdefault(m.group(2), set()).add(m.group(1))
    fontes_repetidas = sorted(nome for nome, prefixos in subconjuntos.items() if len(prefixos) > 1)

    identificacao = f"{produtor} {criador}".lower()
    ferramentas = sorted({desc for chave, desc in PRODUTORES_EDICAO.items() if chave in identificacao})

    return {
        "paginas": len(paginas),
        "paginas_analisadas": len(textos),
        "paginas_sem_texto": sem_texto,
        "texto": "\n".join(textos),
        "revisoes": revisoes,
        "linearizado": linearizado,
        "assinaturas": len(assinaturas),
        "bytes_apos_assinatura": bytes_apos_assinatura,
        "produtor": produtor,
        "criador": criador,
        "ferramentas_edicao": ferramentas,
        "criado_em": criado.isoformat() if criado else None,
        "modificado_em": modificado.isoformat() if modificado else None,
        "dias_entre_criacao_e_modificacao": (
            round(abs((modificado.replace(tzinfo=None) - criado.replace(tzinfo=None)).total_seconds()) / 86400, 2)
            if criado and modificado else None
        ),
        "fontes_distintas": len(set(fontes)),
        "fontes_subconjunto_duplicado": fontes_repetidas,
        "elementos_ativos": sorted(nome for marca, nome in MARCADORES_ATIVOS.items() if marca in dados),
        "criptografado": reader.is_encrypted,
    }
