from PIL import Image
import io

def verificar_ia_nos_metadados(image_bytes):
    # Termos baseados exatamente no seu print de metadados
    termos_ia = {
        "gpt-4o": "OpenAI (GPT-4o / C2PA)",
        "dall-e": "OpenAI (DALL-E)",
        "c2pa": "Assinatura C2PA (Content Authenticity)",
        "trainedalgorithmicmedia": "IA Generativa (Metadata Standard)",
        "adobe firefly": "Adobe Firefly",
        "midjourney": "Midjourney",
        "stable diffusion": "Stable Diffusion"
    }
    
    try:
        # TÉCNICA 1: Varredura Binária (A mais poderosa para C2PA/JUMBF)
        # Transformamos os bytes em string para buscar os termos diretamente no arquivo
        conteudo_bruto = str(image_bytes).lower()
        
        for termo, nome_ia in termos_ia.items():
            if termo in conteudo_bruto:
                return True, nome_ia

        # TÉCNICA 2: Pil Info (Backup para metadados PNG comuns)
        img = Image.open(io.BytesIO(image_bytes))
        for k, v in img.info.items():
            valor_str = str(v).lower()
            for termo, nome_ia in termos_ia.items():
                if termo in valor_str:
                    return True, nome_ia

    except Exception as e:
        print(f"Erro na varredura: {e}")
    
    return False, None