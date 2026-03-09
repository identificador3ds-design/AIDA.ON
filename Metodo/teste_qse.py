import cv2
import numpy as np
import matplotlib.pyplot as plt

def analisar_fisica_imagem(img_bytes):
    # Converte bytes para formato que o OpenCV entende
    nparr = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.CV_16U if img_bytes is None else cv2.IMREAD_COLOR)
    
    if img is None:
        return None

    # Converte para RGB (exibição) e escala de cinza (análise)
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 1. Análise de Luz (média dos pixels)
    luz_score = np.mean(gray) / 255.0

    # 2. Análise de Geometria (linhas de Hough)
    edges = cv2.Canny(gray, 50, 150)
    lines = cv2.HoughLines(edges, 1, np.pi/180, 200)
    geo_score = (len(lines) / 100.0) if lines is not None else 0.05
    geo_score = min(geo_score, 1.0)  # limita a 1.0

    # 3. Análise de Continuidade (variância do Laplaciano)
    laplacian = cv2.Laplacian(gray, cv2.CV_64F).var()
    cont_score = min(laplacian / 500.0, 1.0)

    # 4. Análise de Fourier (corte de altas frequências)
    fourier_score = analisar_fourier(gray)

    # --- Ponderação dos scores ---
    peso_luz = 0.15
    peso_geo = 0.5
    peso_cont = 0.15
    peso_fourier = 0.2

    score_final = (luz_score * peso_luz +
                   geo_score * peso_geo +
                   cont_score * peso_cont +
                   fourier_score * peso_fourier)

    return (luz_score, geo_score, cont_score, fourier_score, score_final)


def analisar_fourier(gray):
    """
    Calcula a proporção de energia nas altas frequências da imagem.
    Retorna um score entre 0 (muito borrada) e 1 (nítida).
    """
    h, w = gray.shape

    # Janela de Hamming para minimizar artefatos de borda
    window = np.outer(np.hamming(h), np.hamming(w))
    img_windowed = gray * window

    # FFT e deslocamento
    f = np.fft.fft2(img_windowed)
    fshift = np.fft.fftshift(f)
    magnitude = np.abs(fshift)

    # Coordenadas de frequência (distância do centro)
    crow, ccol = h // 2, w // 2
    Y, X = np.ogrid[:h, :w]
    dist = np.sqrt((Y - crow)**2 + (X - ccol)**2)

    # Raio máximo até a borda
    max_radius = min(crow, ccol)
    # Limiar para considerar "altas frequências" (70% do raio máximo)
    high_thresh = 0.7 * max_radius

    # Energia total (soma dos quadrados das magnitudes)
    total_energy = np.sum(magnitude**2)
    if total_energy == 0:
        return 0.0

    # Energia nas altas frequências (fora do círculo de raio high_thresh)
    mask_high = dist > high_thresh
    high_energy = np.sum(magnitude[mask_high]**2)

    # Proporção de energia em altas frequências
    high_freq_ratio = high_energy / total_energy

    # Mapeia a razão para um score entre 0 e 1
    # Valores típicos: imagens nítidas ~0.2-0.3, borradas <0.05
    score = min(high_freq_ratio * 5, 1.0)  # fator empírico
    return score


def exibir_resultado_estilo_referencia(stats, img_original):
    """
    Exibe a imagem original e as métricas calculadas, com veredito.
    """
    if stats is None:
        print("Erro: Dados insuficientes para exibir.")
        return

    luz, geo, cont, fourier, score = stats

    # Lógica de veredito (ajustada para os novos pesos)
    is_fake = score < 0.4 or score > 0.8
    veredito = "FALSA" if is_fake else "REAL"
    probabilidade = 90.1 if is_fake else 95.4  # valor ilustrativo

    # Cria figura com dois subplots
    fig, (ax_img, ax_txt) = plt.subplots(1, 2, figsize=(14, 5))

    # --- Imagem original ---
    ax_img.imshow(img_original)
    ax_img.set_title("Imagem Original", fontsize=12, pad=10)
    ax_img.axis('off')

    # --- Painel de métricas ---
    ax_txt.set_facecolor('white')
    ax_txt.axis('off')

    cor_texto = '#A51C30'  # vermelho escuro
    params = {'fontsize': 14, 'color': cor_texto, 'fontname': 'sans-serif'}

    y_start = 0.9
    step = 0.08
    ax_txt.text(0.1, y_start, "🔍 Análise Foto:", weight='bold', fontsize=16, color=cor_texto)
    ax_txt.text(0.1, y_start - step, f"Luz: {luz:.5f}", **params)
    ax_txt.text(0.1, y_start - 2*step, f"Geo: {geo:.5f}", **params)
    ax_txt.text(0.1, y_start - 3*step, f"Cont: {cont:.5f}", **params)
    ax_txt.text(0.1, y_start - 4*step, f"Fourier: {fourier:.5f}", **params)
    ax_txt.text(0.1, y_start - 5*step, f"Score: {score:.5f}", weight='bold', **params)

    ax_txt.text(0.1, y_start - 7*step, f"🚨 {veredito} ({probabilidade}%)",
                weight='bold', fontsize=20, color=cor_texto)

    plt.tight_layout()
    plt.show()


# --- EXECUÇÃO ---
if __name__ == "__main__":
    caminho = '4.png'  # Insira aqui o caminho da imagem
    resultados, imagem_carregada = analisar_fisica_imagem(caminho)

    if resultados:
        exibir_resultado_estilo_referencia(resultados, imagem_carregada)
    else:
        print("Erro: Não foi possível carregar a imagem. Verifique o caminho.")