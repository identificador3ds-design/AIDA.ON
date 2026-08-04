import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from config import CSV_METRICAS, DATASET_IA_DIR, DATASET_REAIS_DIR, GRAFICOS_DIR, criar_estrutura
from extratores import extrair_todas_metricas
from utils_imagem import listar_imagens


METRICAS_GRAFICOS = [
    "fft_energia_alta",
    "fft_razao_alta_baixa",
    "rugosidade",
    "gradiente_medio",
    "laplaciano_medio",
    "lsb_entropia",
    "lsb_uniformidade",
]


def gerar_graficos_comparativos(csv_path=CSV_METRICAS):
    criar_estrutura()
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV não encontrado: {csv_path}")
    df = pd.read_csv(csv_path, encoding="utf-8-sig")
    if "classe" not in df.columns or df.empty:
        raise ValueError("CSV inválido ou vazio.")

    nomes = {0: "Reais", 1: "IA/manipuladas"}
    for metrica in METRICAS_GRAFICOS:
        if metrica not in df.columns:
            continue
        medias = df.groupby("classe")[metrica].mean().reindex([0, 1])
        plt.figure(figsize=(6, 4))
        plt.bar([nomes.get(i, str(i)) for i in medias.index], medias.values, color=["#2f6f73", "#b84a62"])
        plt.title(f"Média de {metrica}")
        plt.ylabel("Média")
        plt.tight_layout()
        plt.savefig(GRAFICOS_DIR / f"comparativo_{metrica}.png", dpi=160)
        plt.close()

    principais = [m for m in METRICAS_GRAFICOS if m in df.columns]
    if principais:
        comp = df.groupby("classe")[principais].mean().T
        comp.columns = ["Reais", "IA/manipuladas"]
        comp.plot(kind="bar", figsize=(10, 5))
        plt.title("Comparação de médias das principais métricas")
        plt.ylabel("Média")
        plt.tight_layout()
        plt.savefig(GRAFICOS_DIR / "comparativo_metricas_principais.png", dpi=160)
        plt.close()


def gerar_csv():
    criar_estrutura()
    linhas = []
    conjuntos = [(DATASET_REAIS_DIR, 0), (DATASET_IA_DIR, 1)]

    for pasta, classe in conjuntos:
        imagens = listar_imagens(pasta)
        if not imagens:
            print(f"Aviso: nenhuma imagem encontrada em {pasta}")
        for caminho in imagens:
            try:
                metricas = extrair_todas_metricas(caminho)
                metricas["classe"] = classe
                metricas["arquivo"] = caminho.name
                metricas["caminho"] = str(caminho)
                linhas.append(metricas)
                print(f"OK: {caminho}")
            except Exception as exc:
                print(f"Erro ao processar {caminho}: {exc}")

    if not linhas:
        raise RuntimeError(
            "Nenhuma imagem válida foi processada. Coloque imagens em dataset/reais e dataset/ia."
        )

    df = pd.DataFrame(linhas)
    colunas_info = ["arquivo", "caminho", "classe"]
    metricas = sorted([c for c in df.columns if c not in colunas_info])
    df = df[colunas_info + metricas]
    df.to_csv(CSV_METRICAS, index=False, encoding="utf-8-sig")
    gerar_graficos_comparativos(CSV_METRICAS)
    print(f"CSV salvo em: {CSV_METRICAS}")
    print(f"Gráficos salvos em: {GRAFICOS_DIR}")
    return CSV_METRICAS


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gera CSV de métricas AIDA.ON.")
    parser.add_argument("--graficos", action="store_true", help="Apenas gera gráficos a partir do CSV existente.")
    args = parser.parse_args()
    if args.graficos:
        gerar_graficos_comparativos()
        print(f"Gráficos salvos em: {GRAFICOS_DIR}")
    else:
        gerar_csv()
