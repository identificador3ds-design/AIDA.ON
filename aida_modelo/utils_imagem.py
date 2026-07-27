from pathlib import Path

import cv2
import numpy as np
import pillow_heif
from PIL import Image


pillow_heif.register_heif_opener()
from PIL import Image, ImageOps, UnidentifiedImageError

from config import EXTENSOES_ACEITAS, PARAMETROS_EXTRATORES, TAMANHO_MAX_BYTES, TAMANHO_MAX_MB

try:
    from pillow_heif import register_heif_opener, register_avif_opener

    register_heif_opener()
    register_avif_opener()
except Exception:
    pass


def validar_arquivo_imagem(caminho):
    caminho = Path(caminho)
    if not caminho.exists():
        raise FileNotFoundError(f"Imagem não encontrada: {caminho}")
    if caminho.suffix.lower() not in EXTENSOES_ACEITAS:
        raise ValueError(f"Formato inválido. Use: {', '.join(sorted(EXTENSOES_ACEITAS))}")
    if caminho.stat().st_size > TAMANHO_MAX_BYTES:
        raise ValueError(f"A imagem ultrapassa o limite de {TAMANHO_MAX_MB} MB.")
    return caminho


def listar_imagens(pasta):
    pasta = Path(pasta)
    if not pasta.exists():
        return []
    return sorted(
        [p for p in pasta.rglob("*") if p.is_file() and p.suffix.lower() in EXTENSOES_ACEITAS]
    )


def carregar_imagem_rgb(caminho):
    caminho = validar_arquivo_imagem(caminho)
    try:
        with Image.open(caminho) as img:
            img = ImageOps.exif_transpose(img).convert("RGB")
            limite = PARAMETROS_EXTRATORES["imagem_tamanho_max_processamento"]
            img.thumbnail((limite, limite), Image.Resampling.LANCZOS)
            return np.array(img)
    except UnidentifiedImageError as exc:
        raise ValueError(
            "Não foi possível ler a imagem. Verifique se o arquivo não está corrompido "
            "e se as bibliotecas para HEIC/AVIF foram instaladas."
        ) from exc
    except Exception as exc:
        raise ValueError(f"Erro ao carregar imagem: {exc}") from exc


def imagem_cinza_float(rgb):
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    return gray.astype(np.float64) / 255.0


def estatisticas(prefixo, valores):
    arr = np.asarray(valores, dtype=np.float64)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        arr = np.array([0.0])
    return {
        f"{prefixo}_media": float(np.mean(arr)),
        f"{prefixo}_desvio": float(np.std(arr)),
        f"{prefixo}_min": float(np.min(arr)),
        f"{prefixo}_max": float(np.max(arr)),
        f"{prefixo}_mediana": float(np.median(arr)),
    }


def limpar_metricas(metricas):
    limpas = {}
    for chave, valor in metricas.items():
        try:
            numero = float(valor)
            if not np.isfinite(numero):
                numero = 0.0
            limpas[chave] = numero
        except Exception:
            limpas[chave] = 0.0
    return limpas
