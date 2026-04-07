import cv2
import os

def extrair_frames(caminho_video, pasta_destino, intervalo_frames=30):
    # Cria a pasta de destino se ela não existir
    if not os.path.exists(pasta_destino):
        os.makedirs(pasta_destino)
        print(f"Pasta '{pasta_destino}' criada.")

    # Carrega o arquivo de vídeo
    video = cv2.VideoCapture(caminho_video)
    
    if not video.isOpened():
        print("Erro ao abrir o vídeo. Verifique o caminho.")
        return

    contagem = 0
    salvos = 0

    while True:
        sucesso, frame = video.read()

        # Se o vídeo acabar, encerra o loop
        if not sucesso:
            break

        # Salva o frame baseado no intervalo escolhido (ex: a cada 30 frames)
        if contagem % intervalo_frames == 0:
            nome_arquivo = os.path.join(pasta_destino, f"frame_{salvos:04d}.jpg")
            cv2.imwrite(nome_arquivo, frame)
            salvos += 1

        contagem += 1

    video.release()
    print(f"Processo finalizado! {salvos} frames salvos em: {pasta_destino}")

# --- Configurações ---
video_input = "videoteste.mp4"  # Coloque o nome do seu arquivo aqui
pasta_output = "frames_extraidos"
pular_frames = 60  # Salva 1 frame a cada 60 (aprox. 2 segundos em vídeos de 30fps)

extrair_frames(video_input, pasta_output, pular_frames)
