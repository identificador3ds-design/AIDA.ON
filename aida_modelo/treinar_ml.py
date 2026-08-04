import json
from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

from config import (
    ARQUIVO_COLUNAS,
    ARQUIVO_DESEMPENHO,
    ARQUIVO_IMPUTER,
    ARQUIVO_MELHOR_MODELO,
    ARQUIVO_MODELO_LOGISTICO,
    ARQUIVO_MODELO_RANDOM_FOREST,
    ARQUIVO_SCALER,
    CSV_METRICAS,
    GRAFICOS_DIR,
    MIN_IMAGENS_POR_CLASSE,
    MODELOS_DIR,
    RANDOM_STATE,
    RELATORIOS_DIR,
    TEST_SIZE,
    criar_estrutura,
)


def _validar_base(df):
    if "classe" not in df.columns:
        raise ValueError("O CSV precisa conter a coluna 'classe'.")
    contagem = df["classe"].value_counts().to_dict()
    faltas = []
    for classe, nome in [(0, "reais"), (1, "IA/manipuladas")]:
        if contagem.get(classe, 0) < MIN_IMAGENS_POR_CLASSE:
            faltas.append(f"{nome}: {contagem.get(classe, 0)} imagem(ns)")
    if faltas:
        raise RuntimeError(
            "Não há imagens suficientes para treinar. "
            "Coloque imagens reais em dataset/reais e imagens IA/manipuladas em dataset/ia. "
            f"Situação atual: {', '.join(faltas)}."
        )


def _avaliar(nome, modelo, x_teste, y_teste):
    pred = modelo.predict(x_teste)
    acc = accuracy_score(y_teste, pred)
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_teste, pred, labels=[0, 1], zero_division=0
    )
    return {
        "modelo": nome,
        "acuracia": float(acc),
        "precision_real": float(precision[0]),
        "precision_ia": float(precision[1]),
        "recall_real": float(recall[0]),
        "recall_ia": float(recall[1]),
        "f1_real": float(f1[0]),
        "f1_ia": float(f1[1]),
        "f1_macro": float((f1[0] + f1[1]) / 2),
        "matriz_confusao": confusion_matrix(y_teste, pred, labels=[0, 1]).tolist(),
    }


def _salvar_matriz(nome, matriz):
    plt.figure(figsize=(5, 4))
    sns.heatmap(matriz, annot=True, fmt="d", cmap="Blues", xticklabels=["Real", "IA"], yticklabels=["Real", "IA"])
    plt.xlabel("Previsto")
    plt.ylabel("Verdadeiro")
    plt.title(f"Matriz de confusão - {nome}")
    plt.tight_layout()
    plt.savefig(GRAFICOS_DIR / f"matriz_confusao_{nome}.png", dpi=160)
    plt.close()


def treinar_modelos():
    criar_estrutura()
    if not CSV_METRICAS.exists():
        raise FileNotFoundError(f"CSV não encontrado: {CSV_METRICAS}. Execute python gerar_csv.py primeiro.")

    df = pd.read_csv(CSV_METRICAS, encoding="utf-8-sig")
    _validar_base(df)
    y = df["classe"].astype(int)
    x = df.drop(columns=[c for c in ["classe", "arquivo", "caminho"] if c in df.columns])
    x = x.apply(pd.to_numeric, errors="coerce")
    colunas = list(x.columns)

    stratify = y if y.value_counts().min() >= 2 else None
    x_train, x_test, y_train, y_test = train_test_split(
        x, y, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=stratify
    )

    imputer = SimpleImputer(strategy="median")
    x_train_imp = imputer.fit_transform(x_train)
    x_test_imp = imputer.transform(x_test)

    scaler = StandardScaler()
    x_train_scaled = scaler.fit_transform(x_train_imp)
    x_test_scaled = scaler.transform(x_test_imp)

    logistica = LogisticRegression(max_iter=2000, random_state=RANDOM_STATE, class_weight="balanced")
    logistica.fit(x_train_scaled, y_train)

    floresta = RandomForestClassifier(
        n_estimators=400,
        random_state=RANDOM_STATE,
        class_weight="balanced",
        n_jobs=-1,
    )
    floresta.fit(x_train_imp, y_train)

    aval_log = _avaliar("regressao_logistica", logistica, x_test_scaled, y_test)
    aval_rf = _avaliar("random_forest", floresta, x_test_imp, y_test)

    melhor = aval_rf
    melhor_modelo = floresta
    usa_scaler = False
    if (aval_log["f1_macro"], aval_log["recall_ia"]) > (aval_rf["f1_macro"], aval_rf["recall_ia"]):
        melhor = aval_log
        melhor_modelo = logistica
        usa_scaler = True

    joblib.dump(logistica, MODELOS_DIR / ARQUIVO_MODELO_LOGISTICO)
    joblib.dump(floresta, MODELOS_DIR / ARQUIVO_MODELO_RANDOM_FOREST)
    joblib.dump({"nome": melhor["modelo"], "modelo": melhor_modelo, "usa_scaler": usa_scaler}, MODELOS_DIR / ARQUIVO_MELHOR_MODELO)
    joblib.dump(scaler, MODELOS_DIR / ARQUIVO_SCALER)
    joblib.dump(imputer, MODELOS_DIR / ARQUIVO_IMPUTER)
    (MODELOS_DIR / ARQUIVO_COLUNAS).write_text(json.dumps(colunas, ensure_ascii=False, indent=2), encoding="utf-8")

    desempenho = {"regressao_logistica": aval_log, "random_forest": aval_rf, "melhor_modelo": melhor["modelo"]}
    (MODELOS_DIR / ARQUIVO_DESEMPENHO).write_text(json.dumps(desempenho, ensure_ascii=False, indent=2), encoding="utf-8")
    (RELATORIOS_DIR / "relatorio_treinamento.json").write_text(json.dumps(desempenho, ensure_ascii=False, indent=2), encoding="utf-8")

    _salvar_matriz("regressao_logistica", aval_log["matriz_confusao"])
    _salvar_matriz("random_forest", aval_rf["matriz_confusao"])

    importancias = pd.Series(floresta.feature_importances_, index=colunas).sort_values(ascending=False).head(20)
    plt.figure(figsize=(9, 6))
    importancias.sort_values().plot(kind="barh", color="#2f6f73")
    plt.title("Principais métricas - Random Forest")
    plt.tight_layout()
    plt.savefig(GRAFICOS_DIR / "importancia_variaveis_random_forest.png", dpi=160)
    plt.close()

    print(json.dumps(desempenho, ensure_ascii=False, indent=2))
    print(f"Melhor modelo: {melhor['modelo']}")
    return desempenho


if __name__ == "__main__":
    treinar_modelos()
