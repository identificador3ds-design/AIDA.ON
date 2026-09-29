"""Testes da analise de movimento (trajetoria DINOv2) e da sua juncao ao voto dos frames.

O DINOv2 nunca e carregado: o codificador e um falso deterministico e os
modelos sao LogReg minusculos treinados na hora.
"""

from __future__ import annotations

import joblib
import numpy as np
import pytest

from aida_video.agregacao import IA, INCONCLUSIVO, REAL, agregar, combinar_visual
from aida_video.analisadores import AnalisadorFixo
from aida_video.analisar_video import analisar_video
from aida_video.trajetoria import NOMES_CARACTERISTICAS, analisar_trajetoria

FRAME_REAL = {"resultado": REAL, "probabilidade_ia": 0.1, "fora_de_dominio": False}
FRAME_IA = {"resultado": IA, "probabilidade_ia": 0.9, "fora_de_dominio": False}
FRAME_INC = {"resultado": INCONCLUSIVO, "probabilidade_ia": 0.5, "fora_de_dominio": False}


class CodificadorFalso:
    def codificar(self, frames):
        return np.arange(len(frames) * 4, dtype=np.float64).reshape(len(frames), 4) ** 1.5


def _modelo_constante(prob_ia, n_colunas):
    """LogReg que devolve ~prob_ia para qualquer entrada (so o intercepto importa)."""
    from sklearn.linear_model import LogisticRegression

    m = LogisticRegression()
    m.classes_ = np.array([0, 1])
    m.coef_ = np.zeros((1, n_colunas))
    m.intercept_ = np.array([np.log(prob_ia / (1 - prob_ia))])
    return m


@pytest.fixture
def modelo(tmp_path):
    def salvar(prob_traj, prob_fusao=None):
        n = len(NOMES_CARACTERISTICAS)
        pacote = {"modelo": _modelo_constante(prob_traj, n), "limiar": 0.5}
        if prob_fusao is not None:
            pacote["modelo_fusao"] = _modelo_constante(prob_fusao, n + 1)
        caminho = tmp_path / "trajetoria.joblib"
        joblib.dump(pacote, caminho)
        return caminho
    return salvar


def _visual(resultado):
    frames = {REAL: [FRAME_REAL] * 5, IA: [FRAME_IA] * 5, INCONCLUSIVO: [FRAME_INC] * 5}[resultado]
    frames = [{**f, "tempo_s": float(i)} for i, f in enumerate(frames)]
    v = agregar(frames)
    assert v["resultado"] == resultado
    return v


# ------------------------------------------------------------ combinar_visual


def test_sem_trajetoria_o_voto_dos_frames_fica():
    v = _visual(REAL)
    assert combinar_visual(v, None) is v
    assert combinar_visual(v, {"disponivel": False, "motivos": ["x"]}) is v


@pytest.mark.parametrize("prob, esperado", [(0.9, IA), (0.75, IA), (0.5, INCONCLUSIVO), (0.35, REAL), (0.1, REAL)])
def test_trajetoria_decide_quando_os_frames_nao_dizem_ia(prob, esperado):
    for frames in (REAL, INCONCLUSIVO):
        r = combinar_visual(_visual(frames), {"disponivel": True, "probabilidade_ia": prob, "usa_core": True})
        assert r["resultado"] == esperado
        assert r["resultado_frames"] == frames
        assert "movimento entre frames" in r["motivos"][0]


@pytest.mark.parametrize("prob, esperado", [(0.65, INCONCLUSIVO), (0.74, INCONCLUSIVO), (0.75, IA)])
def test_movimento_pouco_acima_do_limite_nao_derruba_frames_reais(prob, esperado):
    r = combinar_visual(_visual(REAL), {"disponivel": True, "probabilidade_ia": prob, "usa_core": True})
    assert r["resultado"] == esperado
    # com os frames inconclusivos a margem nao vale: o movimento decide como antes
    r = combinar_visual(_visual(INCONCLUSIVO), {"disponivel": True, "probabilidade_ia": prob, "usa_core": True})
    assert r["resultado"] == IA


def test_ia_pelos_frames_nao_e_desfeita_pela_trajetoria():
    r = combinar_visual(_visual(IA), {"disponivel": True, "probabilidade_ia": 0.05})
    assert r["resultado"] == IA
    assert any("movimento" in m for m in r["motivos"])


# ------------------------------------------------------- analisar_trajetoria


def test_sem_modelo_fica_indisponivel(video_tres_cenas, tmp_path):
    r = analisar_trajetoria(video_tres_cenas, caminho_modelo=tmp_path / "nao_existe.joblib")
    assert r["disponivel"] is False
    assert "não treinado" in r["motivos"][0]


def test_usa_fusao_quando_ha_prob_do_core(video_tres_cenas, modelo):
    caminho = modelo(prob_traj=0.2, prob_fusao=0.8)
    so_traj = analisar_trajetoria(video_tres_cenas, caminho_modelo=caminho, codificador=CodificadorFalso())
    fusao = analisar_trajetoria(video_tres_cenas, prob_core=0.7, caminho_modelo=caminho, codificador=CodificadorFalso())
    assert so_traj["disponivel"] and not so_traj["usa_core"]
    assert so_traj["probabilidade_ia"] == pytest.approx(0.2, abs=1e-3)
    assert so_traj["resultado"] == REAL
    assert fusao["usa_core"] and fusao["resultado"] == IA
    assert fusao["janelas"] == 1


def test_sem_modelo_de_fusao_usa_so_a_trajetoria(video_tres_cenas, modelo):
    r = analisar_trajetoria(video_tres_cenas, prob_core=0.9, caminho_modelo=modelo(0.3), codificador=CodificadorFalso())
    assert r["usa_core"] is False and r["probabilidade_ia"] == pytest.approx(0.3, abs=1e-3)


def test_falha_no_codificador_nao_derruba(video_tres_cenas, modelo):
    class Quebrado:
        def codificar(self, frames):
            raise RuntimeError("sem memoria")

    r = analisar_trajetoria(video_tres_cenas, caminho_modelo=modelo(0.3), codificador=Quebrado())
    assert r["disponivel"] is False and "sem memoria" in r["motivos"][0]


# ------------------------------------------------------------------ pipeline


def test_pipeline_trajetoria_muda_o_resultado_e_vai_no_relatorio(video_tres_cenas, modelo, monkeypatch):
    from aida_video import trajetoria as mod

    monkeypatch.setattr(mod, "ARQUIVO_MODELO", modelo(prob_traj=0.1, prob_fusao=0.9))
    monkeypatch.setattr(mod, "_codificador", CodificadorFalso)
    r = analisar_video(video_tres_cenas, analisador=AnalisadorFixo([FRAME_REAL]))
    assert r["trajetoria"]["usa_core"] is True  # a mediana dos frames (0.1) foi para a fusao
    assert r["visual"]["resultado_frames"] == REAL
    assert r["visual"]["resultado"] == IA
    assert r["resultado"] == IA

    sem = analisar_video(video_tres_cenas, analisador=AnalisadorFixo([FRAME_REAL]), com_trajetoria=False)
    assert sem["trajetoria"] is None and sem["resultado"] == REAL
