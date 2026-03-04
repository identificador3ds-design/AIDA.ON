import numpy as np
import cv2
import io
import base64
import matplotlib.pyplot as plt

def calcular_fft_espectro(imagem_cinza):
    f = np.fft.fft2(imagem_cinza)
    fshift = np.fft.fftshift(f)
    magnitude = np.abs(fshift)
    magnitude_log = np.log1p(magnitude)
    return fshift, magnitude, magnitude_log

def separar_regioes_frequencia(shape, raio):
    h, w = shape
    centro = (h // 2, w // 2)
    Y, X = np.ogrid[:h, :w]
    dist_centro = np.sqrt((X - centro[1])**2 + (Y - centro[0])**2)
    mascara_baixas = dist_centro <= raio
    return mascara_baixas, ~mascara_baixas

def calcular_metricas(magnitude, mascara):
    regiao = magnitude[mascara]
    return np.sum(regiao), np.sum(regiao**2)

def executar_analise_completa_fft(img_bytes):
    # Prepara imagem
    np_img = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(np_img, cv2.IMREAD_GRAYSCALE)
    
    # Processamento
    fshift, magnitude, magnitude_log = calcular_fft_espectro(img)
    h, w = img.shape
    raio = min(h, w) // 4
    _, masc_altas = separar_regioes_frequencia((h, w), raio)
    _, energia_altas = calcular_metricas(magnitude, masc_altas)

    # Gera gráfico
    plt.figure(figsize=(5, 5))
    plt.imshow(magnitude_log, cmap='gray')
    plt.axis('off')
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', pad_inches=0)
    buf.seek(0)
    plot_b64 = base64.b64encode(buf.read()).decode('utf-8')
    plt.close()

    prob = min(99.9, (energia_altas / 1e12) * 100) 
    
    return {
        "status": "sucesso",
        "imagem_fft": f"data:image/png;base64,{plot_b64}",
        "probabilidade": f"{prob:.1f}%",
        "energia": f"{energia_altas:.2e}",
        "metodo": "Análise de Frequência (FFT)"
    }