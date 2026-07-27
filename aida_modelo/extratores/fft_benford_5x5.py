import numpy as np

from extratores.fft_benford import metricas_benford
from utils_imagem import carregar_imagem_rgb, estatisticas, imagem_cinza_float, limpar_metricas
from config import PARAMETROS_EXTRATORES


def _energia_alta_bloco(bloco):
    fft = np.fft.fftshift(np.fft.fft2(bloco))
    magnitude = np.log1p(np.abs(fft))
    h, w = bloco.shape
    y, x = np.indices((h, w))
    r = np.sqrt((x - w // 2) ** 2 + (y - h // 2) ** 2)
    r_norm = r / (np.max(r) + 1e-12)
    return float(magnitude[r_norm >= 0.45].sum() / (magnitude.sum() + 1e-12)), magnitude


def extrair_fft_benford_5x5(caminho_imagem):
    rgb = carregar_imagem_rgb(caminho_imagem)
    gray = imagem_cinza_float(rgb)
    n = PARAMETROS_EXTRATORES["fft_blocos"]
    h, w = gray.shape
    energias = []
    corrs = []
    metricas = {}

    for by in range(n):
        for bx in range(n):
            y0, y1 = int(by * h / n), int((by + 1) * h / n)
            x0, x1 = int(bx * w / n), int((bx + 1) * w / n)
            bloco = gray[y0:y1, x0:x1]
            if bloco.size < 16:
                energia, corr = 0.0, 0.0
            else:
                energia, magnitude = _energia_alta_bloco(bloco)
                corr = metricas_benford(magnitude, "tmp")["tmp_benford_correlacao"]
            idx = by * n + bx + 1
            energias.append(energia)
            corrs.append(corr)
            metricas[f"fft5x5_bloco_{idx:02d}_energia_alta"] = energia
            metricas[f"fft5x5_bloco_{idx:02d}_benford_correlacao"] = corr

    metricas.update(estatisticas("fft5x5_energia_alta", energias))
    metricas.update(estatisticas("fft5x5_benford_correlacao", corrs))
    metricas["fft5x5_energia_alta_amplitude"] = float(np.max(energias) - np.min(energias))
    metricas["fft5x5_benford_correlacao_amplitude"] = float(np.max(corrs) - np.min(corrs))
    return limpar_metricas(metricas)
