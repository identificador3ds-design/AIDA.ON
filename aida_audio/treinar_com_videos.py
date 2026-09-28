"""Treina o modelo de audio com as trilhas dos VIDEOS junto do MLS/MLAAD.

Por que: o modelo treinado so com audiolivro (MLS) contra TTS (MLAAD) nao
generaliza para o som de video (avaliar_externo: AUC 0,65 e 9,7% de falso
positivo nos celulares reais). O problema e de dominio: celular tem ruido,
musica e microfone ruim; Sora/Veo geram som ambiente, nao so fala.

Validacao honesta, como em aida_video.validacao: em cada rodada os videos IA
de UM gerador ficam de fora, junto com uma fatia dos videos reais. O modelo e
treinado no resto (MLS/MLAAD + outros videos) e so preve os de fora. Juntando
as rodadas, cada video recebe uma probabilidade de um modelo que nunca o viu.

O limiar final e escolhido nessas probabilidades fora da amostra para manter o
falso positivo nos celulares reais abaixo de `--fp-alvo`; entre ele e o limiar
fica uma faixa INCONCLUSIVA (`margem_inconclusiva` no pacote salvo).

Uso (na pasta AIDA.ON):
    python -m aida_audio.treinar_com_videos C:/aida_audio_ds/caracteristicas_audio.csv ../videos_teste_padronizado \\
        --cache-videos ../resultados_audio/caracteristicas_videos.csv --saida ../resultados_audio/com_videos
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np

from .avaliar_externo import _auc, listar
from .caracteristicas import extrair_caracteristicas
from .carregar import AudioAusente, carregar_audio
from .modelo import MAX_SEGUNDOS_TREINO, PASTA_MODELOS, calcular_eer

ARQUIVO_CANDIDATO = PASTA_MODELOS / "modelo_audio_com_videos.joblib"
FATIAS_REAIS = 5
COLUNAS_META = ("arquivo", "rotulo", "grupo", "gerador", "origem")


def _ler_csv(caminho):
    with open(caminho, newline="", encoding="utf-8") as arquivo:
        linhas = list(csv.DictReader(arquivo))
    for linha in linhas:
        for chave, valor in linha.items():
            if chave not in COLUNAS_META:
                linha[chave] = float(valor)
        linha["rotulo"] = int(linha["rotulo"])
    return linhas


def _gravar_csv(caminho, linhas):
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=list(linhas[0]))
        escritor.writeheader()
        escritor.writerows(linhas)


def extrair_videos(pasta, avisar=print):
    """Caracteristicas da trilha de audio de cada video (os sem audio sao ignorados)."""
    linhas = []
    for arquivo, rotulo, gerador in listar(pasta):
        try:
            amostras, taxa = carregar_audio(arquivo, max_segundos=MAX_SEGUNDOS_TREINO)
            caracteristicas, qualidade = extrair_caracteristicas(amostras, taxa)
        except AudioAusente:
            continue
        except (ValueError, FileNotFoundError) as exc:
            avisar(f"[pulado] {arquivo.name}: {exc}")
            continue
        if not qualidade["suficiente"]:
            avisar(f"[pulado] {arquivo.name}: audio curto ou so silencio")
            continue
        linhas.append({"arquivo": arquivo.name, "rotulo": rotulo, "grupo": f"video/{gerador}",
                       "gerador": gerador, "origem": "video", **caracteristicas})
    return linhas


def _matriz(linhas, colunas):
    return np.array([[l[c] for c in colunas] for l in linhas], dtype=np.float64)


def _pesos(linhas, peso_videos):
    """Da ao conjunto de videos o mesmo peso total do dataset base, vezes `peso_videos`."""
    n_video = sum(l["origem"] == "video" for l in linhas)
    n_base = len(linhas) - n_video
    if not n_video or not n_base:
        return np.ones(len(linhas))
    w_video = peso_videos * n_base / n_video
    return np.array([w_video if l["origem"] == "video" else 1.0 for l in linhas])


def criar_modelo(nome, semente=42):
    from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    if nome == "regressao_logistica":
        return make_pipeline(StandardScaler(), LogisticRegression(max_iter=3000, C=0.5, class_weight="balanced"))
    if nome == "random_forest":
        return RandomForestClassifier(n_estimators=400, min_samples_leaf=2, class_weight="balanced",
                                      random_state=semente, n_jobs=-1)
    if nome == "gradient_boosting":
        return HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, l2_regularization=1.0,
                                              class_weight="balanced", random_state=semente)
    raise ValueError(f"Modelo desconhecido: {nome}")


def _ajustar(modelo, x, y, w):
    passo = modelo.steps[-1][0] if hasattr(modelo, "steps") else None
    if passo:
        modelo.fit(x, y, **{f"{passo}__sample_weight": w})
    else:
        modelo.fit(x, y, sample_weight=w)
    return modelo


def fatias_reais(videos, n=FATIAS_REAIS, semente=42):
    """Divide os videos reais em n fatias fixas (o mesmo video sempre na mesma fatia)."""
    reais = sorted(l["arquivo"] for l in videos if l["rotulo"] == 0)
    rng = np.random.default_rng(semente)
    rng.shuffle(reais)
    return {nome: i % n for i, nome in enumerate(reais)}


def validar_por_gerador(base, videos, nome_modelo, peso_videos=1.0, usar_base=True, semente=42):
    """Probabilidade fora da amostra para cada video. Devolve lista de dicts."""
    colunas = [c for c in videos[0] if c not in COLUNAS_META]
    fatia = fatias_reais(videos, semente=semente)
    geradores = sorted({l["gerador"] for l in videos if l["rotulo"] == 1})
    previstos = {}
    # Cada rodada tira um gerador e uma fatia de reais. Com menos geradores que
    # fatias, as rodadas extras tiram so reais (senao alguma fatia nunca seria prevista).
    for i in range(max(len(geradores), FATIAS_REAIS)):
        gerador = geradores[i] if i < len(geradores) else None
        fatia_rodada = i % FATIAS_REAIS
        fora = [l for l in videos
                if (l["rotulo"] == 1 and l["gerador"] == gerador)
                or (l["rotulo"] == 0 and fatia[l["arquivo"]] == fatia_rodada)]
        nomes_fora = {l["arquivo"] for l in fora}
        treino = [l for l in videos if l["arquivo"] not in nomes_fora]
        if usar_base:
            treino = base + treino
        modelo = _ajustar(criar_modelo(nome_modelo, semente), _matriz(treino, colunas),
                          np.array([l["rotulo"] for l in treino]), _pesos(treino, peso_videos))
        probs = modelo.predict_proba(_matriz(fora, colunas))[:, 1]
        for l, p in zip(fora, probs):
            # Um real pode cair em mais de uma rodada (mais geradores que fatias): fica a media.
            previstos.setdefault(l["arquivo"], {"arquivo": l["arquivo"], "rotulo": l["rotulo"],
                                                "gerador": l["gerador"], "probs": []})["probs"].append(float(p))
    saida = []
    for item in previstos.values():
        saida.append({**{k: v for k, v in item.items() if k != "probs"},
                      "probabilidade_ia": round(float(np.mean(item["probs"])), 4)})
    return saida


def escolher_limiar(previsoes, fp_alvo):
    """Menor limiar com falso positivo <= fp_alvo nos reais (probabilidades fora da amostra)."""
    reais = np.sort([p["probabilidade_ia"] for p in previsoes if p["rotulo"] == 0])
    if not len(reais):
        return 0.5
    # Quantos reais podem passar do limiar sem estourar o alvo.
    permitidos = int(np.floor(fp_alvo * len(reais)))
    limiar = reais[len(reais) - 1 - permitidos] + 1e-6
    return float(min(max(limiar, 0.5), 0.999))


def medir(previsoes, limiar, margem):
    y = [p["rotulo"] for p in previsoes]
    probs = [p["probabilidade_ia"] for p in previsoes]

    def rotulo(prob):
        if prob >= limiar:
            return "IA/MANIPULADA"
        if prob <= limiar - margem:
            return "REAL"
        return "INCONCLUSIVO"

    reais = [rotulo(p["probabilidade_ia"]) for p in previsoes if p["rotulo"] == 0]
    ias = [p for p in previsoes if p["rotulo"] == 1]
    por_gerador = defaultdict(list)
    for p in ias:
        por_gerador[p["gerador"]].append(rotulo(p["probabilidade_ia"]))
    auc = _auc(y, probs)
    eer = calcular_eer(y, probs)[0] if len(set(y)) == 2 else None
    return {
        "reais": len(reais),
        "ia": len(ias),
        "auc": round(auc, 4) if auc is not None else None,
        "eer": round(eer, 4) if eer is not None else None,
        "limiar": round(limiar, 4),
        "margem_inconclusiva": margem,
        "falso_positivo": round(reais.count("IA/MANIPULADA") / len(reais), 4) if reais else None,
        "reais_inconclusivos": round(reais.count("INCONCLUSIVO") / len(reais), 4) if reais else None,
        "ia_detectada": round(sum(r == "IA/MANIPULADA" for v in por_gerador.values() for r in v) / len(ias), 4)
        if ias else None,
        "ia_detectada_por_gerador": {g: round(v.count("IA/MANIPULADA") / len(v), 4)
                                     for g, v in sorted(por_gerador.items())},
    }


CONFIGURACOES = [
    # (nome, modelo, usar_base, peso_videos)
    ("so_base_logreg", "regressao_logistica", True, 0.0),
    ("base+videos_logreg", "regressao_logistica", True, 1.0),
    ("base+videos_rf", "random_forest", True, 1.0),
    ("base+videos_gb", "gradient_boosting", True, 1.0),
    ("so_videos_logreg", "regressao_logistica", False, 1.0),
    ("so_videos_rf", "random_forest", False, 1.0),
    ("so_videos_gb", "gradient_boosting", False, 1.0),
]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Treina o áudio com MLS/MLAAD + trilhas dos vídeos.")
    parser.add_argument("csv_base", type=Path, help="caracteristicas_audio.csv gerado por aida_audio.modelo")
    parser.add_argument("videos", type=Path, help="pasta com reais/ e ia/ (videos)")
    parser.add_argument("--cache-videos", type=Path, default=None, help="CSV das caracteristicas dos videos")
    parser.add_argument("--saida", type=Path, default=None, help="pasta para validacao.json e previsoes.csv")
    parser.add_argument("--destino", type=Path, default=ARQUIVO_CANDIDATO)
    parser.add_argument("--fp-alvo", type=float, default=0.02)
    parser.add_argument("--margem", type=float, default=0.15, help="largura da faixa INCONCLUSIVA abaixo do limiar")
    args = parser.parse_args(argv)

    if args.cache_videos and args.cache_videos.is_file():
        videos = _ler_csv(args.cache_videos)
    else:
        videos = extrair_videos(args.videos)
        if args.cache_videos and videos:
            _gravar_csv(args.cache_videos, videos)
    if not videos:
        print("Nenhum vídeo com áudio.", file=sys.stderr)
        return 2
    base = _ler_csv(args.csv_base)
    for linha in base:
        linha["gerador"] = linha["grupo"].split("/", 1)[-1]
        linha["origem"] = "base"
    colunas = [c for c in videos[0] if c not in COLUNAS_META]
    faltando = [c for c in colunas if c not in base[0]]
    if faltando:
        raise ValueError(f"CSV base sem as colunas {faltando[:3]}...; gere de novo com aida_audio.modelo")
    print(f"base: {len(base)} áudios; vídeos com áudio: {sum(v['rotulo'] == 0 for v in videos)} reais, "
          f"{sum(v['rotulo'] == 1 for v in videos)} IA")

    resultados = {}
    melhores = {}
    for nome, modelo, usar_base, peso in CONFIGURACOES:
        previsoes = validar_por_gerador(base if usar_base else [], videos, modelo, peso or 1e-9, usar_base)
        limiar = escolher_limiar(previsoes, args.fp_alvo)
        resultados[nome] = {"a_0_5": medir(previsoes, 0.5, 0.0), "limiar_fp_alvo": medir(previsoes, limiar, args.margem)}
        melhores[nome] = previsoes
        r = resultados[nome]["limiar_fp_alvo"]
        print(f"{nome:22s} AUC {r['auc']}  limiar {r['limiar']:.3f}  FP {r['falso_positivo']:.1%}  "
              f"IA detectada {r['ia_detectada']:.1%}  por gerador {r['ia_detectada_por_gerador']}")

    # Escolhe pela deteccao com o FP controlado; empate -> AUC.
    escolhido = max(resultados, key=lambda n: (resultados[n]["limiar_fp_alvo"]["ia_detectada"],
                                               resultados[n]["limiar_fp_alvo"]["auc"] or 0))
    _, nome_modelo, usar_base, peso = next(c for c in CONFIGURACOES if c[0] == escolhido)
    final_linhas = (base if usar_base else []) + videos
    final = _ajustar(criar_modelo(nome_modelo), _matriz(final_linhas, colunas),
                     np.array([l["rotulo"] for l in final_linhas]), _pesos(final_linhas, peso or 1e-9))
    medido = resultados[escolhido]["limiar_fp_alvo"]
    pacote = {
        "modelo": final,
        "nome": f"{nome_modelo} ({escolhido})",
        "colunas": colunas,
        "limiar": medido["limiar"],
        "margem_inconclusiva": args.margem,
        "faixa_inconclusiva": (round(medido["limiar"] - args.margem, 4), medido["limiar"]),
        "desempenho_teste": {"videos_gerador_fora": medido, "configuracoes": resultados},
        "n_total": len(final_linhas),
        "treinado_em": datetime.now().isoformat(timespec="seconds"),
    }
    import joblib

    args.destino.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pacote, args.destino)
    print(f"\nEscolhido: {escolhido} -> {args.destino}")
    print(json.dumps(medido, ensure_ascii=False, indent=2))
    if args.saida:
        args.saida.mkdir(parents=True, exist_ok=True)
        (args.saida / "validacao.json").write_text(
            json.dumps({"escolhido": escolhido, "fp_alvo": args.fp_alvo, "resultados": resultados},
                       ensure_ascii=False, indent=2), encoding="utf-8")
        _gravar_csv(args.saida / "previsoes.csv", melhores[escolhido])
    return 0


if __name__ == "__main__":
    sys.exit(main())
