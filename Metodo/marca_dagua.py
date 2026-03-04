import cv2
import numpy as np
import os

def verificar_marca_dagua(img_bytes):
    try:
        np_img = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(np_img, cv2.IMREAD_COLOR)

        if img is None:
            print("[DEBUG] Erro: Não foi possível decodificar a imagem.")
            return False, None

        h, w = img.shape[:2]
        
        # Isola os últimos 20% da imagem (aumentei um pouco a área de busca)
        h_corte = int(h * 0.80)
        w_corte = int(w * 0.80)
        canto_inferior_direito = img[h_corte:h, w_corte:w]
        gray_canto = cv2.cvtColor(canto_inferior_direito, cv2.COLOR_BGR2GRAY)

        caminho_template = "template_gemini.png" 
        
        # VERIFICAÇÃO 1: O arquivo existe?
        if not os.path.exists(caminho_template):
            print(f"[DEBUG] AVISO: O arquivo '{caminho_template}' não foi encontrado na pasta do Python!")
            return False, None

        template = cv2.imread(caminho_template, cv2.IMREAD_GRAYSCALE)
        
        # VERIFICAÇÃO 2: O template é maior que o canto da imagem?
        if template is None or template.shape[0] > gray_canto.shape[0] or template.shape[1] > gray_canto.shape[1]:
            print("[DEBUG] AVISO: Problema com o tamanho do template ou template vazio.")
            return False, None

        resultado = cv2.matchTemplate(gray_canto, template, cv2.TM_CCOEFF_NORMED)
        
        # 0.7 = 70% de semelhança (abaixei um pouco a exigência para testar)
        threshold = 0.7 
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(resultado)

        # VERIFICAÇÃO 3: Qual foi a pontuação máxima encontrada?
        print(f"[DEBUG] Semelhança máxima encontrada com o template: {max_val:.2f} (Precisa ser >= {threshold})")

        if max_val >= threshold:
            print("[DEBUG] -> MARCA D'ÁGUA ENCONTRADA COM SUCESSO!")
            return True, "Google Gemini"
        else:
            print("[DEBUG] -> Marca d'água NÃO atingiu a pontuação mínima.")

    except Exception as e:
        print(f"[DEBUG] Erro fatal no marca_dagua.py: {e}")
        
    return False, None