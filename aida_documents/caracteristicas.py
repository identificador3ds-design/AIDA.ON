"""Vetor numerico de um PDF para o classificador do AIDA Documents.

Ideia de Adhatarao e Lauradoux (IFIP SEC 2022): o programa que gerou o PDF deixa um
"estilo de codigo" no arquivo (versao, object streams, como embute fontes, tamanho da
pagina, filtros dos streams), e esse estilo e mais dificil de apagar que o Producer.
Por isso quase nada aqui le metadado; ha so dois sinais de texto.

Ficam de fora de proposito, para o modelo nao aprender atalho:
- o ano de criacao (os reais de 08/10 sao de 2017-2018 e os de IA de 2026);
- o nome do Producer (ja e indicio em `estrutura.py`, com peso explicavel).

Uso:
    python -m aida_documents.caracteristicas arquivo.pdf
"""

from __future__ import annotations

import io
import json
import math
import re
import sys
from pathlib import Path

from pypdf import PdfReader

from .estrutura import _SUBSET

NOMES_CARACTERISTICAS = [
    "versao_pdf",
    "object_streams",
    "xref_stream",
    "tem_xmp",
    "tem_id_trailer",
    "pdf_marcado",
    "tem_idioma",
    "fracao_fontes_padrao_sem_embutir",
    "fracao_fontes_subconjunto",
    "fracao_fontes_type0",
    "pagina_a4_reportlab",
    "pagina_com_decimais",
    "usa_ascii85",
    "fracao_streams_sem_compressao",
    "log_objetos_por_pagina",
    "log_bytes_por_pagina",
    "imagens_por_pagina",
    "conteudo_inicia_estilo_reportlab",
    "criacao_igual_modificacao",
    "log_caracteres_por_pagina",
    "travessoes_por_mil",
    "linhas_de_preencher_por_mil",
]

# As 14 fontes padrao do PDF: quem as usa sem embutir e quase sempre biblioteca de
# programacao (ReportLab, FPDF). Word, LibreOffice e navegadores embutem subconjuntos.
_PADRAO_14 = {
    "Helvetica", "Helvetica-Bold", "Helvetica-Oblique", "Helvetica-BoldOblique",
    "Times-Roman", "Times-Bold", "Times-Italic", "Times-BoldItalic",
    "Courier", "Courier-Bold", "Courier-Oblique", "Courier-BoldOblique", "Symbol", "ZapfDingbats",
}
_VERSAO = re.compile(rb"%PDF-(\d\.\d)")
_OBJETO = re.compile(rb"\d+\s+\d+\s+obj\b")
_STREAM = re.compile(rb"<<((?:(?!>>\s*stream).)*?)>>\s*stream", re.S)
# ReportLab abre todo conteudo de pagina com "1 0 0 1 0 0 cm  BT /F1 12 Tf 14.4 TL ET"
# (fonte padrao do canvas), mesmo quando nada e escrito nessa fonte. pypdf preserva isso
# ao regravar, as vezes com um "q" na frente.
_INICIO_REPORTLAB = re.compile(rb"^\s*(q\s+)?1 0 0 1 0 0 cm\s+BT\s+/F1\s+12\s+Tf\s+14\.4\s+TL\s+ET")


def _fontes(reader):
    vistas = {}
    for pagina in reader.pages:
        try:
            fontes = pagina["/Resources"]["/Font"]
        except (KeyError, TypeError):
            continue
        for ref in fontes.values():
            try:
                obj = ref.get_object()
                nome = str(obj.get("/BaseFont", "")).lstrip("/")
                tipo = str(obj.get("/Subtype", ""))
                desc = obj.get("/FontDescriptor")
                if desc is None and tipo == "/Type0":
                    desc = obj["/DescendantFonts"][0].get_object().get("/FontDescriptor")
                desc = desc.get_object() if desc is not None else {}
                embutida = any(k in desc for k in ("/FontFile", "/FontFile2", "/FontFile3"))
                vistas[(nome, tipo)] = embutida
            except Exception:
                continue
    return vistas


def _conteudo_primeira_pagina(reader):
    try:
        conteudo = reader.pages[0].get_contents()
        return conteudo.get_data() if conteudo is not None else b""
    except Exception:
        return b""


def _pagina(reader):
    try:
        caixa = reader.pages[0].mediabox
        return float(caixa.width), float(caixa.height)
    except Exception:
        return 0.0, 0.0


def caracteristicas_bytes(dados: bytes, texto: str | None = None):
    """Devolve (vetor na ordem de NOMES_CARACTERISTICAS, dict com os mesmos valores)."""
    reader = PdfReader(io.BytesIO(dados), strict=False)
    if reader.is_encrypted:
        reader.decrypt("")
    n_pag = max(1, len(reader.pages))

    versao = _VERSAO.search(dados[:1024])
    fontes = _fontes(reader)
    n_fontes = max(1, len(fontes))
    padrao = sum(1 for (nome, _), emb in fontes.items() if nome in _PADRAO_14 and not emb)
    subconj = sum(1 for nome, _ in fontes if _SUBSET.match(nome))
    type0 = sum(1 for _, tipo in fontes if tipo == "/Type0")

    largura, altura = _pagina(reader)
    dicts_stream = _STREAM.findall(dados)
    sem_filtro = sum(1 for d in dicts_stream if b"/Filter" not in d)

    try:
        meta = reader.metadata or {}
        criado, modificado = meta.get("/CreationDate"), meta.get("/ModDate")
    except Exception:
        criado = modificado = None

    if texto is None:
        partes = []
        for pagina in list(reader.pages)[:30]:
            try:
                partes.append(pagina.extract_text() or "")
            except Exception:
                partes.append("")
        texto = "\n".join(partes)
    n_car = max(1, len(texto))

    valores = {
        "versao_pdf": float(versao.group(1)) if versao else 0.0,
        "object_streams": float(b"/ObjStm" in dados),
        "xref_stream": float(b"/Type /XRef" in dados or b"/Type/XRef" in dados),
        "tem_xmp": float(b"/Metadata" in dados),
        "tem_id_trailer": float(b"/ID" in dados),
        "pdf_marcado": float(b"/StructTreeRoot" in dados),
        "tem_idioma": float(b"/Lang" in dados),
        "fracao_fontes_padrao_sem_embutir": padrao / n_fontes if fontes else 0.0,
        "fracao_fontes_subconjunto": subconj / n_fontes if fontes else 0.0,
        "fracao_fontes_type0": type0 / n_fontes if fontes else 0.0,
        "pagina_a4_reportlab": float(abs(largura - 595.2756) < 1e-3 and abs(altura - 841.8898) < 1e-3),
        "pagina_com_decimais": float(largura % 1 > 1e-6 or altura % 1 > 1e-6),
        "usa_ascii85": float(b"/ASCII85Decode" in dados),
        "fracao_streams_sem_compressao": sem_filtro / len(dicts_stream) if dicts_stream else 0.0,
        "log_objetos_por_pagina": math.log1p(len(_OBJETO.findall(dados)) / n_pag),
        "log_bytes_por_pagina": math.log1p(len(dados) / n_pag),
        "imagens_por_pagina": (dados.count(b"/Subtype /Image") + dados.count(b"/Subtype/Image")) / n_pag,
        "conteudo_inicia_estilo_reportlab": float(bool(_INICIO_REPORTLAB.match(_conteudo_primeira_pagina(reader)))),
        "criacao_igual_modificacao": float(criado is not None and criado == modificado),
        "log_caracteres_por_pagina": math.log1p(len(texto) / n_pag),
        "travessoes_por_mil": 1000 * (texto.count("–") + texto.count("—")) / n_car,
        "linhas_de_preencher_por_mil": 1000 * len(re.findall(r"_{5,}", texto)) / n_car,
    }
    return [valores[n] for n in NOMES_CARACTERISTICAS], valores


def caracteristicas_documento(caminho):
    return caracteristicas_bytes(Path(caminho).read_bytes())


if __name__ == "__main__":
    print(json.dumps(caracteristicas_documento(sys.argv[1])[1], ensure_ascii=False, indent=2))
