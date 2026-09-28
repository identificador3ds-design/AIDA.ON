"""Padroniza videos para a rodada de controle da avaliacao em lote.

Problema que isto resolve: se os videos reais sao 4K HEVC do celular e os de IA
sao 720p H.264 recomprimidos para a web, um detector pode "acertar" olhando o
FORMATO (resolucao, codec, compressao, duracao), e nao a sintese. Levando os
dois grupos ao mesmo formato, a diferenca que sobra e a que interessa.

Tudo igual para todos:
- rotacao do celular aplicada (o arquivo sai "em pe", sem metadado de rotacao);
- lado maximo LADO px (so reduz: ampliar criaria interpolacao so num grupo);
- H.264 yuv420p com o mesmo CRF;
- no maximo MAX_S segundos (os videos de IA tem 5 a 15 s);
- audio, quando houver, em AAC mono 44,1 kHz.

Uso:
    python -m aida_video.padronizar ../videos_teste ../videos_teste_padronizado
"""

from __future__ import annotations

import argparse
import sys
from fractions import Fraction
from pathlib import Path

import numpy as np

from .extrair_frames import EXTENSOES_VIDEO, aplicar_rotacao

LADO = 854
CRF = 23
MAX_S = 10.0
FPS_MAX = 30


def _dimensoes(largura, altura, lado):
    escala = min(1.0, lado / max(largura, altura))
    # H.264 com yuv420p exige dimensoes pares.
    return max(2, int(largura * escala) // 2 * 2), max(2, int(altura * escala) // 2 * 2)


def padronizar_video(entrada, saida, lado=LADO, crf=CRF, max_s=MAX_S, fps_max=FPS_MAX):
    import av

    from aida_audio.carregar import AudioAusente, carregar_audio

    entrada, saida = Path(entrada), Path(saida)
    saida.parent.mkdir(parents=True, exist_ok=True)
    try:
        amostras_audio, _ = carregar_audio(entrada, taxa=TAXA_AUDIO, max_segundos=max_s)
    except AudioAusente:
        amostras_audio = None
    with av.open(str(entrada)) as origem:
        trilha = origem.streams.video[0]
        trilha.thread_type = "AUTO"
        trilha.codec_context.skip_frame = "NONREF"  # ver extrair_frames: 4K HEVC e lento aqui
        fps_origem = float(trilha.average_rate or trilha.guessed_rate or 30)
        fps = min(fps_max, max(1, round(fps_origem)))

        with av.open(str(saida), "w") as destino:
            video = None
            proximo_t = 0.0
            indice = 0
            for quadro in origem.decode(trilha):
                t = quadro.time if quadro.time is not None else indice / fps
                if t > max_s:
                    break
                # Reamostra para no maximo fps_max: descarta quadros entre os instantes alvo.
                if t + 1e-6 < proximo_t:
                    continue
                proximo_t += 1.0 / fps
                girado = int(round((quadro.rotation or 0) / 90.0)) % 2 == 1
                largura, altura = (quadro.height, quadro.width) if girado else (quadro.width, quadro.height)
                if video is None:
                    w, h = _dimensoes(largura, altura, lado)
                    video = destino.add_stream("libx264", rate=fps)
                    video.width, video.height, video.pix_fmt = w, h, "yuv420p"
                    # veryfast: o mesmo preset para os dois grupos, entao nao cria vies;
                    # "medium" levava minutos por video nesta maquina.
                    video.options = {"crf": str(crf), "preset": "veryfast"}
                    # O MP4 nao aceita trilha nova depois que a gravacao comecou:
                    # a de audio precisa nascer junto com a de video.
                    audio = _criar_trilha_audio(destino) if amostras_audio is not None and amostras_audio.size else None
                # Reduz na propria conversao de cor (swscale, filtro "area"): converter
                # o 4K 10-bit inteiro e depois reduzir custava segundos por quadro.
                pw, ph = (video.height, video.width) if girado else (video.width, video.height)
                bgr = aplicar_rotacao(
                    quadro.to_ndarray(format="bgr24", width=pw, height=ph, interpolation="AREA"), quadro.rotation
                )
                novo = av.VideoFrame.from_ndarray(np.ascontiguousarray(bgr), format="bgr24")
                novo.pts, novo.time_base = indice, Fraction(1, fps)
                for pacote in video.encode(novo):
                    destino.mux(pacote)
                indice += 1
            if video is None:
                raise ValueError(f"Nenhum quadro legível em {entrada.name}")
            for pacote in video.encode():
                destino.mux(pacote)
            if audio is not None:
                _gravar_audio(audio, destino, amostras_audio)
    return saida


TAXA_AUDIO = 44100


def _criar_trilha_audio(destino):
    audio = destino.add_stream("aac", rate=TAXA_AUDIO)
    audio.layout = "mono"
    audio.bit_rate = 96_000
    return audio


def _gravar_audio(audio, destino, amostras, taxa=TAXA_AUDIO):
    import av

    bloco = 1024
    for inicio in range(0, amostras.size, bloco):
        pedaco = amostras[inicio : inicio + bloco]
        if pedaco.size < bloco:
            pedaco = np.pad(pedaco, (0, bloco - pedaco.size))
        quadro = av.AudioFrame.from_ndarray(pedaco[None, :].astype(np.float32), format="fltp", layout="mono")
        quadro.sample_rate, quadro.pts, quadro.time_base = taxa, inicio, Fraction(1, taxa)
        for pacote in audio.encode(quadro):
            destino.mux(pacote)
    for pacote in audio.encode():
        destino.mux(pacote)


def padronizar_pasta(origem, destino, avisar=print, **opcoes):
    """Espelha origem/reais e origem/ia em destino/, padronizando cada video. Pula os já feitos."""
    origem, destino = Path(origem), Path(destino)
    videos = [v for v in sorted(origem.rglob("*")) if v.is_file() and v.suffix.lower() in EXTENSOES_VIDEO]
    falhas = []
    for n, video in enumerate(videos, 1):
        alvo = destino / video.relative_to(origem).with_suffix(".mp4")
        if alvo.is_file():
            continue
        try:
            padronizar_video(video, alvo, **opcoes)
            avisar(f"[{n}/{len(videos)}] {video.name} -> {alvo.relative_to(destino)}")
        except Exception as exc:
            alvo.unlink(missing_ok=True)
            falhas.append((video, exc))
            avisar(f"[{n}/{len(videos)}] {video.name}: falhou ({exc})")
    return falhas


def main(argv=None):
    parser = argparse.ArgumentParser(description="Padroniza vídeos (formato, resolução, duração) para a rodada de controle.")
    parser.add_argument("origem", type=Path)
    parser.add_argument("destino", type=Path)
    parser.add_argument("--lado", type=int, default=LADO)
    parser.add_argument("--crf", type=int, default=CRF)
    parser.add_argument("--max-s", type=float, default=MAX_S)
    args = parser.parse_args(argv)
    falhas = padronizar_pasta(args.origem, args.destino, lado=args.lado, crf=args.crf, max_s=args.max_s)
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
