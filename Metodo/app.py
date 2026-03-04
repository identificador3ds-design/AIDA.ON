from flask import Flask, request, jsonify
from flask_cors import CORS
import base64

app = Flask(__name__)
CORS(app)

from metadados import verificar_ia_nos_metadados
from fft import executar_analise_completa_fft
from marca_dagua import verificar_marca_dagua # <-- NOVO IMPORT AQUI

app = Flask(__name__)
CORS(app)

@app.route('/analisar', methods=['POST'])
def analisar():
    try:
        data = request.json
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

if __name__ == '__main__':

    app.run(debug=True, port=5000)
