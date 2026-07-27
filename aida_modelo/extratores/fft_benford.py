import cv2
import numpy as np

from utils_imagem import carregar_imagem_rgb, imagem_cinza_float, limpar_metricas


def _benford_probs():
    digitos = np.arange(1, 10)
    return np.log10(1 + 1 / digitos)


def _primeiros_digitos(valores):
    valores = np.abs(np.asarray(valores, dtype=np.float64)).ravel()
    valores = valores[np.isfinite(valores) & (valores > 0)]
    if valores.size == 0:
        return np.array([], dtype=int)
    logs = np.floor(np.log10(valores))
    normalizados = valores / np.power(10, logs)
    return np.floor(normalizados).astype(int)


def metricas_benford(valores, prefixo):
    digitos = _primeiros_digitos(valores)
    esperado = _benford_probs()
    if digitos.size == 0:
        observado = np.zeros(9)
    else:
        observado = np.array([(digitos == d).mean() for d in range(1, 10)])
    mae = np.mean(np.abs(observado - esperado))
    rmse = np.sqrt(np.mean((observado - esperado) ** 2))
    corr = np.corrcoef(observado, esperado)[0, 1] if np.std(observado) > 0 else 0.0
    dados = {
        f"{prefixo}_benford_mae": mae,
        f"{prefixo}_benford_rmse": rmse,
        f"{prefixo}_benford_correlacao": corr,
        f"{prefixo}_benford_chi2": np.sum(((observado - esperado) ** 2) / (esperado + 1e-12)),
    }
    for i, valor in enumerate(observado, start=1):
        dados[f"{prefixo}_benford_digito_{i}"] = valor
    return limpar_metricas(dados)


def _perfil_radial(magnitude):
    h, w = magnitude.shape
    y, x = np.indices((h, w))
    centro_y, centro_x = h // 2, w // 2
    r = np.sqrt((x - centro_x) ** 2 + (y - centro_y) ** 2).astype(int)
    soma = np.bincount(r.ravel(), magnitude.ravel())
    contagem = np.bincount(r.ravel())
    return soma / np.maximum(contagem, 1)


def extrair_fft_benford(caminho_imagem):
    rgb = carregar_imagem_rgb(caminho_imagem)
    gray = imagem_cinza_float(rgb)

    fft = np.fft.fftshift(np.fft.fft2(gray))
    magnitude = np.log1p(np.abs(fft))
    perfil = _perfil_radial(magnitude)
    total = float(np.sum(magnitude) + 1e-12)

    h, w = magnitude.shape
    y, x = np.indices((h, w))
    r = np.sqrt((x - w // 2) ** 2 + (y - h // 2) ** 2)
    r_norm = r / (np.max(r) + 1e-12)

    baixa = magnitude[r_norm < 0.15].sum() / total
    media = magnitude[(r_norm >= 0.15) & (r_norm < 0.45)].sum() / total
    alta = magnitude[r_norm >= 0.45].sum() / total
    freq_dom = r_norm.ravel()[np.argmax(magnitude.ravel())]

    eixo = np.arange(1, len(perfil) + 1)
    if len(perfil) > 3:
        slope = np.polyfit(np.log(eixo), np.log(perfil + 1e-12), 1)[0]
    else:
        slope = 0.0

    sobel_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    sobel_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    sobel = np.hypot(sobel_x, sobel_y)
    lap = cv2.Laplacian(gray, cv2.CV_64F)
    diff = np.diff(gray, axis=1)

    metricas = {
        "fft_energia_baixa": baixa,
        "fft_energia_media": media,
        "fft_energia_alta": alta,
        "fft_razao_alta_baixa": alta / (baixa + 1e-12),
        "fft_frequencia_dominante_norm": freq_dom,
        "fft_inclinacao_perfil_radial": slope,
        "fft_magnitude_media": np.mean(magnitude),
        "fft_magnitude_desvio": np.std(magnitude),
    }
    metricas.update(metricas_benford(magnitude, "fft"))
    metricas.update(metricas_benford(sobel, "sobel"))
    metricas.update(metricas_benford(lap, "laplaciano"))
    metricas.update(metricas_benford(diff, "diferenca_pixels"))
    return limpar_metricas(metricas)
