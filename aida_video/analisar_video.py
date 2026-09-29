"""AIDA Video: pipeline completo de analise de um video.

    video -> frames (etapa 02) -> AIDA Core por frame (etapa 03)
          -> agregacao temporal (etapa 04) -> relatorio
          \\-> trilha de audio -> AIDA Audio ----------------^

Uso:
    python -m aida_video video.mp4                      # usa o Core publico
    python -m aida_video video.mp4 --saida resultado/   # guarda frames, audio.wav e relatorio.json
    python -m aida_video video.mp4 --sem-core           # so extrai frames e analisa o audio
    AIDA_CORE_URL=http://localhost:7860 python -m aida_video video.mp4
"""

from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor
import shutil
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

from .agregacao import INCONCLUSIVO, agregar, combinar, combinar_visual
from .analisadores import AnalisadorCore, CoreIndisponivel
from .extrair_frames import extrair_frames, validar_video

FALHAS_SEGUIDAS_PARA_ABORTAR = 3
RESSALVA = (
    "Indício técnico, não prova. A agregação de frames e o modelo de áudio são linhas de base "
    "ainda em calibração."
)
# Campos do Core que valem a pena guardar por frame; o resto (mapas, metricas
# brutas) incharia o relatorio de um video com centenas de frames.
CAMPOS_CORE = (
    "resultado", "probabilidade_ia", "probabilidade_ia_exibicao", "confianca",
    "fora_de_dominio", "limiar", "motivos", "id_analise",
)


def _um_frame(analisador, caminho):
    """Devolve (campos_do_core, erro, core_indisponivel)."""
    try:
        resposta = analisador.analisar(caminho)
        return {k: resposta.get(k) for k in CAMPOS_CORE if k in resposta}, None, False
    except CoreIndisponivel as exc:
        return {}, str(exc), True
    except Exception as exc:  # um frame ruim nao derruba o video inteiro
        return {}, f"{type(exc).__name__}: {exc}", False


def _analisar_frames(frames, pasta, analisador, progresso, paralelo=1):
    """Analisa em lotes de `paralelo` frames, mantendo a ordem do tempo.

    Em lotes (e nao um pool solto) para a regra de abortar continuar valendo:
    depois de cada lote se sabe quantas falhas seguidas houve.
    """
    paralelo = max(1, int(paralelo))
    resultados = []
    falhas_seguidas = 0
    abortado = None
    executor = ThreadPoolExecutor(max_workers=paralelo) if paralelo > 1 else None
    try:
        for inicio in range(0, len(frames), paralelo):
            lote = frames[inicio : inicio + paralelo]
            if abortado:
                saidas = [({}, f"não analisado: {abortado}", False)] * len(lote)
            elif executor:
                saidas = list(executor.map(lambda f: _um_frame(analisador, pasta / f["arquivo"]), lote))
            else:
                saidas = [_um_frame(analisador, pasta / lote[0]["arquivo"])]
            for frame, (campos, erro, indisponivel) in zip(lote, saidas):
                registro = {"arquivo": frame["arquivo"], "tempo_s": frame["tempo_s"], "motivo_selecao": frame["motivo"]}
                registro.update(campos)
                if erro:
                    registro["erro"] = erro
                if not abortado:
                    falhas_seguidas = falhas_seguidas + 1 if indisponivel else 0
                    if falhas_seguidas >= FALHAS_SEGUIDAS_PARA_ABORTAR:
                        # Sem isso, um Core fora do ar faz o usuario esperar
                        # frames x tentativas x timeout antes de ver o erro.
                        abortado = f"Core indisponível em {FALHAS_SEGUIDAS_PARA_ABORTAR} frames seguidos"
                resultados.append(registro)
                if progresso:
                    progresso(len(resultados), len(frames), registro)
    finally:
        if executor:
            executor.shutdown(wait=True)
    return resultados, abortado


def _analisar_audio(caminho_video, pasta_saida, tem_audio):
    if not tem_audio:
        return {"resultado": None, "presente": False, "motivos": ["o vídeo não tem trilha de áudio"]}
    try:
        from aida_audio.analisar import MAX_SEGUNDOS_ANALISE, analisar_amostras
        from aida_audio.carregar import carregar_audio, salvar_wav

        amostras, taxa = carregar_audio(caminho_video, max_segundos=MAX_SEGUNDOS_ANALISE)
        if pasta_saida is not None:
            salvar_wav(pasta_saida / "audio.wav", amostras, taxa)
        resposta = analisar_amostras(amostras, taxa)
        resposta.pop("caracteristicas", None)
        resposta["presente"] = True
        if pasta_saida is not None:
            resposta["arquivo_wav"] = "audio.wav"
        return resposta
    except Exception as exc:
        return {"resultado": None, "presente": True, "erro": f"{type(exc).__name__}: {exc}", "motivos": []}


def analisar_video(
    caminho_video,
    analisador=None,
    pasta_saida=None,
    analisar_frames=True,
    com_audio=True,
    parametros_extracao=None,
    regras=None,
    progresso=None,
    paralelo=1,
    com_trajetoria=True,
):
    """Analisa um video e devolve o relatorio (dict).

    analisador: objeto com .analisar(caminho_png). None usa o AIDA Core (AIDA_CORE_URL).
    pasta_saida: se dada, guarda frames, manifesto.json, audio.wav e relatorio.json.
                 Se None, trabalha numa pasta temporaria apagada no fim.
    com_trajetoria: analisa o movimento entre frames (DINOv2) e o junta ao voto
                 dos frames. Precisa de torch + timm; sem eles o video segue so
                 com os frames e o relatorio diz por que.
    """
    inicio = time.perf_counter()
    caminho_video = validar_video(caminho_video)
    temporaria = pasta_saida is None
    pasta = Path(tempfile.mkdtemp(prefix="aida_video_")) if temporaria else Path(pasta_saida)

    try:
        manifesto = extrair_frames(caminho_video, pasta, **(parametros_extracao or {}))
        metadados = manifesto["metadados"]

        abortado = None
        if analisar_frames:
            analisador = analisador or AnalisadorCore()
            frames, abortado = _analisar_frames(manifesto["frames"], pasta, analisador, progresso, paralelo)
            visual = agregar(frames, regras)
            if abortado:
                visual["motivos"].insert(0, abortado)
        else:
            frames = [
                {"arquivo": f["arquivo"], "tempo_s": f["tempo_s"], "motivo_selecao": f["motivo"]}
                for f in manifesto["frames"]
            ]
            visual = {
                "resultado": INCONCLUSIVO,
                "inconclusivo": True,
                "motivos": ["análise dos frames desativada (--sem-core)"],
                "frames_total": len(frames),
            }

        trajetoria = None
        if com_trajetoria:
            from .trajetoria import analisar_trajetoria

            estat = visual.get("probabilidade_ia") if analisar_frames else None
            trajetoria = analisar_trajetoria(caminho_video, prob_core=(estat or {}).get("mediana"))
            visual = combinar_visual(visual, trajetoria, regras)

        audio = _analisar_audio(caminho_video, None if temporaria else pasta, com_audio and metadados["tem_audio"])
        if not com_audio and metadados["tem_audio"]:
            audio = {"resultado": None, "presente": True, "motivos": ["análise de áudio desativada"]}

        conclusao = combinar(visual, audio, regras)
        ponderada = None
        if analisar_frames and regras is None:
            from .fusao import carregar_modelo, combinar_ponderado

            ponderada = combinar_ponderado(frames, trajetoria, audio, carregar_modelo())
        if ponderada:
            # Os motivos das regras continuam como evidência (frames, movimento, áudio).
            ponderada["motivos"] += [m for m in conclusao["motivos"] if m not in ponderada["motivos"]]
            ponderada["resultado_regras"] = conclusao["resultado"]
            conclusao = ponderada
        relatorio = {
            "video": caminho_video.name,
            "data_hora": datetime.now().isoformat(timespec="seconds"),
            "duracao_processamento_s": round(time.perf_counter() - inicio, 2),
            **conclusao,
            "visual": visual,
            "trajetoria": trajetoria,
            "audio": audio,
            "metadados": metadados,
            "parametros_extracao": manifesto["parametros"],
            "frames": frames,
            "ressalva": RESSALVA,
        }
        if not temporaria:
            with open(pasta / "relatorio.json", "w", encoding="utf-8") as arquivo:
                json.dump(relatorio, arquivo, ensure_ascii=False, indent=2)
        return relatorio
    finally:
        if temporaria:
            shutil.rmtree(pasta, ignore_errors=True)


def _imprimir_resumo(relatorio):
    meta = relatorio["metadados"]
    visual, audio = relatorio["visual"], relatorio["audio"]
    print(f"\nVideo: {relatorio['video']} | {meta['largura']}x{meta['altura']} | {meta['fps']} fps | {meta['duracao_s']} s")
    print(f"RESULTADO: {relatorio['resultado']}")
    for motivo in relatorio["motivos"]:
        print(f"  - {motivo}")
    if "contagem" in visual:
        c = visual["contagem"]
        print(
            f"Imagem: {visual['resultado']} | {visual['frames_validos']} frames validos "
            f"(REAL {c['REAL']}, IA {c['IA/MANIPULADA']}, inconclusivo {c['INCONCLUSIVO']}; "
            f"erro {visual['frames_com_erro']}, fora de dominio {visual['frames_fora_de_dominio']})"
        )
        for t in visual["trechos_ia"]:
            print(f"  trecho IA: {t['inicio_s']:.1f}s - {t['fim_s']:.1f}s ({t['frames']} frames)")
    else:
        print(f"Imagem: {visual['resultado']} ({'; '.join(visual['motivos'])})")
    traj = relatorio.get("trajetoria")
    if traj:
        if traj.get("disponivel"):
            print(f"Movimento: {traj['resultado']} | prob. IA {traj['probabilidade_ia']:.2f}"
                  + (" (com o Core)" if traj.get("usa_core") else ""))
        else:
            print(f"Movimento: nao avaliado ({'; '.join(traj.get('motivos') or [])})")
    if audio.get("erro"):
        print(f"Audio: erro - {audio['erro']}")
    else:
        prob = audio.get("probabilidade_ia")
        extra = f" | prob. IA {prob:.2f}" if isinstance(prob, float) else ""
        print(f"Audio: {audio.get('resultado') or 'nao avaliado'}{extra} ({'; '.join(audio.get('motivos') or []) or 'ok'})")
    print(f"\n{relatorio['ressalva']}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Analisa um video com o AIDA (frames + audio).")
    parser.add_argument("video", type=Path)
    parser.add_argument("--saida", type=Path, default=None, help="pasta para frames, audio.wav e relatorio.json")
    parser.add_argument("--core-url", default=None, help="URL do AIDA Core (padrao: AIDA_CORE_URL ou o Space publico)")
    parser.add_argument("--timeout", type=float, default=180.0, help="timeout por frame, em segundos")
    parser.add_argument("--intervalo", type=float, default=1.0, help="segundos entre frames")
    parser.add_argument("--max-frames", type=int, default=60)
    parser.add_argument("--paralelo", type=int, default=2, help="frames enviados ao Core ao mesmo tempo")
    parser.add_argument("--sem-core", action="store_true", help="nao envia frames ao Core")
    parser.add_argument("--sem-audio", action="store_true")
    parser.add_argument("--sem-trajetoria", action="store_true", help="nao analisa o movimento (DINOv2)")
    parser.add_argument("--json", action="store_true", help="imprime o relatorio completo em JSON")
    args = parser.parse_args(argv)

    def progresso(i, total, registro):
        estado = registro.get("erro") or registro.get("resultado")
        print(f"[{i}/{total}] {registro['tempo_s']:7.2f}s  {estado}", file=sys.stderr)

    try:
        relatorio = analisar_video(
            args.video,
            analisador=None if args.sem_core else AnalisadorCore(args.core_url, timeout_s=args.timeout),
            pasta_saida=args.saida,
            analisar_frames=not args.sem_core,
            com_audio=not args.sem_audio,
            parametros_extracao={"intervalo_s": args.intervalo, "max_frames": args.max_frames},
            progresso=progresso,
            paralelo=args.paralelo,
            com_trajetoria=not args.sem_trajetoria,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(relatorio, indent=2, ensure_ascii=False))
    else:
        _imprimir_resumo(relatorio)
        if args.saida:
            print(f"Relatorio completo: {args.saida / 'relatorio.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
