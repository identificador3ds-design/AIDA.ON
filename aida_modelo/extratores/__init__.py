from .fft_benford import extrair_fft_benford
from .fft_benford_5x5 import extrair_fft_benford_5x5
from .gradientes_textura import extrair_gradientes_textura
from .laplaciano_dog_tsr import extrair_laplaciano_dog_tsr
from .lsb import extrair_lsb


def extrair_todas_metricas(caminho_imagem):
    metricas = {}
    for extrator in (
        extrair_fft_benford,
        extrair_fft_benford_5x5,
        extrair_gradientes_textura,
        extrair_lsb,
        extrair_laplaciano_dog_tsr,
    ):
        metricas.update(extrator(caminho_imagem))
    return metricas
