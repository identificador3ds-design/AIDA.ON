"""Rota /audio/analisar no servidor do AIDA Video (AIDA Audio com página própria)."""

from __future__ import annotations

import io
import wave

import numpy as np
import pytest

from aida_video.analisadores import AnalisadorFixo
from aida_video.servidor import criar_app


@pytest.fixture
def cliente():
    app = criar_app(lambda: AnalisadorFixo([]), executar_em_thread=False)
    app.config["TESTING"] = True
    return app.test_client()


def _wav(segundos=2.0, taxa=16000):
    t = np.arange(int(segundos * taxa)) / taxa
    sinal = (0.3 * np.sin(2 * np.pi * 220 * t) * (1 + 0.5 * np.sin(2 * np.pi * 3 * t))).astype(np.float32)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(taxa)
        w.writeframes((sinal * 32767).astype("<i2").tobytes())
    buf.seek(0)
    return buf


def test_saude(cliente):
    r = cliente.get("/audio/saude")
    assert r.status_code == 200 and r.get_json()["servico"] == "AIDA Audio"


def test_analisa_wav_e_nao_devolve_caracteristicas_internas(cliente):
    r = cliente.post("/audio/analisar", data={"audio": (_wav(), "voz.wav")}, content_type="multipart/form-data")
    corpo = r.get_json()
    assert r.status_code == 200, corpo
    assert corpo["resultado"] in {"REAL", "IA/MANIPULADA", "INCONCLUSIVO"}
    assert corpo["arquivo"] == "voz.wav"
    assert "caracteristicas" not in corpo and "qualidade" in corpo


def test_recusa_sem_arquivo_e_formato_errado(cliente):
    assert cliente.post("/audio/analisar").status_code == 400
    r = cliente.post("/audio/analisar", data={"audio": (io.BytesIO(b"x"), "nota.pdf")},
                     content_type="multipart/form-data")
    assert r.status_code == 400 and "não suportado" in r.get_json()["erro"]


def test_arquivo_que_nao_e_audio_vira_400(cliente):
    r = cliente.post("/audio/analisar", data={"audio": (io.BytesIO(b"isto nao e audio" * 50), "falso.mp3")},
                     content_type="multipart/form-data")
    assert r.status_code in (400, 422)
