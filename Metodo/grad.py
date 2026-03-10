# -*- coding: utf-8 -*-
"""
Filtro Laplaciano Estilizado (Neon)
Autor: Especialista em Visão Computacional

Descrição:
Aplica o operador Laplaciano para detectar bordas e
utiliza um colormap para criar o efeito visual semelhante
ao da imagem fornecida (azul/roxo/ciano).
"""

import cv2
import numpy as np
import matplotlib.pyplot as plt

# ------------------------------------------------------------
# 1. Carregar imagem
# ------------------------------------------------------------
caminho_imagem = 'copo2.png'
imagem = cv2.imread(caminho_imagem)

if imagem is None:
    print("Erro ao carregar imagem.")
    exit()

# ------------------------------------------------------------
# 2. Converter para escala de cinza
# ------------------------------------------------------------
imagem_cinza = cv2.cvtColor(imagem, cv2.COLOR_BGR2GRAY)

# ------------------------------------------------------------
# 3. Aplicar Laplaciano
# ------------------------------------------------------------
laplaciano = cv2.Laplacian(imagem_cinza, cv2.CV_64F, ksize=3)

# converter para 8 bits
laplaciano_abs = cv2.convertScaleAbs(laplaciano)

# ------------------------------------------------------------
# 4. Aumentar contraste das bordas
# ------------------------------------------------------------
laplaciano_norm = cv2.normalize(
    laplaciano_abs,
    None,
    0,
    255,
    cv2.NORM_MINMAX
)

# ------------------------------------------------------------
# 5. Aplicar colormap (efeito neon azul/roxo)
# ------------------------------------------------------------
gradiente_colorido = cv2.applyColorMap(
    laplaciano_norm,
    cv2.COLORMAP_TURBO   # gera azul, roxo e ciano
)

# ------------------------------------------------------------
# 6. Exibir resultado
# ------------------------------------------------------------
plt.figure(figsize=(10,5))

plt.subplot(1,2,1)
plt.imshow(cv2.cvtColor(imagem, cv2.COLOR_BGR2RGB))
plt.title("Imagem Original")
plt.axis("off")

plt.subplot(1,2,2)
plt.imshow(cv2.cvtColor(gradiente_colorido, cv2.COLOR_BGR2RGB))
plt.title("Gradiente Laplaciano Estilizado")
plt.axis("off")

plt.tight_layout()
plt.show()