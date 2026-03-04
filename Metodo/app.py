from flask import Flask, request, jsonify
from flask_cors import CORS
import base64
import os

app = Flask(__name__)

# Configuração robusta do CORS para aceitar o seu Netlify
CORS(app, resources={r"/*": {"origins": "*"}})

from metadados import verificar_ia_nos_metadados
from fft import executar_analise_completa_fft
from marca_dagua import verificar_marca_dagua

# ROTA DE TESTE (Para evitar o erro que apareceu no seu print)
@app.route('/', methods=['GET'])
def home():
    return "Servidor AIDA.ON está online!", 200

@app.route('/analisar', methods=['POST', 'OPTIONS']) # Adicionado OPTIONS aqui
def analisar():
    # O CORS(app) já trata o OPTIONS, mas manteremos o fluxo
    try:
        data = request.json
        if not data or 'imagem' not in data:
            return jsonify({"status": "erro", "mensagem": "Nenhuma imagem enviada"}), 400
            
        image_full_b64 = data.get('imagem')
        image_b64_data = image_full_b64.split(",")[1]
        img_bytes = base64.b64decode(image_b64_data)

        # ---------------------------------------------------------
        # PASSO 1: Marca d'Água Visual
        # ---------------------------------------------------------
        foi_detectado_marca, nome_ia_marca = verificar_marca_dagua(img_bytes)

        if foi_detectado_marca:
            return jsonify({
                "status": "sucesso",
                "imagem_fft": image_full_b64, 
                "probabilidade": "100% (Confirmado)",
                "energia": "N/A (Marca Visual)",
                "metodo": f"Detecção Visual ({nome_ia_marca})"
            })
        
        # ---------------------------------------------------------
        # PASSO 2: Metadados
        # ---------------------------------------------------------
        foi_detectado_meta, nome_ia_meta = verificar_ia_nos_metadados(img_bytes)

        if foi_detectado_meta:
            return jsonify({
                "status": "sucesso",
                "imagem_fft": image_full_b64, 
                "probabilidade": "100% (Confirmado)",
                "energia": "N/A (Assinatura Digital)",
                "metodo": f"Detecção por Metadados ({nome_ia_meta})"
            })

        # ---------------------------------------------------------
        # PASSO 3: Se não encontrou nada explícito, segue para o FFT
        # ---------------------------------------------------------
        resultado_fft = executar_analise_completa_fft(img_bytes)
        return jsonify(resultado_fft)

    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)


