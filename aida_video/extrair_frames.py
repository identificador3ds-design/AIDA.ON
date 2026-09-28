"""AIDA Video - Etapa 02: extracao de frames.

Separa um video em frames para serem analisados pelo AIDA Core como imagens.
Nao salva todos os quadros: um video de 1 min a 30 fps tem 1800 frames quase
iguais. A selecao combina tres regras:

1. intervalo  - no maximo um frame a cada N segundos (cobertura uniforme);
2. corte      - sempre pega o primeiro frame depois de um corte de cena,
                detectado pela distancia entre histogramas HSV;
3. duplicata  - descarta frames cuja miniatura em cinza e quase igual a do
                ultimo frame salvo (diferenca media absoluta pequena).

Os frames sao salvos em PNG (sem perda). Salvar em JPEG recomprimiria o
quadro e alteraria justamente os sinais de frequencia e ruido que o AIDA mede.

A leitura usa PyAV (FFmpeg embutido na roda do pip) em vez do cv2.VideoCapture:
- o tempo de cada frame vem do PTS do container, exato mesmo em taxa variavel;
- a rotacao gravada por celulares (video "em pe") e aplicada;
- caminhos com acento funcionam no Windows (o cv2 falha neles);
- o mesmo pacote extrai o audio (aida_audio.carregar).

Uso:
    python -m aida_video.extrair_frames video.mp4
    python -m aida_video.extrair_frames video.mp4 --saida frames --intervalo 0.5 --max-frames 120
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import cv2
import numpy as np

from aida_audio.carregar import descrever_erro_ffmpeg

EXTENSOES_VIDEO = {".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi", ".3gp", ".mpg", ".mpeg", ".wmv", ".flv"}
# Video de celular passa facil de 1 GB. O tamanho quase nao pesa no custo:
# a extracao para em max_frames e o audio le no maximo 120 s.
LARGURA_VARREDURA, ALTURA_VARREDURA = 320, 180
TAMANHO_MAX_MB = int(os.environ.get("AIDA_VIDEO_MAX_MB", "2048"))


def validar_video(caminho, tamanho_max_mb=TAMANHO_MAX_MB):
    caminho = Path(caminho)
    if not caminho.is_file():
        raise FileNotFoundError(f"Vídeo não encontrado: {caminho}")
    if caminho.suffix.lower() not in EXTENSOES_VIDEO:
        raise ValueError(
            f"Extensão '{caminho.suffix}' não suportada. Use: {', '.join(sorted(EXTENSOES_VIDEO))}"
        )
    tamanho = caminho.stat().st_size
    if tamanho == 0:
        raise ValueError(f"Arquivo vazio: {caminho.name}")
    if tamanho > tamanho_max_mb * 1024 * 1024:
        raise ValueError(f"O vídeo passa do limite de {tamanho_max_mb} MB.")
    return caminho


def _fracao(valor):
    try:
        return float(valor) if valor else 0.0
    except (TypeError, ZeroDivisionError):
        return 0.0


def ler_metadados(container, trilha):
    fps = _fracao(trilha.average_rate) or _fracao(trilha.guessed_rate)
    duracao = None
    if trilha.duration and trilha.time_base:
        duracao = float(trilha.duration * trilha.time_base)
    elif container.duration:
        duracao = container.duration / 1_000_000  # av.time_base e microssegundo
    contexto = trilha.codec_context
    return {
        "fps": round(fps, 3),
        "total_frames_declarado": int(trilha.frames or 0),
        "duracao_s": round(duracao, 3) if duracao else None,
        "largura": int(contexto.width or 0),
        "altura": int(contexto.height or 0),
        "codec": contexto.name,
        "formato_container": container.format.name,
        "tem_audio": bool(container.streams.audio),
    }


def aplicar_rotacao(frame_bgr, rotacao_graus):
    """Gira o quadro como um player giraria.

    `rotacao_graus` e o angulo anti-horario da matriz de exibicao (convencao do
    PyAV/FFmpeg). Celular filmando em pe grava -90: o quadro precisa girar 90
    no sentido horario. np.rot90(k) gira 90*k no sentido anti-horario.
    """
    k = int(round((rotacao_graus or 0) / 90.0)) % 4
    return np.ascontiguousarray(np.rot90(frame_bgr, k)) if k else frame_bgr


def histograma_hsv(frame):
    # Reduz antes de calcular: o corte de cena e um fenomeno global,
    # nao precisa de resolucao cheia.
    pequeno = cv2.resize(frame, (160, 90), interpolation=cv2.INTER_AREA)
    hsv = cv2.cvtColor(pequeno, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1], None, [32, 32], [0, 180, 0, 256])
    return cv2.normalize(hist, hist).flatten()


def miniatura(frame):
    # Um hash de 64 bits (dHash) se mostrou grosso demais: objeto pequeno se
    # movendo em fundo liso muda poucos bits e o frame era descartado.
    # A diferenca media numa miniatura 64x36 pega esse movimento e ainda
    # ignora o ruido de compressao de uma cena parada.
    cinza = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return cv2.resize(cinza, (64, 36), interpolation=cv2.INTER_AREA).astype(np.float32)


def salvar_png(caminho, frame_bgr):
    # cv2.imwrite nao aceita caminho com acento no Windows; imencode + write_bytes aceita.
    ok, dados = cv2.imencode(".png", frame_bgr)
    if not ok:
        raise ValueError(f"Falha ao codificar PNG: {caminho}")
    Path(caminho).write_bytes(dados.tobytes())


def extrair_frames(
    caminho_video,
    pasta_saida,
    intervalo_s=1.0,
    limiar_corte=0.5,
    limiar_duplicata=2.0,
    varreduras_por_s=5.0,
    max_frames=300,
    tamanho_max_mb=TAMANHO_MAX_MB,
):
    import av

    if intervalo_s <= 0:
        raise ValueError("intervalo_s precisa ser maior que zero.")
    if max_frames < 1:
        raise ValueError("max_frames precisa ser pelo menos 1.")
    caminho_video = validar_video(caminho_video, tamanho_max_mb)

    try:
        container = av.open(str(caminho_video))
    except av.FFmpegError as exc:
        raise ValueError(f"Não foi possível abrir '{caminho_video.name}' como vídeo: {descrever_erro_ffmpeg(exc)}") from exc

    pasta_saida = Path(pasta_saida)
    pasta_saida.mkdir(parents=True, exist_ok=True)
    selecionados = []
    indice = -1
    erro_decodificacao = None

    with container:
        if not container.streams.video:
            raise ValueError(f"'{caminho_video.name}' não tem trilha de vídeo.")
        trilha = container.streams.video[0]
        trilha.thread_type = "AUTO"
        # Pula quadros que nenhum outro usa como referencia (B nao-referencia do
        # HEVC do iPhone). A varredura olha 5 quadros/s de qualquer forma, e
        # decodificar 4K HEVC 10-bit numa CPU de 2 nucleos anda a ~2 quadros/s.
        trilha.codec_context.skip_frame = "NONREF"
        metadados = ler_metadados(container, trilha)
        fps = metadados["fps"] or 30.0
        # Nao precisamos olhar todos os quadros para achar cortes: 5 por segundo
        # bastam. Os demais sao decodificados, mas nao convertidos para BGR.
        passo = max(1, round(fps / varreduras_por_s))

        hist_anterior = None
        ultimo_tempo_salvo = None
        ultima_miniatura = None
        tempo_anterior = -1.0

        try:
            for quadro in container.decode(trilha):
                indice += 1
                if indice % passo:
                    continue

                # Tempo pelo PTS do container, e nao indice/fps: em video de taxa
                # variavel (comum em celular) indice/fps desalinha com o audio.
                tempo_s = quadro.time
                if tempo_s is None or tempo_s < tempo_anterior:
                    tempo_s = indice / fps
                tempo_s = max(float(tempo_s), 0.0)
                tempo_anterior = tempo_s

                # Corte de cena e duplicata so precisam de uma versao pequena, que o
                # swscale gera direto na conversao de cor. Converter o quadro 4K
                # 10-bit inteiro custa ~2,7 s; fica so para os frames que sao salvos.
                pequeno = aplicar_rotacao(
                    quadro.to_ndarray(format="bgr24", width=LARGURA_VARREDURA, height=ALTURA_VARREDURA),
                    quadro.rotation,
                )

                hist = histograma_hsv(pequeno)
                distancia_cena = (
                    cv2.compareHist(hist_anterior, hist, cv2.HISTCMP_BHATTACHARYYA)
                    if hist_anterior is not None
                    else 1.0
                )
                hist_anterior = hist

                if ultimo_tempo_salvo is None:
                    motivo = "primeiro"
                elif distancia_cena >= limiar_corte:
                    motivo = "corte_de_cena"
                elif tempo_s - ultimo_tempo_salvo >= intervalo_s:
                    motivo = "intervalo"
                else:
                    continue

                mini = miniatura(pequeno)
                diferenca = (
                    float(np.mean(np.abs(mini - ultima_miniatura)))
                    if ultima_miniatura is not None
                    else 255.0
                )
                if motivo == "intervalo" and diferenca < limiar_duplicata:
                    # Cena parada: avanca o relogio para nao testar de novo a cada varredura.
                    ultimo_tempo_salvo = tempo_s
                    continue

                nome = f"frame_{len(selecionados):04d}_{tempo_s:09.3f}s.png"
                frame = aplicar_rotacao(quadro.to_ndarray(format="bgr24"), quadro.rotation)
                salvar_png(pasta_saida / nome, frame)
                selecionados.append(
                    {
                        "arquivo": nome,
                        "indice_frame": indice,
                        "tempo_s": round(tempo_s, 3),
                        "motivo": motivo,
                        "distancia_cena": round(float(distancia_cena), 4),
                        "diferenca_ultimo": round(diferenca, 2),
                    }
                )
                ultimo_tempo_salvo = tempo_s
                ultima_miniatura = mini
                if len(selecionados) >= max_frames:
                    break
        except av.FFmpegError as exc:
            # Arquivo truncado (download interrompido): fica com o que foi lido.
            erro_decodificacao = descrever_erro_ffmpeg(exc)

    if not selecionados:
        detalhe = f" ({erro_decodificacao})" if erro_decodificacao else ""
        raise ValueError(f"Nenhum frame legível em '{caminho_video.name}'{detalhe}.")

    metadados["frames_lidos"] = indice + 1
    metadados["erro_decodificacao"] = erro_decodificacao
    # Depois da rotacao a largura/altura exibidas podem ter trocado.
    altura, largura = frame.shape[:2]
    metadados["largura_exibida"], metadados["altura_exibida"] = int(largura), int(altura)

    manifesto = {
        "video": str(caminho_video),
        "metadados": metadados,
        "parametros": {
            "intervalo_s": intervalo_s,
            "limiar_corte": limiar_corte,
            "limiar_duplicata": limiar_duplicata,
            "varreduras_por_s": varreduras_por_s,
            "max_frames": max_frames,
        },
        "frames": selecionados,
    }
    with open(pasta_saida / "manifesto.json", "w", encoding="utf-8") as arquivo:
        json.dump(manifesto, arquivo, ensure_ascii=False, indent=2)
    return manifesto


def main():
    parser = argparse.ArgumentParser(description="Extrai frames representativos de um video.")
    parser.add_argument("video", type=Path)
    parser.add_argument("--saida", type=Path, default=None, help="pasta de saida (padrao: <video>_frames)")
    parser.add_argument("--intervalo", type=float, default=1.0, help="segundos entre frames por intervalo")
    parser.add_argument("--limiar-corte", type=float, default=0.5, help="distancia Bhattacharyya para corte (0-1)")
    parser.add_argument("--limiar-duplicata", type=float, default=2.0, help="diferenca media minima (0-255) para nao ser duplicata")
    parser.add_argument("--max-frames", type=int, default=300)
    args = parser.parse_args()

    saida = args.saida or args.video.with_name(f"{args.video.stem}_frames")
    manifesto = extrair_frames(
        args.video,
        saida,
        intervalo_s=args.intervalo,
        limiar_corte=args.limiar_corte,
        limiar_duplicata=args.limiar_duplicata,
        max_frames=args.max_frames,
    )
    meta = manifesto["metadados"]
    print(f"Video: {meta['largura']}x{meta['altura']} | {meta['fps']} fps | {meta['duracao_s']} s | codec {meta['codec']}")
    contagem = {}
    for frame in manifesto["frames"]:
        contagem[frame["motivo"]] = contagem.get(frame["motivo"], 0) + 1
    print(f"{len(manifesto['frames'])} frames salvos de {meta['frames_lidos']} lidos -> {saida}")
    print("Por motivo:", contagem)


if __name__ == "__main__":
    main()
