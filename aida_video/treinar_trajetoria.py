"""Treina e avalia o modulo de trajetoria (aida_video/trajetoria.py).

Tres etapas, todas retomaveis:

1. extrair: 21 caracteristicas por janela de cada video, em cache JSON
   (<saida>/trajetoria/<pasta>__<video>.json). Rodar de novo pula o que ja existe.
2. avaliar: validacao cruzada deixando UM gerador IA de fora por vez (e uma
   fatia dos reais), igual a `aida_video.validacao`. Mede tambem os atalhos:
   quanto o fps sozinho separa as classes, e como o modelo vai so em 24/30 fps,
   onde as duas classes coexistem. Se houver relatorios do Core para os mesmos
   videos (--relatorios-core), mede a fusao trajetoria + Core.
3. treinar: ajusta o modelo final em tudo e grava aida_video/modelos/trajetoria.joblib.

Uso (na pasta AIDA.ON):
    python -m aida_video.treinar_trajetoria ../videos_teste_padronizado --saida ../resultados_videos/trajetoria_padronizados \
        --relatorios-core ../resultados_videos/padronizados
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

import numpy as np

from .agregacao import IA, REAL
from .avaliar_lote import _auc, carregar_relatorios, listar_videos
from .trajetoria import ARQUIVO_MODELO as MODELO_PADRAO, NOMES_CARACTERISTICAS, CodificadorDino, caracteristicas_video
from .validacao import GERADOR_REAL, bootstrap, gerador_de

LIMIAR = 0.5


def _arquivo_cache(saida, nome_pasta, video):
    return Path(saida) / "trajetoria" / f"{nome_pasta}__{video.stem}{video.suffix.lower().replace('.', '_')}.json"


def extrair(pasta, saida, codificador=None, max_janelas=1, avisar=print):
    itens = listar_videos(pasta)
    (Path(saida) / "trajetoria").mkdir(parents=True, exist_ok=True)
    for n, (video, rotulo, nome_pasta) in enumerate(itens, 1):
        destino = _arquivo_cache(saida, nome_pasta, video)
        if destino.is_file():
            continue
        codificador = codificador or CodificadorDino()
        inicio = time.perf_counter()
        try:
            linhas, info = caracteristicas_video(video, codificador, max_janelas=max_janelas)
            registro = {"video": video.name, "rotulo": rotulo, "pasta": nome_pasta, "info": info,
                        "janelas": linhas.tolist()}
        except Exception as exc:  # video corrompido nao pode derrubar um lote de horas
            registro = {"video": video.name, "rotulo": rotulo, "pasta": nome_pasta, "erro": str(exc)}
        destino.write_text(json.dumps(registro, ensure_ascii=False), encoding="utf-8")
        avisar(f"[{n}/{len(itens)}] {video.name}: {len(registro.get('janelas', []))} janela(s) "
               f"em {time.perf_counter() - inicio:.0f} s" + (f" — erro: {registro['erro']}" if "erro" in registro else ""))


def carregar_cache(saida):
    registros = []
    for arquivo in sorted((Path(saida) / "trajetoria").glob("*.json")):
        r = json.loads(arquivo.read_text(encoding="utf-8"))
        if "erro" not in r and r.get("janelas"):
            registros.append(r)
    return registros


def novo_classificador():
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    return make_pipeline(StandardScaler(), LogisticRegression(C=0.3, max_iter=2000, class_weight="balanced"))


def _xy(registros):
    X, y, grupo = [], [], []
    for i, r in enumerate(registros):
        for linha in r["janelas"]:
            X.append(linha)
            y.append(int(r["rotulo"] == IA))
            grupo.append(i)
    return np.array(X), np.array(y), np.array(grupo)


def prob_por_video(modelo, registros):
    """Probabilidade de IA de cada video: media das janelas."""
    return np.array([float(modelo.predict_proba(np.array(r["janelas"]))[:, 1].mean()) for r in registros])


def dobras_por_gerador(registros, semente=0):
    geradores = sorted({gerador_de(r) for r in registros} - {GERADOR_REAL})
    reais = [i for i, r in enumerate(registros) if r["rotulo"] == REAL]
    random.Random(semente).shuffle(reais)
    fatia = {i: k % len(geradores) for k, i in enumerate(reais)}
    for k, g in enumerate(geradores):
        fora = [i for i, r in enumerate(registros) if gerador_de(r) == g or fatia.get(i) == k]
        yield g, fora


def fora_da_amostra(registros, extra=None, semente=0):
    """Probabilidade de cada video prevista por um modelo que nao viu o gerador dele.

    `extra`: dict indice->lista de colunas somadas a cada janela (ex.: prob do Core)."""
    probs = np.full(len(registros), np.nan)
    for _, fora in dobras_por_gerador(registros, semente):
        fora_set = set(fora)
        treino = [r for i, r in enumerate(registros) if i not in fora_set]
        idx_treino = [i for i in range(len(registros)) if i not in fora_set]
        modelo = novo_classificador()
        X, y, _ = _xy(_com_extra(treino, idx_treino, extra))
        modelo.fit(X, y)
        teste = _com_extra([registros[i] for i in fora], fora, extra)
        probs[fora] = prob_por_video(modelo, teste)
    return probs


def _com_extra(registros, indices, extra):
    if not extra:
        return registros
    return [{**r, "janelas": [list(j) + list(extra[i]) for j in r["janelas"]]} for r, i in zip(registros, indices)]


def _metricas(y, p, limiar=LIMIAR):
    pares = [(IA if yi else REAL, IA if pi >= limiar else REAL) for yi, pi in zip(y, p)]
    return pares, _auc(list(y), list(p))


def _resumo_binario(y, p, limiar=LIMIAR, n_boot=1000):
    pares, auc = _metricas(y, p, limiar)
    ic = bootstrap(pares, n_boot)
    acc = float(np.mean([a == b for a, b in pares]))
    reais = [b for a, b in pares if a == REAL]
    ias = [b for a, b in pares if a == IA]
    return {
        "videos": len(pares),
        "auc": round(auc, 4) if auc is not None else None,
        "acuracia": round(acc, 4),
        "acuracia_ic95": ic.get("acuracia_decididos"),
        "taxa_falso_positivo": round(sum(b == IA for b in reais) / len(reais), 4) if reais else None,
        "taxa_falso_positivo_ic95": ic.get("taxa_falso_positivo"),
        "ia_detectada": round(sum(b == IA for b in ias) / len(ias), 4) if ias else None,
        "ia_detectada_ic95": ic.get("recall_ia"),
    }


def _prob_core(relatorios_core):
    """Mediana da probabilidade_ia do Core por (pasta, video)."""
    saida = {}
    for rel in relatorios_core:
        if "erro" in rel:
            continue
        probs = [f["probabilidade_ia"] for f in rel["frames"]
                 if not f.get("erro") and not f.get("fora_de_dominio") and isinstance(f.get("probabilidade_ia"), (int, float))]
        if probs:
            saida[(rel["pasta"], rel["video"])] = float(np.median(probs))
    return saida


def avaliar(registros, relatorios_core=None, semente=0):
    y = np.array([int(r["rotulo"] == IA) for r in registros])
    fps = np.array([r["info"]["fps"] for r in registros])
    res = {"videos": len(registros), "reais": int((y == 0).sum()), "ia": int(y.sum())}

    # Atalho 1: o fps sozinho. Se ele separa bem, qualquer ganho do modelo e suspeito.
    auc_fps = _auc(list(y), list(-fps))
    res["atalho_auc_so_fps"] = round(max(auc_fps, 1 - auc_fps), 4)

    p = fora_da_amostra(registros, semente=semente)
    res["trajetoria"] = _resumo_binario(y, p)

    por_gerador = {}
    for g, fora in dobras_por_gerador(registros, semente):
        ia_fora = [i for i in fora if registros[i]["rotulo"] == IA]
        por_gerador[g] = round(float(np.mean(p[ia_fora] >= LIMIAR)), 4)
    res["trajetoria_ia_detectada_por_gerador_fora"] = por_gerador

    # Atalho 2: so os videos em 24/30 fps (as duas classes existem nas duas taxas).
    sub = np.isin(np.round(fps), [24, 25, 30]) | ((fps > 29) & (fps < 30.5))
    res["trajetoria_so_24_30fps"] = _resumo_binario(y[sub], p[sub])

    if relatorios_core:
        core = _prob_core(relatorios_core)
        tem = np.array([(r["pasta"], r["video"]) in core for r in registros])
        idx = np.flatnonzero(tem)
        regs = [registros[i] for i in idx]
        pc = np.array([core[(r["pasta"], r["video"])] for r in regs])
        extra = {k: [pc[k]] for k in range(len(regs))}
        pf = fora_da_amostra(regs, extra=extra, semente=semente)
        pt = p[idx]
        res["comparacao_mesmos_videos"] = {
            "core_mediana_frames": _resumo_binario(y[idx], pc),
            "trajetoria": _resumo_binario(y[idx], pt),
            "fusao_trajetoria_mais_core": _resumo_binario(y[idx], pf),
        }
    return res, p


def treinar_final(registros, destino=MODELO_PADRAO, relatorios_core=None):
    """Grava o modelo so de trajetoria e, se houver relatorios do Core, o de fusao.

    A fusao (21 caracteristicas + mediana da prob. do Core nos frames) foi a
    melhor combinacao medida; o modelo so de trajetoria fica de reserva para
    videos em que o Core nao da nenhum frame valido."""
    import joblib

    modelo = novo_classificador()
    X, y, _ = _xy(registros)
    modelo.fit(X, y)
    pacote = {
        "modelo": modelo,
        "caracteristicas": NOMES_CARACTERISTICAS,
        "limiar": LIMIAR,
        "videos_treino": len(registros),
        "descricao": "LogReg sobre 21 caracteristicas da trajetoria DINOv2 (ReStraV); prob = media das janelas",
    }
    if relatorios_core:
        core = _prob_core(relatorios_core)
        idx = [i for i, r in enumerate(registros) if (r["pasta"], r["video"]) in core]
        regs = [registros[i] for i in idx]
        extra = {i: [core[(r["pasta"], r["video"])]] for i, r in zip(idx, regs)}
        fusao = novo_classificador()
        Xf, yf, _ = _xy(_com_extra(regs, idx, extra))
        fusao.fit(Xf, yf)
        pacote["modelo_fusao"] = fusao
        pacote["caracteristicas_fusao"] = list(NOMES_CARACTERISTICAS) + ["core_mediana_prob_ia"]
        pacote["videos_treino_fusao"] = len(regs)
    destino.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pacote, destino)
    return destino


def main(argv=None):
    parser = argparse.ArgumentParser(description="Extrai, avalia e treina o módulo de trajetória DINOv2.")
    parser.add_argument("pasta", type=Path, help="pasta com reais/ e ia/")
    parser.add_argument("--saida", type=Path, required=True)
    parser.add_argument("--relatorios-core", type=Path, default=None,
                        help="saída do avaliar_lote para os MESMOS vídeos (fusão com o Core)")
    parser.add_argument("--so-avaliar", action="store_true")
    parser.add_argument("--janelas", type=int, default=1,
                        help="janelas de 24 frames por vídeo (1 = como no artigo; cada uma custa 24 passes do DINOv2)")
    parser.add_argument("--salvar-modelo", type=Path, default=None,
                        help=f"grava o modelo final (padrão sugerido: {MODELO_PADRAO})")
    args = parser.parse_args(argv)

    if not args.so_avaliar:
        extrair(args.pasta, args.saida, max_janelas=args.janelas)
    registros = carregar_cache(args.saida)
    if len(registros) < 10:
        print("Poucos vídeos com características extraídas.", file=sys.stderr)
        return 2
    core = carregar_relatorios(args.relatorios_core) if args.relatorios_core else None
    res, _ = avaliar(registros, core)
    (args.saida / "avaliacao_trajetoria.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=2))
    if args.salvar_modelo:
        print(f"Modelo salvo em {treinar_final(registros, args.salvar_modelo, core)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
