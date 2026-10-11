"""Estudo dos parametros e treino do classificador do AIDA Documents.

Mesmas pastas de `avaliar_lote` (<pasta>/reais, <pasta>/ia ou <pasta>/manipulados).

1. extrair: as caracteristicas de `caracteristicas.py` de cada PDF, num CSV.
2. estudar: para cada caracteristica, a media em cada classe e a AUC dela sozinha. Uma
   caracteristica que separa tudo sozinha (AUC 1,0) quase sempre e atalho do conjunto
   (todos os de IA saem do mesmo programa), nao sinal de IA.
3. avaliar: regressao logistica com validacao deixando UM documento de fora por vez.
4. treinar (--salvar): ajusta em tudo e grava aida_documents/modelos/documentos.joblib.
   Recusa abaixo de MIN_POR_CLASSE documentos por classe, porque com poucos exemplos o
   modelo so decora o programa gerador.

Uso (na pasta AIDA.ON):
    python -m aida_documents.treinar "G:/Meu Drive/DOCS GATO/lote" --saida estudo_documentos
    python -m aida_documents.treinar <pasta> --saida estudo_documentos --salvar
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np

from .avaliar_lote import ROTULOS, _auc
from .caracteristicas import NOMES_CARACTERISTICAS, caracteristicas_documento

IA = "IA/MANIPULADA"
REAL = "REAL"
MIN_POR_CLASSE = 30
LIMIAR = 0.5
ARQUIVO_MODELO = Path(__file__).with_name("modelos") / "documentos.joblib"


def extrair(pasta):
    registros = []
    for sub, rotulo in ROTULOS.items():
        for arq in sorted((Path(pasta) / sub).glob("*.pdf")):
            try:
                vetor, _ = caracteristicas_documento(arq)
                registros.append({"arquivo": arq.name, "rotulo": rotulo, "x": vetor})
            except Exception as exc:  # um PDF quebrado nao para o lote
                registros.append({"arquivo": arq.name, "rotulo": rotulo, "erro": f"{type(exc).__name__}: {exc}"})
    return registros


def _xy(registros):
    validos = [r for r in registros if "erro" not in r]
    X = np.array([r["x"] for r in validos], dtype=float).reshape(len(validos), len(NOMES_CARACTERISTICAS))
    y = np.array([int(r["rotulo"] == IA) for r in validos])
    return X, y, validos


def estudar(X, y):
    """Media por classe e AUC de cada caracteristica sozinha (0,5 = nao separa)."""
    linhas = []
    for j, nome in enumerate(NOMES_CARACTERISTICAS):
        auc = _auc([(v, IA if t else REAL) for v, t in zip(X[:, j], y)])
        linhas.append({
            "caracteristica": nome,
            "media_real": round(float(X[y == 0, j].mean()), 4) if (y == 0).any() else None,
            "media_ia": round(float(X[y == 1, j].mean()), 4) if (y == 1).any() else None,
            "auc_sozinha": round(auc, 4) if auc is not None else None,
            "separacao": round(abs(auc - 0.5) * 2, 4) if auc is not None else None,
        })
    return sorted(linhas, key=lambda l: -(l["separacao"] or 0))


def novo_classificador():
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    return make_pipeline(StandardScaler(), LogisticRegression(C=0.3, max_iter=2000, class_weight="balanced"))


def deixa_um_de_fora(X, y):
    probs = np.full(len(y), np.nan)
    for i in range(len(y)):
        treino = np.arange(len(y)) != i
        if len(set(y[treino])) < 2:
            continue
        modelo = novo_classificador().fit(X[treino], y[treino])
        probs[i] = modelo.predict_proba(X[i:i + 1])[0, 1]
    return probs


def avaliar(X, y):
    p = deixa_um_de_fora(X, y)
    ok = ~np.isnan(p)
    pred = p[ok] >= LIMIAR
    reais, ias = y[ok] == 0, y[ok] == 1
    auc = _auc([(pi, IA if t else REAL) for pi, t in zip(p[ok], y[ok])])
    return {
        "documentos": int(len(y)),
        "reais": int((y == 0).sum()),
        "ia": int((y == 1).sum()),
        "auc_fora_da_amostra": round(auc, 4) if auc is not None else None,
        "acuracia": round(float((pred == (y[ok] == 1)).mean()), 4) if ok.any() else None,
        "taxa_falso_positivo": round(float(pred[reais].mean()), 4) if reais.any() else None,
        "ia_detectada": round(float(pred[ias].mean()), 4) if ias.any() else None,
        "aviso": None if min((y == 0).sum(), (y == 1).sum()) >= MIN_POR_CLASSE else (
            f"menos de {MIN_POR_CLASSE} documentos por classe: numeros so de estudo, nao publicar"),
    }, p


def treinar_final(X, y, destino=ARQUIVO_MODELO, forcar=False):
    if not forcar and min((y == 0).sum(), (y == 1).sum()) < MIN_POR_CLASSE:
        raise ValueError(f"precisa de pelo menos {MIN_POR_CLASSE} documentos por classe (use --forcar so para teste)")
    import joblib

    modelo = novo_classificador().fit(X, y)
    Path(destino).parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"modelo": modelo, "caracteristicas": NOMES_CARACTERISTICAS, "limiar": LIMIAR}, destino)
    return destino


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pasta")
    parser.add_argument("--saida", default="estudo_documentos")
    parser.add_argument("--salvar", action="store_true", help="grava o modelo final em aida_documents/modelos")
    parser.add_argument("--forcar", action="store_true", help="salva mesmo abaixo do minimo por classe (teste)")
    args = parser.parse_args(argv)

    saida = Path(args.saida)
    saida.mkdir(parents=True, exist_ok=True)
    registros = extrair(args.pasta)
    for r in registros:
        if "erro" in r:
            print(f"erro em {r['arquivo']}: {r['erro']}")
    X, y, validos = _xy(registros)

    with open(saida / "caracteristicas.csv", "w", newline="", encoding="utf-8-sig") as f:
        escritor = csv.writer(f, delimiter=";")
        escritor.writerow(["arquivo", "rotulo", *NOMES_CARACTERISTICAS])
        for r in validos:
            escritor.writerow([r["arquivo"], r["rotulo"], *[round(v, 5) for v in r["x"]]])

    estudo = estudar(X, y)
    resultado, p = avaliar(X, y)
    resultado["prob_ia_fora_da_amostra"] = {r["arquivo"]: (None if np.isnan(pi) else round(float(pi), 4)) for r, pi in zip(validos, p)}
    resultado["caracteristicas"] = estudo
    (saida / "estudo.json").write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"{'caracteristica':36} {'real':>8} {'ia':>8} {'AUC':>6}")
    for l in estudo:
        print(f"{l['caracteristica']:36} {l['media_real']:>8} {l['media_ia']:>8} {l['auc_sozinha']:>6}")
    for chave in ("documentos", "reais", "ia", "auc_fora_da_amostra", "acuracia", "taxa_falso_positivo", "ia_detectada", "aviso"):
        print(f"{chave}: {resultado[chave]}")
    if args.salvar:
        print(f"modelo: {treinar_final(X, y, forcar=args.forcar)}")
    print(f"resultados: {saida}")


if __name__ == "__main__":
    main()
