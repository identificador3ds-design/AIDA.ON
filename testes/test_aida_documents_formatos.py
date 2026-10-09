"""AIDA Documents em .docx, .doc e .txt (alem do PDF)."""

from __future__ import annotations

import io
import sys
import zipfile

import pytest

from aida_documents import analisar_bytes

MANIFESTO_IA = (
    b"\x00\x00\x00\x1ejumbjumdc2pa\x00c2pa.actions.v2cbor\xa1gactions\x81\xa3factionlc2pa.created"
    b"qdigitalSourceTypexFhttp://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia"
    b"msoftwareAgent\xa1dnameggpt-5-6c2pa.claim.v2tclaim_generator_info\xa1dnamegChatGPT"
)
TEXTO = "Machado de Assis foi o principal autor do Realismo no Brasil. " * 40  # ~2.500 caracteres


def docx(texto=TEXTO, minutos=45, palavras=None, aplicativo="Microsoft Office Word", rsids=("00A1B2C3",), extras=None):
    """Um .docx minimo, com core.xml e app.xml como o Word grava."""
    w = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    paragrafos = "".join(
        f'<w:p w:rsidR="{rsids[i % len(rsids)]}"><w:r><w:t>{linha}</w:t></w:r></w:p>'
        for i, linha in enumerate(texto.split(". ")) if linha
    )
    palavras = len(texto.split()) if palavras is None else palavras
    partes = {
        "[Content_Types].xml": "<Types/>",
        "word/document.xml": f"<w:document {w}><w:body>{paragrafos}</w:body></w:document>",
        "docProps/core.xml": (
            '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/">'
            "<dc:creator>Fulano</dc:creator><cp:revision>3</cp:revision>"
            "<dcterms:created>2026-10-01T10:00:00Z</dcterms:created><dcterms:modified>2026-10-01T11:00:00Z</dcterms:modified>"
            "</cp:coreProperties>"
        ),
        "docProps/app.xml": (
            '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">'
            f"<TotalTime>{minutos}</TotalTime><Pages>2</Pages><Words>{palavras}</Words>"
            f"<Application>{aplicativo}</Application><AppVersion>16.0000</AppVersion></Properties>"
        ),
        **(extras or {}),
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for nome, conteudo in partes.items():
            z.writestr(nome, conteudo)
    return buf.getvalue()


def nomes(r):
    return {i["indicio"] for i in r["indicios"]}


# ---------------------------------------------------------------- .docx


def test_docx_do_word_digitado_aos_poucos():
    r = analisar_bytes(docx(minutos=45, rsids=("00A1B2C3", "00D4E5F6", "0011AA22")), "trabalho.docx")
    assert r["formato"] == "docx" and r["estrutura"]["sessoes_edicao"] == 3
    assert r["estrutura"]["criador"] is None  # o nome do autor nao vai para o relatorio
    assert nomes(r) == set()
    assert r["resultado"] == "INCONCLUSIVO"
    assert any(".docx pode ser escrito" in m for m in r["motivos"])


def test_docx_com_texto_colado_de_uma_vez():
    r = analisar_bytes(docx(minutos=1), "trabalho.docx")
    assert "texto_colado" in nomes(r)
    assert r["resultado"] == "INCONCLUSIVO"  # indicio fraco: nao decide sozinho


def test_docx_do_python_docx():
    """O ChatGPT gera .docx com python-docx: autor, descricao e data do modelo denunciam."""
    pytest.importorskip("docx")
    import docx as python_docx

    d = python_docx.Document()
    for _ in range(10):
        d.add_paragraph("Machado de Assis foi o maior escritor do Realismo brasileiro. " * 5)
    buf = io.BytesIO()
    d.save(buf)
    r = analisar_bytes(buf.getvalue(), "trabalho.docx")
    assert {"gerador_programatico", "metadados_inconsistentes"} <= nomes(r)
    assert "texto_colado" not in nomes(r)  # mesma causa: nao conta duas vezes


def test_docx_com_credencial_c2pa_vira_ia():
    r = analisar_bytes(docx(extras={"META-INF/content_credential.c2pa": MANIFESTO_IA}), "trabalho.docx")
    assert r["estrutura"]["c2pa"]["gerador"] == "ChatGPT"
    assert "credencial_c2pa_ia" in nomes(r)
    assert r["resultado"] == "IA/MANIPULADA"


def test_docx_com_macro_gera_alerta_de_seguranca():
    r = analisar_bytes(docx(extras={"word/vbaProject.bin": b"\x00" * 10}), "x.docx")
    assert any("macros" in a for a in r["alertas_seguranca"])


def test_cnpj_errado_digitado_pesa_menos_que_no_pdf():
    r = analisar_bytes(docx(texto="Recibo emitido por CNPJ 11.222.333/0001-82. " * 3), "recibo.docx")
    assert "dv_invalido_digitado" in nomes(r) and "dv_invalido" not in nomes(r)
    assert r["resultado"] == "INCONCLUSIVO"


# ---------------------------------------------------------------- .txt


def test_txt_simples():
    r = analisar_bytes(TEXTO.encode("utf-8"), "texto.txt")
    assert r["formato"] == "txt" and r["resultado"] == "INCONCLUSIVO" and nomes(r) == set()
    assert any(".txt não guarda" in lim for lim in r["limitacoes"])


def test_txt_latin1_e_bom_inicial_nao_quebram():
    assert analisar_bytes("Recibo de aluguel, São Paulo".encode("latin-1"), "a.txt")["formato"] == "txt"
    assert analisar_bytes(b"\xef\xbb\xbf" + TEXTO.encode("utf-8"), "b.txt")["estrutura"]["caracteres_invisiveis"] == 0


def test_txt_com_caracteres_invisiveis():
    zw = chr(0x200B)
    r = analisar_bytes(("texto" + zw) .join(["a"] * 6).encode("utf-8"), "c.txt")
    assert r["estrutura"]["caracteres_invisiveis"] >= 3
    assert "caracteres_invisiveis" in nomes(r)


def test_txt_com_manifesto_c2pa_em_seletores_de_variacao():
    """Cada seletor de variacao invisivel carrega um byte do manifesto."""
    oculto = "".join(chr(0xFE00 + b) if b < 16 else chr(0xE0100 + b - 16) for b in MANIFESTO_IA)
    r = analisar_bytes(("Redação sobre o Realismo." + oculto).encode("utf-8"), "redacao.txt")
    assert r["estrutura"]["c2pa"]["declara_ia"]
    assert r["resultado"] == "IA/MANIPULADA"


# ---------------------------------------------------------------- .doc e formatos recusados

OLE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 504


def test_doc_sem_olefile_fica_inconclusivo(monkeypatch):
    monkeypatch.setitem(sys.modules, "olefile", None)
    r = analisar_bytes(OLE, "antigo.doc")
    assert r["formato"] == "doc" and r["resultado"] == "INCONCLUSIVO"
    assert any("olefile" in lim for lim in r["limitacoes"])
    assert any(".doc (formato antigo)" in lim for lim in r["limitacoes"])


def test_doc_corrompido_e_formato_desconhecido():
    pytest.importorskip("olefile")
    with pytest.raises(ValueError):
        analisar_bytes(OLE, "antigo.doc")
    with pytest.raises(ValueError):
        analisar_bytes(b"\x00\x01planilha", "dados.xlsx")


def test_rota_aceita_os_novos_formatos():
    from aida_documents.servidor import EXTENSOES

    assert {".pdf", ".docx", ".doc", ".txt"} <= EXTENSOES
