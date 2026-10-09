"""Testes do AIDA Documents: Benford, digitos verificadores, estrutura do PDF e decisao."""

from __future__ import annotations

import io

import numpy as np
import pytest

from aida_documents import analisar_benford, analisar_bytes, extrair_numeros, inspecionar_pdf, verificar_identificadores
from aida_documents.numeros import _dv_mod11, chave_acesso_valida, cnpj_valido, cpf_valido

canvas = pytest.importorskip("reportlab.pdfgen.canvas")

CNPJ_OK = "11.222.333/0001-81"


def chave_nfe(cnpj="11222333000181", uf="35", aamm="2609", modelo="55"):
    corpo = f"{uf}{aamm}{cnpj}{modelo}001000012345100000001"
    assert len(corpo) == 43
    return corpo + str(_dv_mod11(corpo, [2 + (i % 8) for i in range(43)][::-1]))


def pdf_texto(linhas, produtor=None):
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    if produtor:
        c.setProducer(produtor)
    y = 800
    for linha in linhas:
        c.drawString(40, y, linha)
        y -= 12
        if y < 40:
            c.showPage()
            y = 800
    c.save()
    return buf.getvalue()


def valores_benford(n, semente=0):
    return 10 ** np.random.default_rng(semente).uniform(1, 5, n)


def nota(cnpj=CNPJ_OK, n_valores=120, produtor="Emissor NF-e 4.0", chave=True):
    linhas = ["NOTA FISCAL", f"CNPJ {cnpj}", "Emissao 28/09/2026 14:32"]
    if chave:
        linhas.append(f"Chave de acesso {chave_nfe()}")
    linhas += [f"Item {i}  R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") for i, v in enumerate(valores_benford(n_valores))]
    return pdf_texto(linhas, produtor)


# ---------------------------------------------------------------- Benford


def test_benford_conforme_e_uniforme():
    boa = analisar_benford(valores_benford(2000))
    assert boa["suficiente"] and boa["mad"] < 0.006
    ruim = analisar_benford(np.random.default_rng(1).integers(10, 100, 2000))
    assert ruim["mad"] > 0.015 and ruim["p_valor"] < 1e-6


def test_benford_amostra_pequena_nao_e_suficiente():
    assert not analisar_benford([12, 34, 150])["suficiente"]


def test_p_valor_qui2_bate_com_tabela():
    from aida_documents.benford import _p_valor_qui2

    assert _p_valor_qui2(15.507) == pytest.approx(0.05, abs=1e-3)


# ---------------------------------------------------------------- identificadores


def test_digitos_verificadores():
    assert cnpj_valido(CNPJ_OK) and not cnpj_valido("11.222.333/0001-82")
    assert cnpj_valido("12.ABC.345/01DE-35")  # exemplo oficial do CNPJ alfanumerico
    assert cpf_valido("529.982.247-25") and not cpf_valido("529.982.247-26")
    assert chave_acesso_valida(chave_nfe())
    ruim = chave_nfe()[:-1] + str((int(chave_nfe()[-1]) + 1) % 10)
    assert not chave_acesso_valida(ruim)


def test_extrai_valores_sem_identificadores():
    texto = f"CNPJ {CNPJ_OK} em 28/09/2026 10:15 CEP 01310-100 total R$ 1.234,56 qtd 3 frete 45,00"
    assert extrair_numeros(texto) == [1234.56, 45.0]


def test_chave_com_emitente_diferente():
    texto = f"CNPJ {CNPJ_OK}\nChave {chave_nfe(cnpj='11444777000161')}"
    alertas = verificar_identificadores(texto)["alertas"]
    assert any("emitente" in a for a in alertas)


# ---------------------------------------------------------------- estrutura e decisao


def test_pdf_limpo_e_real():
    r = analisar_bytes(nota())
    assert r["estrutura"]["revisoes"] == 1
    assert r["benford"]["suficiente"]
    assert r["resultado"] == "REAL", r["indicios"]


def test_orcamento_inventado_com_dv_certo_nao_e_real():
    """CNPJ/CPF com DV certo saem de gerador: sem assinatura nem chave, nada comprova a origem."""
    linhas = ["ORCAMENTO", f"Empresa CNPJ {CNPJ_OK}", "Cliente CPF 529.982.247-25"]
    linhas += [f"Servico {i}  R$ {v:.2f}".replace(".", ",") for i, v in enumerate(valores_benford(15))]
    r = analisar_bytes(pdf_texto(linhas))  # produtor padrao do ReportLab
    assert r["identificadores"]["alertas"] == []
    assert {i["indicio"] for i in r["indicios"]} == {"gerador_programatico"}
    assert r["resultado"] == "INCONCLUSIVO"
    assert any("comprova a origem" in m for m in r["motivos"])


def test_cnpj_invalido_e_edicao_viram_manipulada():
    r = analisar_bytes(nota(cnpj="11.222.333/0001-82", produtor="iLovePDF"))
    nomes = {i["indicio"] for i in r["indicios"]}
    assert {"dv_invalido", "ferramenta_edicao"} <= nomes
    assert r["resultado"] == "IA/MANIPULADA"


def test_revisao_incremental_detectada():
    from pypdf import PdfWriter

    original = nota()
    writer = PdfWriter(io.BytesIO(original), incremental=True)
    writer.add_metadata({"/Author": "editado"})
    saida = io.BytesIO()
    writer.write(saida)
    est = inspecionar_pdf(saida.getvalue())
    assert est["revisoes"] == 2


def test_pdf_so_imagem_pede_ocr():
    from PIL import Image
    from reportlab.lib.utils import ImageReader

    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawImage(ImageReader(Image.new("RGB", (200, 100), "white")), 40, 600)
    c.save()
    r = analisar_bytes(buf.getvalue())
    assert r["estrutura"]["paginas_sem_texto"] == 1
    assert r["resultado"] == "INCONCLUSIVO"
    assert any(i["indicio"] == "sem_camada_texto_total" for i in r["indicios"])


def test_word_calibri_truetype_e_type0_nao_e_edicao():
    """O Word embute a Calibri como TrueType e de novo como Type0 (Identity-H): os 3 artigos
    reais de 08/10 eram acusados de "texto acrescentado por outro programa"."""
    from aida_documents.estrutura import _subconjuntos_duplicados

    word = [("/BCDEEE+Calibri", "/TrueType"), ("/BCDHEE+Calibri", "/Type0"), ("/BCDFEE+Calibri-Bold", "/TrueType")]
    assert _subconjuntos_duplicados(word) == []
    editado = [("/ABCDEF+Arial", "/TrueType"), ("/GHIJKL+Arial", "/TrueType")]
    assert _subconjuntos_duplicados(editado) == ["Arial"]


def test_produtores_pdfsam_e_pypdf():
    from aida_documents.estrutura import _ferramentas

    # PDFsam grava "SAMBox (www.sejda.org)": nao e o editor online Sejda.
    assert _ferramentas("sambox 1.1.41 (www.sejda.org) pdfsam basic v3.3.7") == ["organizador de páginas (PDFsam)"]
    assert _ferramentas("sejda") == ["editor online (Sejda)"]
    r = analisar_bytes(pdf_texto(["Prova de literatura " * 3], produtor="pypdf"))
    assert {i["indicio"] for i in r["indicios"]} == {"gerador_programatico"}


def _com_c2pa(pdf, fonte="trainedAlgorithmicMedia"):
    """Anexa um manifesto C2PA minimo (mesmos rotulos CBOR do ChatGPT) como revisao incremental."""
    from pypdf import PdfWriter

    manifesto = (
        b"\x00\x00\x00\x1ejumbjumdc2pa\x00c2pa.actions.v2cbor\xa1gactions\x81\xa3factionlc2pa.created"
        b"qdigitalSourceTypexFhttp://cv.iptc.org/newscodes/digitalsourcetype/" + fonte.encode()
        + b"msoftwareAgent\xa1dnameggpt-5-6c2pa.claim.v2tclaim_generator_info\xa1dnamegChatGPT"
    )
    writer = PdfWriter(io.BytesIO(pdf), incremental=True)
    writer.add_attachment("Content Credentials", manifesto)
    saida = io.BytesIO()
    writer.write(saida)
    return saida.getvalue()


def test_credencial_c2pa_do_chatgpt_vira_ia():
    """0015 da coleta de 09/10: prova do ChatGPT com C2PA da OpenAI estava entre os reais."""
    r = analisar_bytes(_com_c2pa(pdf_texto(["Prova de literatura " * 3], produtor="Emissor X")))
    c2pa = r["estrutura"]["c2pa"]
    assert c2pa["presente"] and c2pa["declara_ia"]
    assert (c2pa["gerador"], c2pa["modelo"]) == ("ChatGPT", "gpt-5-6")
    nomes = {i["indicio"] for i in r["indicios"]}
    assert "credencial_c2pa_ia" in nomes
    assert "revisoes_incrementais" not in nomes  # a revisao que so traz o manifesto nao e edicao
    assert r["resultado"] == "IA/MANIPULADA"
    assert any("C2PA" in lim for lim in r["limitacoes"])


def test_c2pa_sem_ia_e_pdf_sem_c2pa():
    r = analisar_bytes(_com_c2pa(pdf_texto(["Recibo " * 5], produtor="Emissor X"), fonte="digitalCapture"))
    assert r["estrutura"]["c2pa"]["presente"] and not r["estrutura"]["c2pa"]["declara_ia"]
    assert "credencial_c2pa_ia" not in {i["indicio"] for i in r["indicios"]}
    assert analisar_bytes(nota())["estrutura"]["c2pa"] == {"presente": False}


def test_imagem_e_arquivo_invalido():
    assert analisar_bytes(b"\x89PNG...", "nota.png")["resultado"] == "INCONCLUSIVO"
    with pytest.raises(ValueError):
        analisar_bytes(b"nao sou pdf", "x.pdf")


# ---------------------------------------------------------------- rotas HTTP


@pytest.fixture
def cliente():
    from aida_video.servidor import criar_app

    return criar_app(executar_em_thread=False).test_client()


def test_rota_documento_analisa_pdf(cliente):
    r = cliente.post("/documento/analisar", data={"documento": (io.BytesIO(nota()), "nota.pdf")},
                     content_type="multipart/form-data")
    assert r.status_code == 200
    corpo = r.get_json()
    assert corpo["resultado"] == "REAL" and corpo["documento"] == "nota.pdf"
    assert "texto" not in corpo["estrutura"]  # o texto do documento nunca volta


def test_rota_documento_recusa_nao_pdf(cliente):
    assert cliente.get("/documento/saude").get_json()["servico"] == "AIDA Documents"
    r = cliente.post("/documento/analisar", data={"documento": (io.BytesIO(b"oi"), "nota.txt")},
                     content_type="multipart/form-data")
    assert r.status_code == 400
    r = cliente.post("/documento/analisar", data={"documento": (io.BytesIO(b"oi"), "nota.pdf")},
                     content_type="multipart/form-data")
    assert r.status_code == 400
