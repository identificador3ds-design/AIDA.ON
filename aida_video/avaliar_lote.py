"""AIDA Video: avaliacao em lote e calibracao das regras de agregacao.

Passos 1 e 2 da pesquisa (docs/pesquisa-aida-video-audio.md): rodar um conjunto
de videos ROTULADOS pelo pipeline e medir

- quantos videos o AIDA acerta, erra ou deixa inconclusivos;
- quao bem o Core separa frames reais de frames IA (AUC por frame);
- quais regras de agregacao funcionam melhor neste conjunto.

Estrutura de entrada (o nome da pasta e o rotulo):

    videos_teste/
        reais/   IMG_2195.MOV, ...
        ia/      sora_01.mp4, ...

Uso:
    python -m aida_video.avaliar_lote videos_teste/ --saida resultados_videos/
    python -m aida_video.avaliar_lote videos_teste/ --saida resultados_videos/ --so-calibrar

O relatorio de cada video fica em <saida>/relatorios/<rotulo>__<video>.json. Uma
segunda execucao PULA os videos ja analisados (o lote pode ser interrompido e
retomado), e --so-calibrar refaz as metricas e a busca de regras so a partir
desses JSON, sem chamar o Core.
"""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import sys
import time
from pathlib import Path

from .agregacao import IA, INCONCLUSIVO, REAL, REGRAS_PADRAO, agregar, combinar
from .analisadores import AnalisadorCore
from .analisar_video import analisar_video
from .extrair_frames import EXTENSOES_VIDEO

ROTULOS = {"reais": REAL, "ia": IA}
# Grade de regras testada na calibracao. Pequena de proposito: com 20 videos,
# uma busca grande so encontraria a combinacao que decora este conjunto.
GRADE_REGRAS = {
    "fracao_ia": [0.3, 0.4, 0.5],
    "fracao_real": [0.6, 0.7, 0.8],
    "sequencia_minima": [2, 3, 4],
    "fracao_trecho": [0.1, 0.15, 0.25],
}


def listar_videos(pasta):
    pasta = Path(pasta)
    itens = []
    for nome_pasta, rotulo in ROTULOS.items():
        raiz = pasta / nome_pasta
        if raiz.is_dir():
            itens += [
                (v, rotulo, nome_pasta)
                for v in sorted(raiz.rglob("*"))
                if v.is_file() and v.suffix.lower() in EXTENSOES_VIDEO
            ]
    if not itens:
        raise FileNotFoundError(
            f"Nenhum vídeo em {pasta / 'reais'} nem em {pasta / 'ia'}. "
            "Coloque os vídeos nessas subpastas: o nome da pasta é o rótulo."
        )
    return itens


def _arquivo_relatorio(saida, nome_pasta, video):
    return Path(saida) / "relatorios" / f"{nome_pasta}__{video.stem}{video.suffix.lower().replace('.', '_')}.json"


def analisar_lote(pasta, saida, analisador=None, parametros_extracao=None, paralelo=2, avisar=print):
    """Roda cada video ainda nao analisado e grava o relatorio (sem os PNG dos frames)."""
    itens = listar_videos(pasta)
    analisador = analisador or AnalisadorCore()
    (Path(saida) / "relatorios").mkdir(parents=True, exist_ok=True)
    for n, (video, rotulo, nome_pasta) in enumerate(itens, 1):
        destino = _arquivo_relatorio(saida, nome_pasta, video)
        if destino.is_file():
            avisar(f"[{n}/{len(itens)}] {video.name}: já analisado, pulando")
            continue
        avisar(f"[{n}/{len(itens)}] {video.name} ({nome_pasta}) ...")
        inicio = time.perf_counter()
        try:
            relatorio = analisar_video(
                video,
                analisador=analisador,
                parametros_extracao=parametros_extracao,
                paralelo=paralelo,
            )
        except (FileNotFoundError, ValueError) as exc:
            relatorio = {"video": video.name, "erro": str(exc)}
            avisar(f"    erro: {exc}")
        relatorio["rotulo"] = rotulo
        relatorio["pasta"] = nome_pasta
        destino.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8")
        if "erro" not in relatorio:
            avisar(f"    {relatorio['resultado']} em {time.perf_counter() - inicio:.0f} s")
    return itens


def carregar_relatorios(saida):
    relatorios = []
    for arquivo in sorted((Path(saida) / "relatorios").glob("*.json")):
        relatorios.append(json.loads(arquivo.read_text(encoding="utf-8")))
    return relatorios


def _auc(rotulos, scores):
    """AUC pela estatistica de Mann-Whitney (sem depender do sklearn).

    Por postos medios, O(n log n): a comparacao par a par era O(n^2) e, com ~3000
    frames, dominava o tempo da `calibrar` (que chama `metricas` 81 vezes)."""
    pares = sorted(zip(scores, rotulos))
    n_pos = sum(1 for _, r in pares if r == 1)
    n_neg = sum(1 for _, r in pares if r == 0)
    if not n_pos or not n_neg:
        return None
    soma_postos_pos, i = 0.0, 0
    while i < len(pares):
        j = i
        while j < len(pares) and pares[j][0] == pares[i][0]:
            j += 1
        posto_medio = (i + 1 + j) / 2  # postos i+1..j empatados
        soma_postos_pos += posto_medio * sum(1 for _, r in pares[i:j] if r == 1)
        i = j
    return (soma_postos_pos - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)


def metricas(relatorios, regras=None):
    """Matriz de confusao por video (reagregando os frames com `regras`) e AUC por frame."""
    matriz = {r: {IA: 0, REAL: 0, INCONCLUSIVO: 0} for r in (REAL, IA)}
    linhas = []
    for rel in relatorios:
        if "erro" in rel:
            continue
        visual = agregar(rel["frames"], regras) if regras else rel["visual"]
        previsto = combinar(visual, rel.get("audio"))["resultado"]
        matriz[rel["rotulo"]][previsto] += 1
        linhas.append((rel, visual, previsto))

    decididos = sum(matriz[r][p] for r in matriz for p in (IA, REAL))
    acertos = matriz[REAL][REAL] + matriz[IA][IA]
    total = sum(sum(v.values()) for v in matriz.values())

    rotulos_frames, scores_frames = [], []
    for rel in relatorios:
        for f in rel.get("frames", []):
            if f.get("erro") or f.get("fora_de_dominio") or not isinstance(f.get("probabilidade_ia"), (int, float)):
                continue
            rotulos_frames.append(1 if rel["rotulo"] == IA else 0)
            scores_frames.append(f["probabilidade_ia"])

    auc = _auc(rotulos_frames, scores_frames)
    return {
        "videos": total,
        "matriz": matriz,
        "acuracia_decididos": round(acertos / decididos, 4) if decididos else None,
        "cobertura": round(decididos / total, 4) if total else None,
        "acertos_sobre_total": round(acertos / total, 4) if total else None,
        "falsos_positivos": matriz[REAL][IA],  # real acusado de IA: o erro mais caro
        "frames_avaliados": len(scores_frames),
        "auc_frames": round(auc, 4) if auc is not None else None,
        "linhas": linhas,
    }


def calibrar(relatorios):
    """Testa a grade de regras e ordena: menos falsos positivos, mais acertos, mais cobertura."""
    chaves = list(GRADE_REGRAS)
    resultados = []
    for valores in itertools.product(*(GRADE_REGRAS[c] for c in chaves)):
        regras = {**REGRAS_PADRAO, **dict(zip(chaves, valores))}
        m = metricas(relatorios, regras)
        resultados.append({"regras": regras, **{k: v for k, v in m.items() if k != "linhas"}})
    resultados.sort(key=lambda r: (r["falsos_positivos"], -(r["acertos_sobre_total"] or 0), -(r["cobertura"] or 0)))
    return resultados


def gravar_csvs(relatorios, saida, regras=None):
    """regras=None usa o resultado gravado no relatorio (regras de quando foi analisado).
    Dado, reagrega cada video com essas regras antes de escrever o CSV — sem chamar o Core de novo."""
    saida = Path(saida)
    with open(saida / "resumo_videos.csv", "w", newline="", encoding="utf-8-sig") as arq:
        w = csv.writer(arq, delimiter=";")
        w.writerow([
            "video", "rotulo", "resultado", "acertou", "frames_validos", "frames_real", "frames_ia",
            "frames_inconclusivos", "fora_de_dominio", "erros", "prob_ia_mediana", "prob_ia_max",
            "maior_trecho_ia", "audio", "resolucao", "codec", "duracao_s", "tempo_processamento_s", "erro",
        ])
        for rel in relatorios:
            if "erro" in rel:
                w.writerow([rel["video"], rel["rotulo"]] + [""] * 16 + [rel["erro"]])
                continue
            v = agregar(rel["frames"], regras) if regras else rel["visual"]
            resultado = combinar(v, rel.get("audio"))["resultado"] if regras else rel["resultado"]
            meta = rel["metadados"]
            probs = v.get("probabilidade_ia") or {}
            w.writerow([
                rel["video"], rel["rotulo"], resultado,
                "" if resultado == INCONCLUSIVO else int(resultado == rel["rotulo"]),
                v.get("frames_validos"), v["contagem"][REAL], v["contagem"][IA], v["contagem"][INCONCLUSIVO],
                v.get("frames_fora_de_dominio"), v.get("frames_com_erro"),
                probs.get("mediana"), probs.get("maxima"),
                max((t["frames"] for t in v.get("trechos_ia", [])), default=0),
                (rel.get("audio") or {}).get("resultado"),
                f"{meta.get('largura_exibida')}x{meta.get('altura_exibida')}", meta.get("codec"),
                meta.get("duracao_s"), rel.get("duracao_processamento_s"), "",
            ])
    with open(saida / "frames.csv", "w", newline="", encoding="utf-8-sig") as arq:
        w = csv.writer(arq, delimiter=";")
        w.writerow(["video", "rotulo", "tempo_s", "resultado", "probabilidade_ia", "fora_de_dominio", "erro"])
        for rel in relatorios:
            for f in rel.get("frames", []):
                w.writerow([
                    rel["video"], rel["rotulo"], f.get("tempo_s"), f.get("resultado"),
                    f.get("probabilidade_ia"), f.get("fora_de_dominio"), f.get("erro", ""),
                ])


def _imprimir_metricas(titulo, m):
    print(f"\n== {titulo} ==")
    print(f"{m['videos']} vídeos | acurácia nos decididos: {m['acuracia_decididos']} | "
          f"cobertura (não inconclusivos): {m['cobertura']} | falsos positivos: {m['falsos_positivos']}")
    print(f"AUC por frame (probabilidade_ia do Core): {m['auc_frames']} em {m['frames_avaliados']} frames")
    print("                 previsto REAL   previsto IA   inconclusivo")
    for rotulo in (REAL, IA):
        c = m["matriz"][rotulo]
        print(f"  rótulo {rotulo:<14}{c[REAL]:>8}{c[IA]:>14}{c[INCONCLUSIVO]:>15}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Avalia um lote de vídeos rotulados e calibra a agregação.")
    parser.add_argument("pasta", type=Path, help="pasta com subpastas reais/ e ia/")
    parser.add_argument("--saida", type=Path, required=True)
    parser.add_argument("--intervalo", type=float, default=1.0)
    parser.add_argument("--max-frames", type=int, default=40)
    parser.add_argument("--paralelo", type=int, default=2)
    parser.add_argument("--core-url", default=None)
    parser.add_argument("--so-calibrar", action="store_true", help="não analisa nada; só relê os relatórios")
    parser.add_argument(
        "--regras", type=str, default=None,
        help='JSON com as regras de agregação a usar (ex.: \'{"fracao_ia":0.4,"sequencia_minima":4}\'); '
        "sobrescreve REGRAS_PADRAO só nesta execução, sem precisar chamar o Core de novo.",
    )
    args = parser.parse_args(argv)
    regras = {**REGRAS_PADRAO, **json.loads(args.regras)} if args.regras else None

    if not args.so_calibrar:
        try:
            analisar_lote(
                args.pasta, args.saida, AnalisadorCore(args.core_url),
                {"intervalo_s": args.intervalo, "max_frames": args.max_frames}, args.paralelo,
            )
        except FileNotFoundError as exc:
            print(f"Erro: {exc}", file=sys.stderr)
            return 2

    relatorios = carregar_relatorios(args.saida)
    if not relatorios:
        print("Nenhum relatório encontrado.", file=sys.stderr)
        return 2
    gravar_csvs(relatorios, args.saida, regras)
    atual = metricas(relatorios, regras)
    _imprimir_metricas("Regras atuais" if not regras else "Regras informadas (--regras)", atual)

    ranking = calibrar(relatorios)
    (args.saida / "calibracao.json").write_text(json.dumps(ranking, ensure_ascii=False, indent=2), encoding="utf-8")
    melhor = ranking[0]
    print("\n== Melhor combinação da grade (menos falsos positivos, depois mais acertos) ==")
    print({k: melhor["regras"][k] for k in GRADE_REGRAS})
    print(f"acurácia nos decididos {melhor['acuracia_decididos']} | cobertura {melhor['cobertura']} | "
          f"falsos positivos {melhor['falsos_positivos']}")
    print("\nCom poucos vídeos, trate a melhor combinação como indício: confirme num conjunto separado.")
    print(f"Arquivos: {args.saida / 'resumo_videos.csv'}, {args.saida / 'frames.csv'}, {args.saida / 'calibracao.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
