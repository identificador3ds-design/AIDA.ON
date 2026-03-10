import numpy as np
import cv2
import base64

def extract_lsb_plane(image):
    """
    Extrai o plano do bit menos significativo de cada canal.
    Retorna uma imagem (mesmo shape da original) com valores 0 ou 255.
    """
    if len(image.shape) == 3:
        lsb = np.zeros(image.shape[:2], dtype=np.uint8)
        for c in range(3):
            lsb = np.maximum(lsb, (image[:,:,c] & 1) * 255)
    else:
        lsb = (image & 1) * 255
    return lsb.astype(np.uint8)

def executar_analise_m4(img_bytes):
    """
    Executa a análise LSB (plano de bits menos significativos)
    e retorna um dicionário compatível com o frontend.
    """
    try:
        print("[M4] Iniciando análise LSB...")
        
        # Carregar imagem colorida
        np_img = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(np_img, cv2.IMREAD_COLOR)
        
        if img is None:
            print("[M4] ERRO: Não foi possível decodificar a imagem")
            return {
                "status": "erro",
                "mensagem": "Falha ao decodificar imagem"
            }
        
        # Converter para RGB
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        print(f"[M4] Imagem carregada: {img_rgb.shape}")

        # Extrair plano LSB
        lsb_plane = extract_lsb_plane(img_rgb)
        print(f"[M4] Plano LSB extraído: {lsb_plane.shape}")

        # Codificar a imagem LSB como PNG em base64
        _, buffer = cv2.imencode('.png', lsb_plane)
        lsb_base64 = base64.b64encode(buffer).decode('utf-8')
        imagem_resultado = f"data:image/png;base64,{lsb_base64}"

        # Calcular probabilidade (percentual de pixels com LSB = 1)
        total_pixels = lsb_plane.size
        pixels_ativos = np.count_nonzero(lsb_plane)  # valores 255
        prob = (pixels_ativos / total_pixels) * 100

        # Energia (formato legível)
        energia = f"{pixels_ativos}/{total_pixels}"

        print(f"[M4] Análise concluída - Ativos: {pixels_ativos}/{total_pixels} ({prob:.1f}%)")

        return {
            "status": "sucesso",
            "imagem_fft": imagem_resultado,
            "probabilidade": f"{prob:.1f}%",
            "energia": energia,
            "metodo": "Análise LSB (plano de bits)"
        }
        
    except Exception as e:
        print(f"[M4] ERRO: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "status": "erro",
            "mensagem": str(e)
        }