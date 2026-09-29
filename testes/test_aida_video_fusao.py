"""Testes da combinacao ponderada (aida_video/fusao.py). Sem rede e sem torch."""

from __future__ import annotations

import numpy as np
import pytest

from aida_video import analisar_video as pipeline
from aida_video import fusao
from aida_video.agregacao import IA, INCONCLUSIVO, REAL
from aida_video.analisadores import AnalisadorFixo


def _frames(n_ia, n_real, p_ia=0.9, p_real=0.1):
    return ([{"resultado": IA, "probabilidade_ia": p_ia}] * n_ia
            + [{"resultado": REAL, "probabilidade_ia": p_real}] * n_real)


def _videos_sinteticos(n=40, semente=0):
    """Reais com audio; metade da IA sem audio (o atalho que o modelo nao pode aprender)."""
    rng = np.random.default_rng(semente)
    videos, registros = [], []
    geradores = ["g1", "g2", "g3", "g4"]
    for i in range(n):
        ia = i % 2 == 1
        gerador = geradores[(i // 2) % 4] if ia else "real"
        p = float(np.clip(rng.normal(0.7 if ia else 0.3, 0.15), 0.01, 0.99))
        n_ia = int(round(8 * p))
        tem_audio = (not ia) or (i % 4 == 1)
        rotulo = IA if ia else REAL
        nome = f"{gerador}_{i}.mp4" if ia else f"real{i}.mp4"
        videos.append({"video": nome, "rotulo": rotulo, "gerador": gerador, "frames": _frames(n_ia, 8 - n_ia),
                       "p_trajetoria": p, "p_audio": float(np.clip(p + rng.normal(0, 0.1), 0.01, 0.99)) if tem_audio else None})
        registros.append({"video": nome, "rotulo": rotulo, "pasta": "ia" if ia else "reais"})
    return registros, videos


def test_caracteristicas_colunas_e_valores():
    linha = fusao.caracteristicas(_frames(3, 1, p_ia=0.8), 0.5, None)
    assert len(linha) == len(fusao.NOMES_VISUAIS) + len(fusao.NOMES_AUDIO)
    assert linha[0] == pytest.approx(0.0)  # logit(0,5)
    assert linha[1:3] == [0.75, 0.25]
    assert linha[3] == pytest.approx(np.log(0.8 / 0.2))
    assert linha[4] == 0.0  # sem audio


def test_frames_com_erro_e_fora_de_dominio_nao_contam():
    frames = _frames(1, 1) + [{"erro": "timeout"}, {"resultado": IA, "probabilidade_ia": 0.99, "fora_de_dominio": True}]
    linha = fusao.caracteristicas(frames, 0.5)
    assert linha[1] == pytest.approx(2 / 3)  # 3 frames com resultado, 2 IA
    assert linha[3] == pytest.approx(np.log(0.9 / 0.1))  # o fora de dominio nao vira o maximo


def test_video_sem_audio_usa_so_o_modelo_de_imagem():
    _, videos = _videos_sinteticos()
    X, y, a = fusao._matriz(videos)
    modelo = fusao.Fusao().fit(X, y, a)
    sem = ~a
    esperado = modelo.visual.predict_proba(X[sem][:, : len(fusao.NOMES_VISUAIS)])[:, 1]
    assert modelo.prob(X[sem], a[sem]) == pytest.approx(esperado)
    # A coluna do audio de um video sem audio nao muda nada.
    X2 = X.copy()
    X2[sem, -1] = 5.0
    assert modelo.prob(X2[sem], a[sem]) == pytest.approx(esperado)


def test_sem_as_duas_classes_com_audio_fica_so_a_imagem():
    _, videos = _videos_sinteticos()
    for v in videos:
        if v["rotulo"] == IA:
            v["p_audio"] = None
    X, y, a = fusao._matriz(videos)
    modelo = fusao.Fusao().fit(X, y, a)
    assert modelo.com_audio is None
    assert modelo.prob(X, a) == pytest.approx(modelo.visual.predict_proba(X[:, :4])[:, 1])


def test_limiares_respeitam_o_alvo_de_falso_positivo():
    rng = np.random.default_rng(1)
    y = np.array([0] * 200 + [1] * 200)
    p = np.concatenate([rng.beta(2, 5, 200), rng.beta(5, 2, 200)])
    baixo, alto = fusao.escolher_limiares(y, p, fp_alvo=0.05, ia_como_real_alvo=0.10)
    assert baixo <= alto
    assert np.mean(p[y == 0] >= alto) <= 0.05
    assert np.mean(p[y == 1] < baixo) <= 0.10


@pytest.mark.parametrize("prob,esperado", [(0.9, IA), (0.5, INCONCLUSIVO), (0.1, REAL)])
def test_decidir(prob, esperado):
    assert fusao.decidir(prob, 0.3, 0.7) == esperado


def test_fora_da_amostra_preve_todos_os_videos():
    registros, videos = _videos_sinteticos()
    previstos, prob = fusao.fora_da_amostra_ponderada(registros, videos)
    assert len(previstos) == len(videos) and all(p in (IA, REAL, INCONCLUSIVO) for p in previstos)
    assert not np.isnan(prob).any()


def _pacote(videos):
    X, y, a = fusao._matriz(videos)
    return {"modelo": fusao.Fusao().fit(X, y, a), "faixa_inconclusiva": (0.4, 0.6)}


def test_combinar_ponderado_sem_entradas_devolve_none():
    _, videos = _videos_sinteticos()
    pacote = _pacote(videos)
    traj = {"disponivel": True, "probabilidade_ia": 0.9}
    assert fusao.combinar_ponderado(_frames(4, 0), traj, None, None) is None
    assert fusao.combinar_ponderado(_frames(4, 0), {"disponivel": False}, None, pacote) is None
    assert fusao.combinar_ponderado([{"erro": "x"}], traj, None, pacote) is None


def test_combinar_ponderado_decide_e_explica():
    _, videos = _videos_sinteticos()
    pacote = _pacote(videos)
    ia = fusao.combinar_ponderado(_frames(8, 0), {"disponivel": True, "probabilidade_ia": 0.95},
                                  {"resultado": IA, "probabilidade_ia": 0.9}, pacote)
    real = fusao.combinar_ponderado(_frames(0, 8), {"disponivel": True, "probabilidade_ia": 0.05},
                                    {"resultado": REAL, "probabilidade_ia": 0.05}, pacote)
    assert ia["resultado"] == IA and real["resultado"] == REAL
    assert ia["combinacao"]["usa_audio"] is True
    assert "imagem, movimento e áudio" in ia["motivos"][0]
    sem_audio = fusao.combinar_ponderado(_frames(8, 0), {"disponivel": True, "probabilidade_ia": 0.95},
                                         {"resultado": "INCONCLUSIVO", "presente": True, "probabilidade_ia": None}, pacote)
    assert sem_audio["combinacao"]["usa_audio"] is False
    assert any("só pela imagem" in m for m in sem_audio["motivos"])


@pytest.mark.parametrize("prob, esperado", [(None, None), (0.64, None), (0.50, None), (0.77, None),
                                            (0.30, 0.30), (0.90, 0.90)])
def test_audio_perto_do_limiar_nao_entra(prob, esperado):
    assert fusao.audio_utilizavel(prob, 0.63) == esperado


def test_audio_de_confianca_baixa_nao_decide_o_video():
    """Caso do teste11: imagem e movimento de camera real, audio 0,64 logo acima do limiar 0,63."""
    _, videos = _videos_sinteticos()
    pacote = _pacote(videos)
    traj = {"disponivel": True, "probabilidade_ia": 0.1}
    incerto = fusao.combinar_ponderado(_frames(0, 8), traj, {"probabilidade_ia": 0.64, "limiar": 0.63}, pacote)
    so_imagem = fusao.combinar_ponderado(_frames(0, 8), traj, None, pacote)
    assert incerto["combinacao"]["usa_audio"] is False
    assert incerto["combinacao"]["probabilidade_ia"] == so_imagem["combinacao"]["probabilidade_ia"]
    assert any("confiança baixa" in m for m in incerto["motivos"])


def test_pipeline_usa_a_combinacao_quando_ha_modelo(video_tres_cenas, monkeypatch):
    _, videos = _videos_sinteticos()
    pacote = _pacote(videos)
    import aida_video.trajetoria as trajetoria

    monkeypatch.setattr(trajetoria, "analisar_trajetoria",
                        lambda *a, **k: {"disponivel": True, "probabilidade_ia": 0.97, "motivos": []})
    monkeypatch.setattr(fusao, "carregar_modelo", lambda *a, **k: pacote)
    rel = pipeline.analisar_video(video_tres_cenas, analisador=AnalisadorFixo([{"resultado": IA, "probabilidade_ia": 0.95, "fora_de_dominio": False}]))
    assert rel["combinacao"]["metodo"] == "ponderada"
    assert rel["resultado"] == IA
    assert "resultado_regras" in rel
    assert rel["motivos"][0].startswith("combinação ponderada")


def test_pipeline_sem_modelo_segue_pelas_regras(video_tres_cenas, monkeypatch):
    import aida_video.trajetoria as trajetoria

    monkeypatch.setattr(trajetoria, "analisar_trajetoria",
                        lambda *a, **k: {"disponivel": True, "probabilidade_ia": 0.97, "motivos": []})
    monkeypatch.setattr(fusao, "carregar_modelo", lambda *a, **k: None)
    rel = pipeline.analisar_video(video_tres_cenas, analisador=AnalisadorFixo([{"resultado": IA, "probabilidade_ia": 0.95, "fora_de_dominio": False}]))
    assert "combinacao" not in rel
    assert rel["resultado"] == IA
