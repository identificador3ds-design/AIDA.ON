import cv2
import numpy as np

from utils_imagem import carregar_imagem_rgb, limpar_metricas


def extrair_metricas_laplaciano_dog_tsr(gray):
    """Extrai métricas de Laplaciano, DoG e resíduos direcionais (TSR)."""
    metricas = {}

    laplaciano = cv2.Laplacian(gray, cv2.CV_64F)
    laplaciano_abs = np.abs(laplaciano)
    _, laplaciano_forte = cv2.threshold(
        laplaciano_abs,
        30,
        255,
        cv2.THRESH_BINARY,
    )

    metricas["laplaciano_media"] = float(np.mean(laplaciano_abs))
    metricas["laplaciano_desvio"] = float(np.std(laplaciano_abs))
    metricas["laplaciano_variancia"] = float(np.var(laplaciano_abs))
    metricas["laplaciano_maximo"] = float(np.max(laplaciano_abs))
    metricas["laplaciano_pixels_fortes"] = float(
        np.sum(laplaciano_forte > 0) / laplaciano_forte.size
    )

    gray_float = gray.astype(np.float32)
    blur_narrow = cv2.GaussianBlur(gray_float, (3, 3), 0)
    blur_wide = cv2.GaussianBlur(gray_float, (15, 15), 0)
    dog_abs = np.abs(blur_narrow - blur_wide)
    limite_dog = np.mean(dog_abs) + np.std(dog_abs)

    metricas["dog_media"] = float(np.mean(dog_abs))
    metricas["dog_desvio"] = float(np.std(dog_abs))
    metricas["dog_variancia"] = float(np.var(dog_abs))
    metricas["dog_maximo"] = float(np.max(dog_abs))
    metricas["dog_energia"] = float(np.mean(dog_abs**2))
    metricas["dog_pixels_fortes"] = float(
        np.sum(dog_abs > limite_dog) / dog_abs.size
    )

    kernels = {
        "0": np.array([[0, 0, 0], [1, -2, 1], [0, 0, 0]], dtype=np.float32),
        "45": np.array([[0, 0, 1], [0, -2, 0], [1, 0, 0]], dtype=np.float32),
        "90": np.array([[0, 1, 0], [0, -2, 0], [0, 1, 0]], dtype=np.float32),
        "135": np.array([[1, 0, 0], [0, -2, 0], [0, 0, 1]], dtype=np.float32),
    }
    residuos_angulos = {}

    for angulo, kernel in kernels.items():
        residuo = cv2.filter2D(gray_float, cv2.CV_32F, kernel)
        residuo_abs = np.abs(residuo)
        residuos_angulos[angulo] = residuo_abs
        metricas[f"tsr_media_{angulo}"] = float(np.mean(residuo_abs))
        metricas[f"tsr_desvio_{angulo}"] = float(np.std(residuo_abs))
        metricas[f"tsr_energia_{angulo}"] = float(np.mean(residuo_abs**2))

    medias_angulos = [metricas[f"tsr_media_{angulo}"] for angulo in kernels]
    mean_residual = np.mean(list(residuos_angulos.values()), axis=0)

    metricas["tsr_media_geral"] = float(np.mean(mean_residual))
    metricas["tsr_desvio_geral"] = float(np.std(mean_residual))
    metricas["tsr_energia_geral"] = float(np.mean(mean_residual**2))
    metricas["tsr_diferenca_angulos"] = float(
        np.max(medias_angulos) - np.min(medias_angulos)
    )
    metricas["tsr_variacao_angulos"] = float(np.std(medias_angulos))

    return limpar_metricas(metricas)


def extrair_laplaciano_dog_tsr(caminho_imagem):
    """Carrega uma imagem e extrai as métricas dos três métodos."""
    rgb = carregar_imagem_rgb(caminho_imagem)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    return extrair_metricas_laplaciano_dog_tsr(gray)
