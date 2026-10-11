"""INCONCLUSIVO pede outra evidência e combina as respostas (decisão de 11/10/2026).

As regras vivem em scripts/aida-evidencia-combinada.js (puro, sem DOM) e são
exercitadas aqui pelo Node, o mesmo que o CI já usa para checar a sintaxe JS.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
MODULO = RAIZ / "scripts" / "aida-evidencia-combinada.js"
PAGINA = (RAIZ / "pages" / "index-analise.html").read_text(encoding="utf-8")
ANALISE = (RAIZ / "scripts" / "script-analise.js").read_text(encoding="utf-8")

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node ausente")

LIM = 0.686


def _combinar(evidencias, concluir=False):
    codigo = (f"const m=require({json.dumps(str(MODULO))});"
              f"process.stdout.write(JSON.stringify(m.combinar({json.dumps(evidencias)},{json.dumps(concluir)})))")
    saida = subprocess.run(["node", "-e", codigo], capture_output=True, text=True, check=True)
    return json.loads(saida.stdout)


def ev(resultado, p, **extra):
    return {"resultado": resultado, "probabilidade_ia": p, "limiar": LIM, **extra}


def test_uma_inconclusiva_pede_evidencia():
    c = _combinar([ev("INCONCLUSIVO", 0.70)])
    assert c["estado"] == "PEDIR_EVIDENCIA" and c["resultado"] == "INCONCLUSIVO"


def test_segunda_evidencia_conclusiva_decide():
    c = _combinar([ev("INCONCLUSIVO", 0.70), ev("IA/MANIPULADA", 0.95)])
    assert c["estado"] == "DECIDIDO" and c["resultado"] == "IA/MANIPULADA" and c["confianca"] == "media"
    c = _combinar([ev("INCONCLUSIVO", 0.62), ev("REAL", 0.10)])
    assert c["resultado"] == "REAL"


def test_real_com_editor_vira_real_editada():
    c = _combinar([ev("INCONCLUSIVO", 0.62), ev("REAL_EDITADA", 0.10, editada=True)])
    assert c["resultado"] == "REAL_EDITADA"


def test_contradicao_pede_mais_e_no_maximo_decide_pela_media():
    duas = [ev("INCONCLUSIVO", 0.70), ev("REAL", 0.20), ev("IA/MANIPULADA", 0.90)][:2]
    assert _combinar(duas)["estado"] == "DECIDIDO"              # só um lado decidido: decide
    contra = [ev("REAL", 0.20), ev("IA/MANIPULADA", 0.90)]
    c = _combinar(contra)
    assert c["estado"] == "PEDIR_EVIDENCIA" and "contradizem" in c["motivo"]
    c = _combinar(contra + [ev("INCONCLUSIVO", 0.70)])        # 3 = máximo
    assert c["estado"] == "DECIDIDO" and c["confianca"] == "baixa"
    assert c["resultado"] == "REAL"                              # média 0,60 < 0,686


def test_concluir_com_o_que_tem_usa_a_media():
    c = _combinar([ev("INCONCLUSIVO", 0.70), ev("INCONCLUSIVO", 0.74)], concluir=True)
    assert c["estado"] == "DECIDIDO" and c["resultado"] == "IA/MANIPULADA" and c["confianca"] == "baixa"


def test_fora_do_escopo_nao_conta():
    c = _combinar([ev("INCONCLUSIVO", 0.70), ev("INCONCLUSIVO", 0.1, fora_de_dominio=True)])
    assert c["n"] == 1 and c["ignoradas"] == 1 and c["estado"] == "PEDIR_EVIDENCIA"


def test_pagina_carrega_o_modulo_e_tem_o_painel():
    assert "aida-evidencia-combinada.js" in PAGINA
    assert PAGINA.index("aida-evidencia-combinada.js") < PAGINA.index("script-analise.js")
    for ident in ("blocoEvidenciaExtra", "btnEvidenciaExtra", "inputEvidenciaExtra", "btnConcluirEvidencias"):
        assert f'id="{ident}"' in PAGINA
    assert "renderizarPedidoEvidencia(dados);" in ANALISE
    # Evidência extra não grava no histórico do usuário.
    assert 'formData.append("historico_habilitado", "false");' in ANALISE
