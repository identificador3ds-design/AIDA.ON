"""Calibra o detector de texto com documentos rotulados e grava `calibracao.json`.

Estrutura esperada (PDF, DOCX ou TXT, em subpastas se quiser):
    <pasta>/humano/...     textos escritos por gente (de preferencia anteriores a 2022)
    <pasta>/ia/...         textos gerados por LLMs (ChatGPT, Claude, Gemini...)

Uso:
    python -m aida_documents.texto.calibrar "G:/Meu Drive/TCC/textos_teste" --idioma pt

Mesma regra do resto do AIDA: os documentos sao divididos em treino (60%), validacao
(20%) e teste (20%). A regressao logistica e ajustada no treino, os limiares sao
escolhidos na validacao e o teste e tocado uma unica vez, para reportar. A divisao e
por DOCUMENTO: segmentos do mesmo arquivo nunca caem em lados diferentes.

Os limiares nao buscam acuracia maxima, e sim um teto de falso positivo: o limiar
"IA" e o menor em que no maximo `--fpr` (padrao 1%) dos documentos humanos da
validacao seriam acusados. O que fica entre os dois limiares sai INCONCLUSIVO.

A passada pelo modelo de linguagem e a parte cara; `--cache` guarda as medidas para
que mudar a semente ou o alvo de falso positivo nao custe outra passada.
"""

from __future__ import annotations

import argparse
import json
import random
from datetime import date
from pathlib import Path

import numpy as np

from .detector import ARQUIVO_CALIBRACAO, FEATURES, MIN_PALAVRAS_DOCUMENTO, _sigmoide, agregar, decidir, logit, medir_segmento, preparar
from .extracao import EXTENSOES_TEXTO
from .perplexidade import obter_modelo

PASTAS = {"humano": 0, "reais": 0, "ia": 1}
MIN_DOCUMENTOS_POR_CLASSE = 20
FNR_ALVO_HUMANO = 0.05
FPR_ALVO_SEGMENTO = 0.05


def coletar(pasta, idioma, modelo, cache=None, aviso=print):
    """Mede todos os documentos da pasta. Devolve lista de {"arquivo", "rotulo", "segmentos"}."""
    cache = Path(cache) if cache else None
    feitos = {}
    if cache and cache.exists():
        feitos = {d["arquivo"]: d for d in json.loads(cache.read_text(encoding="utf-8")) if d.get("modelo") == modelo.nome}
    docs = []
    for sub, rotulo in PASTAS.items():
        arquivos = sorted(a for a in (Path(pasta) / sub).rglob("*") if a.suffix.lower() in EXTENSOES_TEXTO)
        for arq in arquivos:
            chave = f"{sub}/{arq.relative_to(Path(pasta) / sub).as_posix()}"
            if chave in feitos:
                docs.append(feitos[chave])
                continue
            try:
                doc = preparar(arq.read_bytes(), arq.name)
            except Exception as exc:
                aviso(f"  pulado {chave}: {exc}")
                continue
            if doc["idioma"] != idioma or doc["palavras"] < MIN_PALAVRAS_DOCUMENTO:
                aviso(f"  pulado {chave}: idioma {doc['idioma']}, {doc['palavras']} palavras")
                continue
            segmentos = []
            for seg in doc["segmentos"]:
                medidas = medir_segmento(seg["texto"], idioma, modelo)
                segmentos.append({"palavras": seg["palavras"], "medidas": {f: medidas[f] for f in FEATURES}})
            docs.append({"arquivo": chave, "rotulo": rotulo, "modelo": modelo.nome, "segmentos": segmentos})
            aviso(f"  {chave}: {len(segmentos)} segmentos")
            if cache:
                cache.write_text(json.dumps(docs, ensure_ascii=False), encoding="utf-8")
    return docs


def dividir(docs, semente=0):
    """Treino/validacao/teste 60/20/20, estratificado por rotulo, por documento."""
    partes = {"treino": [], "validacao": [], "teste": []}
    for rotulo in (0, 1):
        grupo = sorted((d for d in docs if d["rotulo"] == rotulo), key=lambda d: d["arquivo"])
        random.Random(semente + rotulo).shuffle(grupo)
        a, b = round(0.6 * len(grupo)), round(0.8 * len(grupo))
        partes["treino"] += grupo[:a]
        partes["validacao"] += grupo[a:b]
        partes["teste"] += grupo[b:]
    return partes


def ajustar(treino):
    """Regressao logistica nos segmentos do treino. Devolve centro, escala, pesos e vies."""
    from sklearn.linear_model import LogisticRegression

    linhas = [(s["medidas"], d["rotulo"]) for d in treino for s in d["segmentos"]]
    x = np.array([[np.nan if m[f] is None else m[f] for f in FEATURES] for m, _ in linhas], dtype=float)
    y = np.array([r for _, r in linhas])
    centro = np.nanmean(x, axis=0)
    escala = np.nanstd(x, axis=0)
    escala[~(escala > 0)] = 1.0
    z = (np.where(np.isnan(x), centro, x) - centro) / escala
    modelo = LogisticRegression(class_weight="balanced", max_iter=1000).fit(z, y)
    return {
        "features": list(FEATURES),
        "centro": dict(zip(FEATURES, map(float, centro))),
        "escala": dict(zip(FEATURES, map(float, escala))),
        "pesos": dict(zip(FEATURES, map(float, modelo.coef_[0]))),
        "vies": float(modelo.intercept_[0]),
    }


def pontuar(docs, cal):
    """Aplica os parametros: devolve [(rotulo, probabilidade, fracao_suspeita)] por documento."""
    saida = []
    for d in docs:
        segmentos = []
        for s in d["segmentos"]:
            valor = logit(s["medidas"], cal)
            segmentos.append({"palavras": s["palavras"], "logit": valor, "probabilidade": _sigmoide(valor)})
        saida.append((d["rotulo"], *agregar(segmentos, cal)))
    return saida


def limiar_fpr(negativos, candidatos, alvo):
    """Menor limiar em que a fracao de negativos com score >= limiar fica em `alvo` ou menos."""
    negativos = np.asarray(negativos, dtype=float)
    for t in sorted(set(candidatos) | {1.0}):
        if not len(negativos) or float(np.mean(negativos >= t)) <= alvo:
            return float(t)
    return 1.0


def limiar_fnr(positivos, candidatos, alvo):
    """Maior limiar em que a fracao de positivos com score <= limiar fica em `alvo` ou menos."""
    positivos = np.asarray(positivos, dtype=float)
    for t in sorted(set(candidatos) | {0.0}, reverse=True):
        if not len(positivos) or float(np.mean(positivos <= t)) <= alvo:
            return float(t)
    return 0.0


def auc(pares):
    pos = [p for r, p in pares if r == 1]
    neg = [p for r, p in pares if r == 0]
    if not pos or not neg:
        return None
    return sum(1.0 if a > b else 0.5 if a == b else 0.0 for a in pos for b in neg) / (len(pos) * len(neg))


def metricas(pontuados, cal):
    decisoes = [(r, decidir(p, f, cal)[0]) for r, p, f in pontuados]
    humanos = [d for r, d in decisoes if r == 0]
    ias = [d for r, d in decisoes if r == 1]
    decididos = [(r, d) for r, d in decisoes if d != "INCONCLUSIVO"]
    certos = sum((r == 1) == (d == "IA") for r, d in decididos)
    razao = lambda n, total: round(n / total, 4) if total else None  # noqa: E731
    return {
        "documentos": len(decisoes),
        "auc": (lambda v: round(v, 4) if v is not None else None)(auc([(r, p) for r, p, _ in pontuados])),
        "falso_positivo": razao(sum(d == "IA" for d in humanos), len(humanos)),
        "deteccao": razao(sum(d == "IA" for d in ias), len(ias)),
        "cobertura": razao(len(decididos), len(decisoes)),
        "acuracia_decididos": razao(certos, len(decididos)),
    }


def calibrar(docs, modelo_nome, fpr_alvo=0.01, semente=0):
    partes = dividir(docs, semente)
    cal = {**ajustar(partes["treino"]), "calibrado": True, "limiares": {"segmento": 0.5, "ia": 1.0, "humano": 0.0}}

    # Limiar de segmento: no maximo 5% dos segmentos humanos da validacao destacados.
    seg_val = [(d["rotulo"], _sigmoide(logit(s["medidas"], cal))) for d in partes["validacao"] for s in d["segmentos"]]
    cal["limiares"]["segmento"] = limiar_fpr([p for r, p in seg_val if r == 0], [p for _, p in seg_val], FPR_ALVO_SEGMENTO)

    val = pontuar(partes["validacao"], cal)
    scores = [p for _, p, _ in val]
    ia = limiar_fpr([p for r, p, _ in val if r == 0], scores, fpr_alvo)
    humano = min(limiar_fnr([p for r, p, _ in val if r == 1], scores, FNR_ALVO_HUMANO), ia)
    cal["limiares"].update({"ia": ia, "humano": humano})

    cal.update({
        "modelo": modelo_nome,
        "data": date.today().isoformat(),
        "semente": semente,
        "fpr_alvo": fpr_alvo,
        "documentos": {nome: {"humano": sum(d["rotulo"] == 0 for d in parte), "ia": sum(d["rotulo"] == 1 for d in parte)}
                       for nome, parte in partes.items()},
        "metricas_validacao": metricas(val, cal),
        "metricas_teste": metricas(pontuar(partes["teste"], cal), cal),
    })
    return cal


def main(argv=None):
    parser = argparse.ArgumentParser(description="Calibra o detector de texto gerado por IA.")
    parser.add_argument("pasta")
    parser.add_argument("--idioma", choices=("pt", "en"), required=True)
    parser.add_argument("--fpr", type=float, default=0.01, help="teto de falso positivo em documentos humanos")
    parser.add_argument("--semente", type=int, default=0)
    parser.add_argument("--cache", help="arquivo JSON para guardar as medidas entre execuções")
    parser.add_argument("--saida", default=str(ARQUIVO_CALIBRACAO))
    args = parser.parse_args(argv)

    modelo, motivo = obter_modelo(args.idioma)
    if modelo is None:
        raise SystemExit(f"Sem modelo de linguagem: {motivo}")
    docs = coletar(args.pasta, args.idioma, modelo, args.cache)
    por_classe = [sum(d["rotulo"] == r for d in docs) for r in (0, 1)]
    if min(por_classe) < MIN_DOCUMENTOS_POR_CLASSE:
        raise SystemExit(
            f"Poucos documentos ({por_classe[0]} humanos, {por_classe[1]} de IA): "
            f"são precisos pelo menos {MIN_DOCUMENTOS_POR_CLASSE} de cada para calibrar."
        )
    cal = calibrar(docs, modelo.nome, args.fpr, args.semente)

    saida = Path(args.saida)
    tudo = json.loads(saida.read_text(encoding="utf-8")) if saida.exists() else {}
    tudo[args.idioma] = cal
    saida.write_text(json.dumps(tudo, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: cal[k] for k in ("limiares", "pesos", "documentos", "metricas_validacao", "metricas_teste")},
                     ensure_ascii=False, indent=2))
    print(f"Calibração de '{args.idioma}' gravada em {saida}")


if __name__ == "__main__":
    main()
