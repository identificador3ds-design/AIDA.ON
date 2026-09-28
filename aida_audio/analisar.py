"""AIDA Audio: analisa um audio (ou a trilha de um video) e devolve um indicio.

Tres estados, como no AIDA Core: REAL, IA/MANIPULADA e INCONCLUSIVO. O audio
cai em INCONCLUSIVO quando e curto demais, quase todo silencio, ou quando
ainda nao existe modelo treinado — nesse caso as caracteristicas sao
devolvidas mesmo assim, para inspecao.

Uso:
    python -m aida_audio.analisar audio.wav
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from .caracteristicas import extrair_caracteristicas
from .carregar import carregar_audio
from .modelo import ARQUIVO_MODELO, carregar_modelo

DURACAO_MINIMA_S = 1.0
FRACAO_SILENCIO_MAXIMA = 0.9
FRACAO_SATURADA_ALERTA = 0.01
# Faixa em torno do limiar onde o modelo nao decide.
MARGEM_INCONCLUSIVA = 0.10
MAX_SEGUNDOS_ANALISE = 120.0
RESSALVA = "Indício técnico, não prova. O modelo de áudio é uma linha de base em validação."


def _confianca(distancia):
    if distancia < 0.15:
        return "baixa"
    if distancia < 0.30:
        return "media"
    return "alta"


def analisar_amostras(amostras, taxa, pacote_modelo=None, caminho_modelo=ARQUIVO_MODELO):
    """Analisa um array ja decodificado. pacote_modelo=None carrega do disco."""
    caracteristicas, qualidade = extrair_caracteristicas(amostras, taxa)
    motivos, limitacoes = [], []

    if qualidade["duracao_s"] < DURACAO_MINIMA_S:
        motivos.append(f"áudio com menos de {DURACAO_MINIMA_S:g} s")
    if qualidade["fracao_silencio"] > FRACAO_SILENCIO_MAXIMA or not qualidade["suficiente"]:
        motivos.append("áudio quase todo em silêncio")
    if qualidade["fracao_saturada"] > FRACAO_SATURADA_ALERTA:
        limitacoes.append("áudio saturado (clipping): distorce as altas frequências")

    pacote = pacote_modelo if pacote_modelo is not None else carregar_modelo(caminho_modelo)
    resposta = {
        "resultado": "INCONCLUSIVO",
        "inconclusivo": True,
        "probabilidade_ia": None,
        "confianca": "baixa",
        "limiar": None,
        "modelo_disponivel": pacote is not None,
        "modelo_utilizado": pacote["nome"] if pacote else None,
        "motivos": motivos,
        "limitacoes": limitacoes,
        "qualidade": qualidade,
        "caracteristicas": caracteristicas,
        "ressalva": RESSALVA,
    }
    if pacote is None:
        motivos.append("nenhum modelo de áudio treinado (rode: python -m aida_audio.modelo <dataset>)")
        return resposta
    if motivos:
        return resposta

    faltando = [c for c in pacote["colunas"] if c not in caracteristicas]
    if faltando:
        raise ValueError(
            f"O modelo foi treinado com {len(faltando)} caracteristicas que este extrator nao gera "
            f"(ex.: {faltando[0]}). Treine o modelo de novo."
        )
    x = np.array([[caracteristicas[c] for c in pacote["colunas"]]], dtype=np.float64)
    prob_ia = float(pacote["modelo"].predict_proba(x)[0, 1])
    limiar = float(pacote.get("limiar", 0.5))
    distancia = abs(prob_ia - limiar)
    # Modelos calibrados nos videos trazem a propria faixa: [baixo, limiar) e
    # INCONCLUSIVO; o limiar fica alto para segurar o falso positivo.
    baixo, alto = pacote.get("faixa_inconclusiva") or (limiar - MARGEM_INCONCLUSIVA, limiar + MARGEM_INCONCLUSIVA)

    if prob_ia >= alto:
        resultado = "IA/MANIPULADA"
    elif prob_ia <= baixo:
        resultado = "REAL"
    else:
        resultado = "INCONCLUSIVO"
        motivos.append("probabilidade próxima do limiar de decisão")

    resposta.update(
        {
            "resultado": resultado,
            "inconclusivo": resultado == "INCONCLUSIVO",
            "probabilidade_ia": round(prob_ia, 4),
            "confianca": _confianca(distancia),
            "limiar": round(limiar, 4),
        }
    )
    return resposta


def analisar_audio(caminho, pacote_modelo=None, caminho_modelo=ARQUIVO_MODELO):
    amostras, taxa = carregar_audio(caminho, max_segundos=MAX_SEGUNDOS_ANALISE)
    resposta = analisar_amostras(amostras, taxa, pacote_modelo, caminho_modelo)
    resposta["arquivo"] = Path(caminho).name
    return resposta


def main():
    parser = argparse.ArgumentParser(description="Analisa um arquivo de audio com o AIDA Audio.")
    parser.add_argument("audio", type=Path)
    parser.add_argument("--modelo", type=Path, default=ARQUIVO_MODELO)
    parser.add_argument("--com-caracteristicas", action="store_true", help="inclui as ~200 caracteristicas na saida")
    args = parser.parse_args()
    resposta = analisar_audio(args.audio, caminho_modelo=args.modelo)
    if not args.com_caracteristicas:
        resposta.pop("caracteristicas")
    print(json.dumps(resposta, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
