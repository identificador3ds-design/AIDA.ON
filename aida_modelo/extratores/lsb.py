import numpy as np

from config import PARAMETROS_EXTRATORES
from utils_imagem import carregar_imagem_rgb, estatisticas, limpar_metricas


def _entropia_bits(bits):
    p1 = float(np.mean(bits))
    p0 = 1.0 - p1
    ent = 0.0
    for p in (p0, p1):
        if p > 0:
            ent -= p * np.log2(p)
    return ent


def _corr(a, b):
    a = a.astype(float).ravel()
    b = b.astype(float).ravel()
    if a.size < 2 or np.std(a) == 0 or np.std(b) == 0:
        return 0.0
    return float(np.corrcoef(a, b)[0, 1])


def extrair_lsb(caminho_imagem):
    rgb = carregar_imagem_rgb(caminho_imagem)
    bits = (rgb.astype(np.uint8) & 1).astype(np.uint8)
    nomes = ["r", "g", "b"]
    metricas = {}

    for i, nome in enumerate(nomes):
        canal = bits[:, :, i]
        p1 = float(np.mean(canal))
        metricas[f"lsb_{nome}_proporcao_bits_1"] = p1
        metricas[f"lsb_{nome}_uniformidade"] = 1.0 - abs(p1 - 0.5) * 2
        metricas[f"lsb_{nome}_entropia"] = _entropia_bits(canal)
        metricas[f"lsb_{nome}_corr_horizontal"] = _corr(canal[:, :-1], canal[:, 1:])
        metricas[f"lsb_{nome}_corr_vertical"] = _corr(canal[:-1, :], canal[1:, :])

    geral = bits.ravel()
    metricas["lsb_proporcao_bits_1"] = float(np.mean(geral))
    metricas["lsb_uniformidade"] = 1.0 - abs(metricas["lsb_proporcao_bits_1"] - 0.5) * 2
    metricas["lsb_entropia"] = _entropia_bits(geral)

    n = PARAMETROS_EXTRATORES["lsb_blocos"]
    h, w, _ = bits.shape
    proporcoes, entropias, uniformidades = [], [], []
    for by in range(n):
        for bx in range(n):
            y0, y1 = int(by * h / n), int((by + 1) * h / n)
            x0, x1 = int(bx * w / n), int((bx + 1) * w / n)
            bloco = bits[y0:y1, x0:x1, :].ravel()
            p1 = float(np.mean(bloco)) if bloco.size else 0.0
            ent = _entropia_bits(bloco) if bloco.size else 0.0
            uni = 1.0 - abs(p1 - 0.5) * 2
            idx = by * n + bx + 1
            metricas[f"lsb_bloco_{idx:02d}_proporcao_bits_1"] = p1
            metricas[f"lsb_bloco_{idx:02d}_entropia"] = ent
            proporcoes.append(p1)
            entropias.append(ent)
            uniformidades.append(uni)

    metricas.update(estatisticas("lsb_blocos_proporcao_bits_1", proporcoes))
    metricas.update(estatisticas("lsb_blocos_entropia", entropias))
    metricas.update(estatisticas("lsb_blocos_uniformidade", uniformidades))
    return limpar_metricas(metricas)
