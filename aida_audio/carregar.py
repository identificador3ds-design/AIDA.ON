"""Leitura de audio de qualquer arquivo (WAV, MP3, M4A, OGG/Opus, e a trilha de um video).

Tudo passa pelo PyAV, que traz as bibliotecas do FFmpeg dentro da roda do pip:
nao e preciso instalar o executavel ffmpeg nem coloca-lo no PATH.

O formato de saida e sempre o mesmo que os modelos de audio esperam:
mono, 16 kHz, float32 no intervalo [-1, 1]. Padronizar aqui evita que a taxa
de amostragem do arquivo de origem vire uma "caracteristica" que o modelo
aprende no lugar do indicio real (ex.: todo audio de IA do dataset em 24 kHz).
"""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

TAXA_PADRAO = 16000


def descrever_erro_ffmpeg(exc):
    """So a descricao do FFmpeg, sem o caminho do arquivo que ele anexa
    (no servidor, esse caminho e uma pasta temporaria interna)."""
    return getattr(exc, "strerror", None) or type(exc).__name__


class AudioAusente(ValueError):
    """O arquivo abriu, mas nao tem nenhuma trilha de audio (ex.: gravacao de tela muda)."""


def _abrir(caminho):
    import av  # import tardio: quem so extrai caracteristicas de um array nao precisa do PyAV

    caminho = Path(caminho)
    if not caminho.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho}")
    if caminho.stat().st_size == 0:
        raise ValueError(f"Arquivo vazio: {caminho.name}")
    try:
        # Tags de audiolivro (MLS) vem em Latin-1: com o padrao "strict" o PyAV
        # falha ao abrir o arquivo inteiro por causa do titulo.
        return av.open(str(caminho), metadata_errors="replace")
    except av.FFmpegError as exc:
        raise ValueError(f"Não foi possível abrir '{caminho.name}' como mídia: {descrever_erro_ffmpeg(exc)}") from exc


def _mono(quadro):
    dados = quadro.to_ndarray()  # formato planar: (canais, amostras)
    return dados.mean(axis=0) if dados.ndim == 2 else dados.reshape(-1)


def carregar_audio(caminho, taxa=TAXA_PADRAO, max_segundos=None):
    """Decodifica a primeira trilha de audio. Devolve (amostras float32 mono, taxa).

    Levanta AudioAusente se nao houver trilha de audio e ValueError se o arquivo
    nao for uma midia legivel.
    """
    import av

    limite = int(max_segundos * taxa) if max_segundos else None
    with _abrir(caminho) as container:
        if not container.streams.audio:
            raise AudioAusente(f"'{Path(caminho).name}' não tem trilha de áudio.")
        trilha = container.streams.audio[0]
        # Reamostra mantendo os canais e tira a MEDIA depois. O downmix do FFmpeg
        # soma os canais com ganho de +3 dB: o mesmo som em estereo ficaria mais
        # alto que em mono, e o volume viraria uma pista falsa para o modelo.
        reamostrador = av.AudioResampler(format="fltp", rate=taxa)
        pedacos = []
        total = 0
        try:
            for pacote in container.demux(trilha):
                for quadro in pacote.decode():
                    for saida in reamostrador.resample(quadro):
                        pedaco = _mono(saida)
                        pedacos.append(pedaco)
                        total += pedaco.size
                if limite and total >= limite:
                    break
            # Descarrega o que ficou no buffer interno do reamostrador.
            for saida in reamostrador.resample(None):
                pedacos.append(_mono(saida))
        except av.FFmpegError as exc:
            if not pedacos:
                raise ValueError(f"Trilha de áudio corrompida em '{Path(caminho).name}': {descrever_erro_ffmpeg(exc)}") from exc
            # Arquivo truncado no fim: aproveita o que foi lido.

    amostras = np.concatenate(pedacos).astype(np.float32) if pedacos else np.zeros(0, np.float32)
    if limite:
        amostras = amostras[:limite]
    np.clip(amostras, -1.0, 1.0, out=amostras)
    return amostras, taxa


def salvar_wav(caminho, amostras, taxa=TAXA_PADRAO):
    """Grava PCM 16 bits mono. Usa so a biblioteca padrao."""
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    pcm = (np.clip(np.asarray(amostras, dtype=np.float32), -1.0, 1.0) * 32767.0).astype("<i2")
    with wave.open(str(caminho), "wb") as arquivo:
        arquivo.setnchannels(1)
        arquivo.setsampwidth(2)
        arquivo.setframerate(int(taxa))
        arquivo.writeframes(pcm.tobytes())
    return caminho
