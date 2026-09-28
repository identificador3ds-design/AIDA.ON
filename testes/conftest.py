"""Fixtures compartilhadas: midia sintetica gerada na hora, sem arquivos no repositorio."""

from __future__ import annotations

import sys
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))


@pytest.fixture(autouse=True)
def _sem_modelos_treinados(monkeypatch, tmp_path_factory):
    """Os testes nunca usam os modelos treinados de verdade (trajetoria.joblib,
    modelo_audio.joblib): o resultado mudaria a cada retreino e o DINOv2 levaria
    minutos. Quem precisa de modelo passa um explicitamente."""
    from aida_audio import analisar as mod_analisar
    from aida_audio.modelo import ARQUIVO_MODELO as MODELO_AUDIO
    from aida_video import trajetoria as mod_trajetoria

    monkeypatch.setattr(mod_trajetoria, "ARQUIVO_MODELO", tmp_path_factory.mktemp("sem_modelo") / "trajetoria.joblib")
    carregar = mod_analisar.carregar_modelo
    monkeypatch.setattr(
        mod_analisar, "carregar_modelo",
        lambda caminho=MODELO_AUDIO: None if Path(caminho) == MODELO_AUDIO else carregar(caminho),
    )


def gerar_video(
    caminho,
    cenas=((0, 0, 255), (0, 255, 0), (255, 0, 0)),
    segundos_por_cena=2.0,
    fps=25,
    tamanho=(160, 120),
    com_audio=True,
    quadrado_movel=True,
):
    """Cenas de cor solida (cortes nitidos) com um quadrado branco se movendo.

    Audio: seno de 440 Hz em estereo 44,1 kHz (forca reamostragem para 16 kHz mono).
    """
    import av

    largura, altura = tamanho
    caminho = Path(caminho)
    with av.open(str(caminho), "w") as saida:
        video = saida.add_stream("mpeg4", rate=fps)
        video.width, video.height = largura, altura
        video.pix_fmt = "yuv420p"
        audio = None
        if com_audio:
            audio = saida.add_stream("aac", rate=44100)
            audio.layout = "stereo"

        n_por_cena = int(round(segundos_por_cena * fps))
        indice = 0
        for cor in cenas:
            for i in range(n_por_cena):
                quadro = np.zeros((altura, largura, 3), np.uint8)
                quadro[:] = cor
                if quadrado_movel:
                    x = (i * 3) % (largura - 20)
                    quadro[50:70, x : x + 20] = 255
                vf = av.VideoFrame.from_ndarray(quadro, format="rgb24")
                vf.pts = indice
                vf.time_base = Fraction(1, fps)
                for pacote in video.encode(vf):
                    saida.mux(pacote)
                indice += 1
        for pacote in video.encode():
            saida.mux(pacote)

        if audio is not None:
            total_s = segundos_por_cena * len(cenas)
            taxa = 44100
            t = np.arange(int(total_s * taxa)) / taxa
            sinal = (0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
            estereo = np.stack([sinal, sinal])
            bloco = 1024
            for inicio in range(0, estereo.shape[1] - bloco + 1, bloco):
                af = av.AudioFrame.from_ndarray(
                    np.ascontiguousarray(estereo[:, inicio : inicio + bloco]), format="fltp", layout="stereo"
                )
                af.sample_rate = taxa
                af.pts = inicio
                af.time_base = Fraction(1, taxa)
                for pacote in audio.encode(af):
                    saida.mux(pacote)
            for pacote in audio.encode():
                saida.mux(pacote)
    return caminho


@pytest.fixture
def video_tres_cenas(tmp_path):
    return gerar_video(tmp_path / "tres_cenas.mp4")


@pytest.fixture
def video_sem_audio(tmp_path):
    return gerar_video(tmp_path / "mudo.mp4", com_audio=False)


@pytest.fixture
def video_parado(tmp_path):
    return gerar_video(
        tmp_path / "parado.mp4", cenas=((90, 90, 90),), segundos_por_cena=6.0, quadrado_movel=False, com_audio=False
    )
