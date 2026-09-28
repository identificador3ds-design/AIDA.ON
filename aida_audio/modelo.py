"""Treino e carga do classificador de audio (baseline A: caracteristicas + ML classico).

Estrutura esperada do dataset:

    dataset_audio/
        reais/   <arquivos de audio ou video>   (ou subpastas por locutor/fonte)
        ia/      <arquivos de audio ou video>

Se houver subpastas dentro de reais/ e ia/, o nome da subpasta vira o GRUPO
(locutor, gerador, canal). A divisao treino/teste nunca coloca o mesmo grupo
dos dois lados: sem isso o modelo reconhece a VOZ do locutor, nao o artefato
da sintese, e a acuracia medida fica otimista.

Uso:
    python -m aida_audio.modelo dataset_audio/
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path

import numpy as np

from .caracteristicas import extrair_caracteristicas
from .carregar import AudioAusente, carregar_audio

PASTA_MODELOS = Path(__file__).resolve().parent / "modelos"
ARQUIVO_MODELO = PASTA_MODELOS / "modelo_audio.joblib"
EXTENSOES_MIDIA = {
    ".wav", ".mp3", ".m4a", ".aac", ".ogg", ".opus", ".flac", ".webm",
    ".mp4", ".mov", ".mkv", ".avi", ".3gp",
}
CLASSES = {"reais": 0, "ia": 1}
MAX_SEGUNDOS_TREINO = 30.0


def calcular_eer(rotulos, scores):
    """Equal Error Rate: ponto em que falso positivo = falso negativo.

    E a metrica padrao do ASVspoof; diferente da acuracia, nao depende de um
    limiar escolhido e nao e inflada por classes desbalanceadas.
    Devolve (eer, limiar).
    """
    rotulos = np.asarray(rotulos).astype(int)
    scores = np.asarray(scores, dtype=np.float64)
    if rotulos.min() == rotulos.max():
        raise ValueError("EER precisa das duas classes no conjunto avaliado.")
    limiares = np.unique(scores)
    positivos = rotulos == 1
    fpr = np.array([np.mean(scores[~positivos] >= t) for t in limiares])
    fnr = np.array([np.mean(scores[positivos] < t) for t in limiares])
    i = int(np.argmin(np.abs(fpr - fnr)))
    return float((fpr[i] + fnr[i]) / 2), float(limiares[i])


def listar_dataset(pasta):
    """Devolve [(caminho, rotulo, grupo)] e valida a estrutura."""
    pasta = Path(pasta)
    itens = []
    for nome_classe, rotulo in CLASSES.items():
        raiz = pasta / nome_classe
        if not raiz.is_dir():
            raise FileNotFoundError(f"Pasta obrigatoria ausente: {raiz}")
        for arquivo in sorted(raiz.rglob("*")):
            if arquivo.is_file() and arquivo.suffix.lower() in EXTENSOES_MIDIA:
                relativo = arquivo.relative_to(raiz)
                grupo = f"{nome_classe}/{relativo.parts[0]}" if len(relativo.parts) > 1 else f"{nome_classe}/{arquivo.stem}"
                itens.append((arquivo, rotulo, grupo))
    return itens


def _extrair_um(item):
    """Extrai as caracteristicas de um arquivo. Devolve (linha, None) ou (None, falha)."""
    caminho, rotulo, grupo = item
    try:
        amostras, taxa = carregar_audio(caminho, max_segundos=MAX_SEGUNDOS_TREINO)
        caracteristicas, qualidade = extrair_caracteristicas(amostras, taxa)
    except (AudioAusente, ValueError, FileNotFoundError) as exc:
        return None, {"arquivo": str(caminho), "erro": str(exc)}
    if not qualidade["suficiente"]:
        return None, {"arquivo": str(caminho), "erro": "audio curto ou so silencio"}
    return {"arquivo": str(caminho), "rotulo": rotulo, "grupo": grupo, **caracteristicas}, None


def gerar_tabela(pasta, csv_saida=None, avisar=print, processos=1):
    """Extrai caracteristicas de todo o dataset. Arquivos ilegiveis sao pulados e listados.

    processos > 1 divide os arquivos entre varios processos (a extracao e so CPU).
    """
    itens = listar_dataset(pasta)
    linhas, falhas = [], []
    if processos and processos > 1:
        from concurrent.futures import ProcessPoolExecutor

        with ProcessPoolExecutor(max_workers=processos) as executor:
            resultados = executor.map(_extrair_um, itens, chunksize=8)
            resultados = list(resultados)
    else:
        resultados = map(_extrair_um, itens)
    for linha, falha in resultados:
        if falha:
            falhas.append(falha)
            avisar(f"[pulado] {Path(falha['arquivo']).name}: {falha['erro']}")
        else:
            linhas.append(linha)

    if csv_saida and linhas:
        csv_saida = Path(csv_saida)
        csv_saida.parent.mkdir(parents=True, exist_ok=True)
        with open(csv_saida, "w", newline="", encoding="utf-8") as arquivo:
            escritor = csv.DictWriter(arquivo, fieldnames=list(linhas[0].keys()))
            escritor.writeheader()
            escritor.writerows(linhas)
    return linhas, falhas


def treinar(linhas, destino=ARQUIVO_MODELO, fracao_teste=0.3, semente=42):
    """Treina Regressao Logistica e Random Forest; salva o de menor EER no teste."""
    import joblib
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import accuracy_score, roc_auc_score
    from sklearn.model_selection import GroupShuffleSplit
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    if not linhas:
        raise ValueError("Nenhum audio valido para treinar.")
    colunas = [c for c in linhas[0] if c not in ("arquivo", "rotulo", "grupo")]
    x = np.array([[linha[c] for c in colunas] for linha in linhas], dtype=np.float64)
    y = np.array([linha["rotulo"] for linha in linhas], dtype=int)
    grupos = np.array([linha["grupo"] for linha in linhas])

    for rotulo, nome in ((0, "reais"), (1, "ia")):
        n_grupos = len(set(grupos[y == rotulo]))
        if n_grupos < 2:
            raise ValueError(
                f"A classe '{nome}' precisa de pelo menos 2 arquivos (ou 2 subpastas) para "
                f"separar treino e teste; tem {n_grupos}."
            )

    # Sorteia divisoes por grupo ate as duas classes aparecerem nos dois lados.
    divisor = GroupShuffleSplit(n_splits=50, test_size=fracao_teste, random_state=semente)
    for idx_treino, idx_teste in divisor.split(x, y, grupos):
        if len(set(y[idx_treino])) == 2 and len(set(y[idx_teste])) == 2:
            break
    else:
        raise ValueError("Nao foi possivel dividir treino/teste com as duas classes; junte mais dados.")

    candidatos = {
        "regressao_logistica": make_pipeline(
            StandardScaler(), LogisticRegression(max_iter=2000, class_weight="balanced")
        ),
        "random_forest": RandomForestClassifier(
            n_estimators=300, class_weight="balanced", random_state=semente, n_jobs=1
        ),
    }
    desempenho = {}
    for nome, modelo in candidatos.items():
        modelo.fit(x[idx_treino], y[idx_treino])
        scores = modelo.predict_proba(x[idx_teste])[:, 1]
        eer, limiar = calcular_eer(y[idx_teste], scores)
        desempenho[nome] = {
            "eer": round(eer, 4),
            "limiar_eer": round(limiar, 4),
            "auc": round(float(roc_auc_score(y[idx_teste], scores)), 4),
            "acuracia_0_5": round(float(accuracy_score(y[idx_teste], scores >= 0.5)), 4),
        }

    melhor = min(desempenho, key=lambda n: (desempenho[n]["eer"], -desempenho[n]["auc"]))
    # Reajusta o vencedor com todos os dados: o teste ja cumpriu o papel de escolher.
    final = candidatos[melhor].fit(x, y)
    pacote = {
        "modelo": final,
        "nome": melhor,
        "colunas": colunas,
        "limiar": desempenho[melhor]["limiar_eer"],
        "desempenho_teste": desempenho,
        "n_treino": int(len(idx_treino)),
        "n_teste": int(len(idx_teste)),
        "n_total": int(len(y)),
        "treinado_em": datetime.now().isoformat(timespec="seconds"),
    }
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pacote, destino)
    return pacote


def carregar_modelo(caminho=ARQUIVO_MODELO):
    """Devolve o pacote salvo por treinar(), ou None se ainda nao houver modelo."""
    caminho = Path(caminho)
    if not caminho.is_file():
        return None
    import joblib

    pacote = joblib.load(caminho)
    if not isinstance(pacote, dict) or "modelo" not in pacote or "colunas" not in pacote:
        raise ValueError(f"Arquivo de modelo invalido: {caminho}")
    return pacote


def main():
    parser = argparse.ArgumentParser(description="Treina o classificador de audio do AIDA.")
    parser.add_argument("dataset", type=Path, help="pasta com subpastas reais/ e ia/")
    parser.add_argument("--csv", type=Path, default=None, help="onde salvar a tabela de caracteristicas")
    parser.add_argument("--destino", type=Path, default=ARQUIVO_MODELO)
    parser.add_argument("--processos", type=int, default=1, help="processos em paralelo na extracao")
    args = parser.parse_args()

    linhas, falhas = gerar_tabela(
        args.dataset, args.csv or args.dataset / "caracteristicas_audio.csv", processos=args.processos
    )
    print(f"{len(linhas)} audios validos, {len(falhas)} pulados.")
    pacote = treinar(linhas, args.destino)
    print(f"Modelo escolhido: {pacote['nome']} -> {args.destino}")
    print(json.dumps(pacote["desempenho_teste"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
