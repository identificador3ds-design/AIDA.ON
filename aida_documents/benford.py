"""Lei de Benford no primeiro digito dos valores de um documento.

Tres medidas de aderencia, porque nenhuma sozinha e confiavel em amostra pequena:
- MSE: media dos erros quadraticos por digito (a mesma do extrator de imagem);
- MAD de Nigrini, com as faixas empiricas 0,006 / 0,012 / 0,015;
- qui-quadrado com 8 graus de liberdade (p-valor), que so faz sentido com N moderado.

Uma nota fiscal tem poucas dezenas de valores. Abaixo de N_MINIMO a analise e
devolvida para inspecao, mas marcada como insuficiente e nao pesa na decisao.
"""

from __future__ import annotations

import math

import numpy as np

BENFORD = np.log10(1 + 1 / np.arange(1, 10))
N_MINIMO = 50
N_RECOMENDADO = 300
# Nigrini (2012), primeiro digito.
MAD_FAIXAS = ((0.006, "conformidade próxima"), (0.012, "conformidade aceitável"), (0.015, "conformidade marginal"))


def primeiros_digitos(valores):
    v = np.abs(np.asarray(valores, dtype=np.float64)).ravel()
    v = v[np.isfinite(v) & (v > 0)]
    if v.size == 0:
        return np.array([], dtype=int)
    return np.floor(v / np.power(10.0, np.floor(np.log10(v)))).astype(int).clip(1, 9)


def _p_valor_qui2(estatistica, gl=8):
    # Sobrevivencia da qui-quadrado com gl par, sem scipy: e^(-x/2) * sum (x/2)^k / k!
    x = estatistica / 2.0
    termo, soma = 1.0, 1.0
    for k in range(1, gl // 2):
        termo *= x / k
        soma += termo
    return float(min(1.0, math.exp(-x) * soma))


def analisar_benford(valores):
    digitos = primeiros_digitos(valores)
    n = int(digitos.size)
    observado = np.bincount(digitos, minlength=10)[1:] / n if n else np.zeros(9)
    desvio = observado - BENFORD
    mad = float(np.mean(np.abs(desvio)))
    qui2 = float(n * np.sum(desvio**2 / BENFORD)) if n else 0.0
    faixa = next((nome for limite, nome in MAD_FAIXAS if mad <= limite), "não conforme")
    return {
        "n": n,
        "suficiente": n >= N_MINIMO,
        "mse": float(np.mean(desvio**2)),
        "mad": mad,
        "faixa_mad": faixa,
        # MAD esperado se os dados seguissem Benford, so pelo tamanho da amostra.
        "mad_esperado_ao_acaso": float(np.mean(np.sqrt(2 / np.pi * BENFORD * (1 - BENFORD) / n))) if n else None,
        "qui2": qui2,
        "p_valor": _p_valor_qui2(qui2) if n else None,
        "observado": [float(x) for x in observado],
        "esperado": [float(x) for x in BENFORD],
    }
