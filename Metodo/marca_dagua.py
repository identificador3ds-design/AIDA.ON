import os

import cv2
import numpy as np


def verificar_marca_dagua(img_bytes):
    try:
        np_img = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(np_img, cv2.IMREAD_COLOR)

        if img is None:
            print("[DEBUG] Erro: nao foi possivel decodificar a imagem.")
            return False, None, None

        h, w = img.shape[:2]

        # Analisa apenas o canto inferior direito, onde a logo do Gemini costuma aparecer.
        h_corte = int(h * 0.80)
        w_corte = int(w * 0.80)
        canto_inferior_direito = img[h_corte:h, w_corte:w]
        gray_canto = cv2.cvtColor(canto_inferior_direito, cv2.COLOR_BGR2GRAY)

        caminho_template = os.path.join(os.path.dirname(__file__), "template_gemini.png")

        if not os.path.exists(caminho_template):
            print(f"[DEBUG] AVISO: o arquivo '{caminho_template}' nao foi encontrado.")
            return False, None, None

        template = cv2.imread(caminho_template, cv2.IMREAD_GRAYSCALE)

        if template is None or template.shape[0] > gray_canto.shape[0] or template.shape[1] > gray_canto.shape[1]:
            print("[DEBUG] AVISO: problema com o tamanho do template ou template vazio.")
            return False, None, None

        resultado = cv2.matchTemplate(gray_canto, template, cv2.TM_CCOEFF_NORMED)
        threshold = 0.7
        _min_val, max_val, _min_loc, max_loc = cv2.minMaxLoc(resultado)

        print(
            f"[DEBUG] Semelhanca maxima encontrada com o template: {max_val:.2f} "
            f"(precisa ser >= {threshold})"
        )

        if max_val >= threshold:
            print("[DEBUG] -> MARCA D'AGUA ENCONTRADA COM SUCESSO!")

            template_h, template_w = template.shape[:2]
            x_local, y_local = max_loc

            return True, "Google Gemini", {
                "tipo": "logo_gemini",
                "confianca": float(max_val),
                "search_region": {
                    "x": int(w_corte),
                    "y": int(h_corte),
                    "width": int(w - w_corte),
                    "height": int(h - h_corte)
                },
                "bounding_box": {
                    "x": int(w_corte + x_local),
                    "y": int(h_corte + y_local),
                    "width": int(template_w),
                    "height": int(template_h)
                }
            }

        print("[DEBUG] -> Marca d'agua nao atingiu a pontuacao minima.")
    except Exception as e:
        print(f"[DEBUG] Erro fatal no marca_dagua.py: {e}")

    return False, None, None
