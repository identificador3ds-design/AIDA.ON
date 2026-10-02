"""Extracao do texto bruto de PDF, DOCX e TXT, pagina a pagina.

Devolve o texto como chegou, sem limpar: quem tira cabecalho, rodape e numero de
pagina e `limpeza.py`, que precisa das paginas separadas para achar o que se repete.

- PDF: pypdf (ja usado pelo resto do AIDA Documents).
- DOCX: zipfile + XML da biblioteca padrao. O corpo fica em word/document.xml;
  cabecalhos e rodapes sao partes separadas (header*.xml, footer*.xml) e por isso
  nem chegam aqui. Tabelas sao puladas: nao sao prosa.
- TXT/MD: UTF-8, com latin-1 como reserva.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
from xml.etree import ElementTree

EXTENSOES_TEXTO = {".pdf", ".docx", ".txt", ".md"}
MAX_PAGINAS = 200
# document.xml descompactado: protege de arquivo-bomba.
MAX_XML_BYTES = 60 * 1024 * 1024
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class FormatoNaoSuportado(ValueError):
    pass


def _pdf(dados):
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(dados), strict=False)
    if reader.is_encrypted:
        reader.decrypt("")
    paginas, sem_texto = [], 0
    total = len(reader.pages)
    for pagina in list(reader.pages)[:MAX_PAGINAS]:
        try:
            texto = pagina.extract_text() or ""
        except Exception:  # pagina malformada nao derruba o documento
            texto = ""
        if len(texto.strip()) < 20:
            sem_texto += 1
        paginas.append(texto)
    avisos = []
    if sem_texto:
        avisos.append(f"{sem_texto} página(s) sem texto selecionável (imagem): ficaram fora da análise, não há OCR")
    if total > MAX_PAGINAS:
        avisos.append(f"documento com {total} páginas: só as primeiras {MAX_PAGINAS} foram lidas")
    return paginas, avisos


def _texto_paragrafo(p):
    partes = []
    for no in p.iter():
        if no.tag == _W + "t":
            partes.append(no.text or "")
        elif no.tag == _W + "tab":
            partes.append(" ")
        elif no.tag in (_W + "br", _W + "cr"):
            partes.append("\n")
        elif no.tag == _W + "delText":  # texto apagado em revisao: nao faz parte do documento
            continue
    return "".join(partes)


def _docx(dados):
    try:
        pacote = zipfile.ZipFile(io.BytesIO(dados))
        info = pacote.getinfo("word/document.xml")
    except (zipfile.BadZipFile, KeyError) as exc:
        raise FormatoNaoSuportado("o arquivo não é um DOCX válido") from exc
    if info.file_size > MAX_XML_BYTES:
        raise FormatoNaoSuportado("DOCX grande demais para analisar")
    raiz = ElementTree.fromstring(pacote.read(info))
    corpo = raiz.find(_W + "body")
    paragrafos, tabelas = [], 0
    for filho in list(corpo) if corpo is not None else []:
        if filho.tag == _W + "p":
            paragrafos.append(_texto_paragrafo(filho))
        elif filho.tag == _W + "tbl":
            tabelas += 1
    avisos = [f"{tabelas} tabela(s) ignorada(s): a análise olha só o texto corrido"] if tabelas else []
    # Linha em branco entre paragrafos: a limpeza trata cada um como paragrafo pronto.
    return ["\n\n".join(paragrafos)], avisos


def _txt(dados):
    for codificacao in ("utf-8-sig", "utf-8"):
        try:
            return [dados.decode(codificacao)], []
        except UnicodeDecodeError:
            continue
    return [dados.decode("latin-1")], []


def extrair(dados: bytes, nome="documento.pdf"):
    """Devolve {"formato", "paginas": [str], "avisos": [str]}."""
    ext = Path(nome).suffix.lower()
    if ext == ".doc":
        raise FormatoNaoSuportado("arquivo .doc (Word antigo) não é lido: salve como .docx ou PDF")
    if ext not in EXTENSOES_TEXTO:
        raise FormatoNaoSuportado("formato não suportado: envie PDF, DOCX ou TXT")
    if ext == ".pdf":
        if not dados.lstrip()[:5].startswith(b"%PDF"):
            raise FormatoNaoSuportado("o arquivo não é um PDF")
        paginas, avisos = _pdf(dados)
    elif ext == ".docx":
        paginas, avisos = _docx(dados)
    else:
        paginas, avisos = _txt(dados)
    return {"formato": ext.lstrip("."), "paginas": paginas, "avisos": avisos}
