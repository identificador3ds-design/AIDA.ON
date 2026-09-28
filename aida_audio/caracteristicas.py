"""Caracteristicas manuais de audio (Abordagem A da pesquisa).

Mesma receita do AIDA Image: extrair numeros interpretaveis, gravar em CSV e
treinar um classificador classico. Implementado so com numpy/scipy para nao
depender do librosa (e das dezenas de pacotes que ele puxa).

Grupos:
- MFCC (+ delta): envelope espectral na escala mel, que imita o ouvido;
- LFCC (+ delta): o mesmo com bancos LINEARES. Nos desafios ASVspoof o LFCC
  supera o MFCC porque nao comprime as altas frequencias, onde vocoders
  deixam mais artefatos;
- espectrais: centroide, largura de banda, rolloff, planura, fluxo e a razao
  de energia acima de 4 kHz;
- temporais: ZCR, RMS, fracao de silencio e de amostras saturadas.

Todas as funcoes devolvem SEMPRE o mesmo conjunto de chaves, inclusive para
silencio ou audio curto: o CSV de treino nao pode ter colunas que somem.
"""

from __future__ import annotations

import numpy as np
from scipy.fft import dct, rfft

JANELA_S = 0.025
PASSO_S = 0.010
N_FFT = 512
N_BANDAS = 40
N_COEFS = 20
PRE_ENFASE = 0.97
LIMIAR_SILENCIO_DB = -40.0  # relativo ao quadro mais forte
MIN_QUADROS = 3


def _quadros(sinal, taxa):
    tam = int(round(JANELA_S * taxa))
    passo = int(round(PASSO_S * taxa))
    if sinal.size < tam:
        sinal = np.pad(sinal, (0, tam - sinal.size))
    n = 1 + (sinal.size - tam) // passo
    indices = np.arange(tam)[None, :] + passo * np.arange(n)[:, None]
    return sinal[indices] * np.hamming(tam)[None, :]


def _hz_para_mel(hz):
    return 2595.0 * np.log10(1.0 + np.asarray(hz) / 700.0)


def _mel_para_hz(mel):
    return 700.0 * (10.0 ** (np.asarray(mel) / 2595.0) - 1.0)


def _banco_triangular(pontos_hz, taxa, n_fft=N_FFT):
    """Filtros triangulares com vertices em pontos_hz (n_bandas + 2 pontos)."""
    n_bins = n_fft // 2 + 1
    bins = np.floor((n_fft + 1) * np.asarray(pontos_hz) / taxa).astype(int)
    banco = np.zeros((len(pontos_hz) - 2, n_bins))
    for i in range(1, len(pontos_hz) - 1):
        # Em baixas frequencias da escala mel, bandas vizinhas caem no mesmo bin:
        # forca largura minima de 1 bin para nenhum filtro ficar zerado.
        esq = min(bins[i - 1], n_bins - 1)
        centro = max(bins[i], esq + 1)
        dir_ = max(bins[i + 1], centro + 1)
        subida = np.arange(esq, min(centro, n_bins))
        descida = np.arange(centro, min(dir_, n_bins))
        banco[i - 1, subida] = (subida - esq) / (centro - esq)
        banco[i - 1, descida] = (dir_ - descida) / (dir_ - centro)
    return banco


def banco_mel(taxa, n_bandas=N_BANDAS, n_fft=N_FFT):
    mels = np.linspace(_hz_para_mel(0), _hz_para_mel(taxa / 2), n_bandas + 2)
    return _banco_triangular(_mel_para_hz(mels), taxa, n_fft)


def banco_linear(taxa, n_bandas=N_BANDAS, n_fft=N_FFT):
    return _banco_triangular(np.linspace(0, taxa / 2, n_bandas + 2), taxa, n_fft)


def _cepstrais(potencia, banco):
    energia = np.maximum(potencia @ banco.T, 1e-10)
    return dct(np.log(energia), type=2, axis=1, norm="ortho")[:, :N_COEFS]


def _delta(coefs, n=2):
    """Derivada temporal por regressao (formula do HTK)."""
    if coefs.shape[0] < 2:
        return np.zeros_like(coefs)
    pad = np.pad(coefs, ((n, n), (0, 0)), mode="edge")
    denominador = 2 * sum(i * i for i in range(1, n + 1))
    return sum(
        i * (pad[n + i : n + i + coefs.shape[0]] - pad[n - i : n - i + coefs.shape[0]])
        for i in range(1, n + 1)
    ) / denominador


def _resumo(prefixo, matriz):
    """Media e desvio por coluna -> {prefixo_00_media: ..., prefixo_00_desvio: ...}."""
    saida = {}
    media = matriz.mean(axis=0)
    desvio = matriz.std(axis=0)
    for i in range(matriz.shape[1]):
        saida[f"{prefixo}_{i:02d}_media"] = float(media[i])
        saida[f"{prefixo}_{i:02d}_desvio"] = float(desvio[i])
    return saida


def _stats(prefixo, valores):
    valores = np.asarray(valores, dtype=np.float64)
    return {
        f"{prefixo}_media": float(np.mean(valores)),
        f"{prefixo}_desvio": float(np.std(valores)),
        f"{prefixo}_p10": float(np.percentile(valores, 10)),
        f"{prefixo}_p90": float(np.percentile(valores, 90)),
    }


def extrair_caracteristicas(amostras, taxa):
    """Devolve (caracteristicas: dict[str, float], qualidade: dict)."""
    sinal = np.asarray(amostras, dtype=np.float64).reshape(-1)
    sinal = np.nan_to_num(sinal)
    duracao = sinal.size / taxa if taxa else 0.0
    saturadas = float(np.mean(np.abs(sinal) >= 0.999)) if sinal.size else 0.0

    # Remove DC; a pre-enfase realca as altas frequencias antes da analise.
    sinal = sinal - (sinal.mean() if sinal.size else 0.0)
    enfatizado = np.append(sinal[:1], sinal[1:] - PRE_ENFASE * sinal[:-1]) if sinal.size else sinal

    quadros_brutos = _quadros(sinal, taxa)
    quadros = _quadros(enfatizado, taxa)
    rms = np.sqrt(np.mean(quadros_brutos**2, axis=1))
    rms_db = 20 * np.log10(np.maximum(rms, 1e-10))
    ativos = rms_db > (rms_db.max() + LIMIAR_SILENCIO_DB)
    # Silencio absoluto (tudo -200 dB) tambem conta como inativo.
    ativos &= rms > 1e-5
    fracao_silencio = float(1.0 - ativos.mean()) if ativos.size else 1.0

    qualidade = {
        "duracao_s": round(duracao, 3),
        "taxa_amostragem": int(taxa),
        "fracao_silencio": round(fracao_silencio, 4),
        "fracao_saturada": round(saturadas, 5),
        "quadros_ativos": int(ativos.sum()),
        "suficiente": bool(ativos.sum() >= MIN_QUADROS),
    }

    # Com poucos quadros de fala, usa todos para nao devolver estatisticas vazias.
    selecao = ativos if ativos.sum() >= MIN_QUADROS else np.ones_like(ativos)
    quadros = quadros[selecao]
    quadros_brutos = quadros_brutos[selecao]
    rms = rms[selecao]

    espectro = np.abs(rfft(quadros, n=N_FFT, axis=1))
    potencia = (espectro**2) / N_FFT
    freqs = np.linspace(0, taxa / 2, potencia.shape[1])

    mfcc = _cepstrais(potencia, banco_mel(taxa))
    lfcc = _cepstrais(potencia, banco_linear(taxa))

    soma = np.maximum(potencia.sum(axis=1), 1e-12)
    centroide = (potencia @ freqs) / soma
    largura = np.sqrt(((freqs[None, :] - centroide[:, None]) ** 2 * potencia).sum(axis=1) / soma)
    acumulado = np.cumsum(potencia, axis=1)
    rolloff = freqs[np.argmax(acumulado >= 0.85 * acumulado[:, -1:], axis=1)]
    planura = np.exp(np.mean(np.log(np.maximum(potencia, 1e-12)), axis=1)) / np.maximum(
        potencia.mean(axis=1), 1e-12
    )
    normalizado = espectro / np.maximum(espectro.sum(axis=1, keepdims=True), 1e-12)
    fluxo = (
        np.sqrt((np.diff(normalizado, axis=0) ** 2).sum(axis=1))
        if normalizado.shape[0] > 1
        else np.zeros(1)
    )
    razao_alta = potencia[:, freqs >= 4000].sum(axis=1) / soma
    zcr = np.mean(np.abs(np.diff(np.sign(quadros_brutos), axis=1)) > 0, axis=1)

    caracteristicas = {}
    caracteristicas.update(_resumo("mfcc", mfcc))
    caracteristicas.update(_resumo("mfcc_delta", _delta(mfcc)))
    caracteristicas.update(_resumo("lfcc", lfcc))
    caracteristicas.update(_resumo("lfcc_delta", _delta(lfcc)))
    caracteristicas.update(_stats("centroide_hz", centroide))
    caracteristicas.update(_stats("largura_banda_hz", largura))
    caracteristicas.update(_stats("rolloff85_hz", rolloff))
    caracteristicas.update(_stats("planura", planura))
    caracteristicas.update(_stats("fluxo", fluxo))
    caracteristicas.update(_stats("razao_acima_4khz", razao_alta))
    caracteristicas.update(_stats("zcr", zcr))
    caracteristicas.update(_stats("rms_db", 20 * np.log10(np.maximum(rms, 1e-10))))
    caracteristicas["fracao_silencio"] = fracao_silencio
    caracteristicas["fracao_saturada"] = saturadas

    # Nada de NaN/inf no CSV: o imputer do treino aceitaria, mas mascararia bug.
    caracteristicas = {k: (float(v) if np.isfinite(v) else 0.0) for k, v in caracteristicas.items()}
    return caracteristicas, qualidade
