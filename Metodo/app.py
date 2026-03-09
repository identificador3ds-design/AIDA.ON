from flask import Flask, request, jsonify, make_response
from flask_cors import CORS
import base64
import io
import os
import matplotlib
matplotlib.use('Agg')  # OBRIGATÓRIO para servidores como o Render
import matplotlib.pyplot as plt

# Importação dos seus módulos de detecção
# Certifique-se que estes arquivos (.py) estão na mesma pasta
from metadados import verificar_ia_nos_metadados
from fft import executar_analise_completa_fft
from marca_dagua import verificar_marca_dagua
from teste_qse import analisar_fisica_imagem

app = Flask(__name__)

# Configuração de CORS para permitir que o seu HTML acesse o Python
CORS(app, resources={r"/*": {"origins": "*"}})

@app.before_request
def handle_preflight():
    if request.method == "OPTIONS":
        response = make_response()
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add("Access-Control-Allow-Headers", "*")
        response.headers.add("Access-Control-Allow-Methods", "*")
        return response, 200

@app.route('/', methods=['GET'])
def home():
    return "Servidor AIDA.ON online e pronto para análise.", 200

@app.route('/analisar', methods=['POST'])
def analisar():
    try:
        data = request.json
        if not data or 'imagem' not in data:
            return jsonify({"status": "erro", "mensagem": "Nenhuma imagem enviada"}), 400
            
        metodo_solicitado = data.get('metodo') # Captura o método do Select
        image_full_b64 = data.get('imagem')
        image_b64_data = image_full_b64.split(",")[1] if "," in image_full_b64 else image_full_b64
        img_bytes = base64.b64decode(image_b64_data)

        # --- NOVA LÓGICA: Se o usuário selecionou especificamente ESTATISTICA ---
        if metodo_solicitado == "ESTATIC":
            stats = analisar_fisica_imagem(img_bytes)
            if stats:
                luz, geo, cont, fourier, score = stats
                is_fake = score < 0.4 or score > 0.8
                return jsonify({
                    "status": "sucesso",
                    "imagem_fft": image_full_b64, 
                    "probabilidade": "90.1%" if is_fake else "5.2%",
                    "energia": f"Score Físico: {score:.4f}",
                    "metodo": "Análise Estatística de Consistência",
                    "veredito": "IA DETECTADA" if is_fake else "REAL",
                    "detalhes": {"luz": luz, "geo": geo, "cont": cont, "fourier": fourier}
                })

        # --- PASSO 1: Marcas d'Água Visuais ---
        foi_detectado_marca, nome_ia_marca = verificar_marca_dagua(img_bytes)
        if foi_detectado_marca:
            return jsonify({
                "status": "sucesso",
                "imagem_fft": image_full_b64, 
                "probabilidade": "100%",
                "energia": "N/A",
                "metodo": f"Marca Visual ({nome_ia_marca})",
                "veredito": "IA DETECTADA"
            })
        
        # --- PASSO 2: Metadados e Assinaturas ---
        foi_detectado_meta, nome_ia_meta = verificar_ia_nos_metadados(img_bytes)
        if foi_detectado_meta:
            return jsonify({
                "status": "sucesso",
                "imagem_fft": image_full_b64, 
                "probabilidade": "100%",
                "energia": "N/A",
                "metodo": f"Metadados ({nome_ia_meta})",
                "veredito": "IA DETECTADA"
            })
        
# --- PASSO 3: Análise Física/Estatística ---
        stats = analisar_fisica_imagem(img_bytes)
        
        if stats:
            # Desempacotando a tupla de 5 valores que vem do seu teste_qse.py
            luz, geo, cont, fourier, score = stats
            
            # Lógica: Se o score fugir do padrão humano [0.4 a 0.8], é suspeito
            if score < 0.4 or score > 0.8:
                return jsonify({
                    "status": "sucesso",
                    "imagem_fft": image_full_b64, 
                    "probabilidade": "90.1%",
                    "energia": f"Score Físico: {score:.4f}",
                    "metodo": "Análise de Consistência Física",
                    "veredito": "IA DETECTADA (Anomalia)",
                    "detalhes": {
                        "luz": float(luz), 
                        "geo": float(geo), 
                        "cont": float(cont), 
                        "fourier": float(fourier)
                    }
                })

        # --- PASSO 4: Análise de Frequência (FFT) ---
        # Caso os filtros acima passem, o FFT dá a palavra final
        resultado_fft = executar_analise_completa_fft(img_bytes)
        return jsonify(resultado_fft)

    except Exception as e:
        print(f"Erro no processamento: {str(e)}")
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)