"""Testes das caracteristicas e do estudo/treino do AIDA Documents."""

from __future__ import annotations

import io

import numpy as np
import pytest

from aida_documents.caracteristicas import NOMES_CARACTERISTICAS, caracteristicas_bytes

canvas = pytest.importorskip("reportlab.pdfgen.canvas")


def pdf_reportlab(texto="Questao 1. Explique o conto. ______________________"):
    from reportlab.lib.pagesizes import A4

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.drawString(40, 800, texto)
    c.save()
    return buf.getvalue()


def test_estilo_reportlab_aparece_nas_caracteristicas():
    vetor, valores = caracteristicas_bytes(pdf_reportlab())
    assert len(vetor) == len(NOMES_CARACTERISTICAS)
    assert valores["fracao_fontes_padrao_sem_embutir"] == 1.0
    assert valores["pagina_a4_reportlab"] == 1.0
    assert valores["conteudo_inicia_estilo_reportlab"] == 1.0
    assert valores["fracao_fontes_subconjunto"] == 0.0
    assert valores["linhas_de_preencher_por_mil"] > 0


def test_estilo_sobrevive_a_regravacao_pelo_pypdf():
    """Documento-IA.pdf de 08/10: ReportLab regravado pelo pypdf perde o Producer, nao o estilo."""
    from pypdf import PdfReader, PdfWriter

    writer = PdfWriter()
    writer.append(PdfReader(io.BytesIO(pdf_reportlab())))
    saida = io.BytesIO()
    writer.write(saida)
    _, valores = caracteristicas_bytes(saida.getvalue())
    assert valores["conteudo_inicia_estilo_reportlab"] == 1.0
    assert valores["pagina_a4_reportlab"] == 1.0


def test_estudo_e_validacao_deixa_um_de_fora():
    pytest.importorskip("sklearn")
    from aida_documents.treinar import MIN_POR_CLASSE, avaliar, estudar, treinar_final

    rng = np.random.default_rng(0)
    X = rng.normal(size=(40, len(NOMES_CARACTERISTICAS)))
    y = np.array([0] * 20 + [1] * 20)
    X[y == 1, 0] += 6  # so a primeira caracteristica separa
    estudo = estudar(X, y)
    assert estudo[0]["caracteristica"] == NOMES_CARACTERISTICAS[0] and estudo[0]["auc_sozinha"] == 1.0
    res, p = avaliar(X, y)
    assert res["auc_fora_da_amostra"] >= 0.95 and not np.isnan(p).any()
    assert str(MIN_POR_CLASSE) in res["aviso"]
    with pytest.raises(ValueError):
        treinar_final(X, y)
