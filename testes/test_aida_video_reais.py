"""Regressao: 14 videos REAIS (teste1-14) nao podem ser acusados de IA.

Usa as leituras de producao guardadas em testes/dados/videos_reais_producao.json
(quadros do Core, movimento e audio) e refaz so a decisao: a fusao publicada em
aida_video/modelos/fusao.joblib e as regras. Uma mudanca de modelo, limiar ou
regra que marque algum deles como IA quebra este teste antes da publicacao.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aida_video import fusao
from aida_video.agregacao import IA, INCONCLUSIVO, REAL, agregar, combinar, combinar_visual

DADOS = Path(__file__).resolve().parent / "dados" / "videos_reais_producao.json"
VIDEOS = json.loads(DADOS.read_text(encoding="utf-8"))["videos"]
# Referencia de 29/09/2026: 13 REAL e 1 INCONCLUSIVO (teste10). Pode haver mais
# inconclusivos no futuro, mas nao falso positivo e nao muitos inconclusivos.
MAX_INCONCLUSIVOS = 2


def _decidir(video, pacote):
    ponderada = fusao.combinar_ponderado(video["frames"], video["trajetoria"], video["audio"], pacote)
    if ponderada:
        return ponderada["resultado"]
    visual = combinar_visual(agregar(video["frames"]), video["trajetoria"])
    return combinar(visual, video["audio"])["resultado"]


@pytest.fixture(scope="module")
def pacote():
    p = fusao.carregar_modelo()
    if p is None:
        pytest.skip("aida_video/modelos/fusao.joblib ausente")
    return p


@pytest.mark.parametrize("nome", sorted(VIDEOS, key=lambda n: int(n[5:])))
def test_video_real_nao_vira_ia(nome, pacote):
    assert _decidir(VIDEOS[nome], pacote) != IA


def test_poucos_inconclusivos(pacote):
    resultados = [_decidir(v, pacote) for v in VIDEOS.values()]
    assert resultados.count(INCONCLUSIVO) <= MAX_INCONCLUSIVOS
    assert resultados.count(REAL) >= len(VIDEOS) - MAX_INCONCLUSIVOS


def test_regras_sozinhas_tambem_nao_acusam():
    """Sem a fusao (ex.: movimento indisponivel no Space) as regras seguram o falso positivo."""
    for nome, video in VIDEOS.items():
        visual = combinar_visual(agregar(video["frames"]), video["trajetoria"])
        assert combinar(visual, video["audio"])["resultado"] != IA, nome


def test_audio_perto_do_limiar_fica_de_fora_no_teste11(pacote):
    video = VIDEOS["teste11"]
    assert 0.63 < video["audio"]["probabilidade_ia"] < 0.65
    saida = fusao.combinar_ponderado(video["frames"], video["trajetoria"], video["audio"], pacote)
    assert saida["combinacao"]["usa_audio"] is False
    assert saida["resultado"] == REAL
