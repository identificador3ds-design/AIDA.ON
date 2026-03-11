import cv2
import numpy as np
import base64
import matplotlib.pyplot as plt
import io

def executar_analise_gradiente(img_bytes):
    """
    Aplica o filtro Laplaciano estilizado (efeito neon)
    e retorna um dicionário compatível com o frontend,
    utilizando matplotlib para gerar a imagem com a mesma aparência do código original.
    """
    try:
        print("[GRAD] Iniciando análise Gradiente Laplaciano...")
        
        # Carregar imagem
        np_img = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(np_img, cv2.IMREAD_COLOR)
        
        if img is None:
            print("[GRAD] ERRO: Não foi possível decodificar a imagem")
            return {
                "status": "erro",
                "mensagem": "Falha ao decodificar imagem"
            }
        
        # Converter para escala de cinza
        imagem_cinza = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Aplicar Laplaciano
        laplaciano = cv2.Laplacian(imagem_cinza, cv2.CV_64F, ksize=3)
        laplaciano_abs = cv2.convertScaleAbs(laplaciano)
        
        # Normalizar para aumentar contraste
        laplaciano_norm = cv2.normalize(
            laplaciano_abs,
            None,
            0,
            255,
            cv2.NORM_MINMAX
        )
        
        # Aplicar colormap (efeito neon) – retorna imagem BGR
        gradiente_colorido = cv2.applyColorMap(
            laplaciano_norm,
            cv2.COLORMAP_TURBO
        )
        
        # Converter BGR para RGB para uso no matplotlib
        gradiente_rgb = cv2.cvtColor(gradiente_colorido, cv2.COLOR_BGR2RGB)
        
        # --- Gerar a figura usando matplotlib (igual ao código original) ---
        plt.figure(figsize=(8, 8))  # Tamanho quadrado, semelhante à visualização
        plt.imshow(gradiente_rgb)
        plt.axis('off')
        
        # Remover bordas brancas
        plt.subplots_adjust(left=0, right=1, top=1, bottom=0)
        
        # Salvar em buffer
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', pad_inches=0)
        buf.seek(0)
        plt.close()  # Fecha a figura para liberar memória
        
        # Codificar em base64
        gradiente_base64 = base64.b64encode(buf.read()).decode('utf-8')
        imagem_resultado = f"data:image/png;base64,{gradiente_base64}"
        
        # Calcular "probabilidade" baseada na intensidade das bordas
        intensidade_media = np.mean(laplaciano_abs)
        prob = min(99.9, (intensidade_media / 255) * 100)
        
        # Energia (intensidade média das bordas)
        energia = f"Intensidade média: {intensidade_media:.2f}"
        
        print(f"[GRAD] Análise concluída - Intensidade média: {intensidade_media:.2f}")
        
        return {
            "status": "sucesso",
            "imagem_fft": imagem_resultado,
            "probabilidade": f"{prob:.1f}%",
            "energia": energia,
            "metodo": "Gradiente Laplaciano (Efeito Neon)"
        }
        
    except Exception as e:
        print(f"[GRAD] ERRO: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "status": "erro",
            "mensagem": str(e)
        }