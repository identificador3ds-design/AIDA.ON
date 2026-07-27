import cv2
import numpy as np

from config import PARAMETROS_EXTRATORES
from utils_imagem import carregar_imagem_rgb, imagem_cinza_float, limpar_metricas


def extrair_gradientes_textura(caminho_imagem):
    rgb = carregar_imagem_rgb(caminho_imagem)
    gray = imagem_cinza_float(rgb)

    sobel_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    sobel_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    grad = np.hypot(sobel_x, sobel_y)
    lap = cv2.Laplacian(gray, cv2.CV_64F)

    blur = cv2.GaussianBlur(gray, (0, 0), sigmaX=2.0)
    alta_freq = gray - blur
    janela = PARAMETROS_EXTRATORES["janela_desvio_local"]
    media = cv2.blur(gray, (janela, janela))
    media2 = cv2.blur(gray * gray, (janela, janela))
    desvio_local = np.sqrt(np.maximum(media2 - media * media, 0))

    limiar = np.percentile(grad, PARAMETROS_EXTRATORES["limiar_bordas_percentil"])
    bordas = grad >= limiar

    orientacao = np.arctan2(sobel_y, sobel_x)
    coerencia = np.abs(np.mean(np.exp(1j * orientacao)))
    continuidade = 1.0 - (np.std(np.diff(grad, axis=1)) + np.std(np.diff(grad, axis=0))) / (
        np.mean(grad) + 1e-12
    )

    metricas = {
        "gradiente_medio": np.mean(grad),
        "gradiente_desvio": np.std(grad),
        "gradiente_p90": np.percentile(grad, 90),
        "gradiente_p95": np.percentile(grad, 95),
        "gradiente_p99": np.percentile(grad, 99),
        "laplaciano_medio": np.mean(np.abs(lap)),
        "laplaciano_desvio": np.std(lap),
        "laplaciano_variancia": np.var(lap),
        "rugosidade": np.mean(np.abs(gray - blur)),
        "alta_frequencia_media": np.mean(np.abs(alta_freq)),
        "alta_frequencia_desvio": np.std(alta_freq),
        "densidade_bordas": np.mean(bordas),
        "desvio_local_medio": np.mean(desvio_local),
        "desvio_local_desvio": np.std(desvio_local),
        "coerencia": coerencia,
        "continuidade": continuidade,
        "contraste_global": np.std(gray),
    }
    return limpar_metricas(metricas)
