from flask import Flask, request, jsonify, make_response
from flask_cors import CORS
import base64
import io
import os

# Importação dos seus módulos de detecção
from metadados import verificar_ia_nos_metadados
from fft import executar_analise_completa_fft
from marca_dagua import verificar_marca_dagua
from m4 import executar_analise_m4  # ← IMPORTANTE: importar a função do m4.py
from grad import executar_analise_gradiente

app = Flask(__name__)

# Configuração de CORS
CORS(app, resources={r"/*": {"origins": "*"}})

@app.before_request
def handle_preflight():
    if request.method == "OPTIONS":
        response = make_response()
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add("Access-Control-Allow-Headers", "*")
        response.headers.add("Access-Control-Allow-Methods", "*")
        return response, 200

# Dicionário que mapeia o valor do método para a função de análise
METODOS_PRINCIPAIS = {
    "FFT": executar_analise_completa_fft,
    "M4": executar_analise_m4,
    "GRAD": executar_analise_gradiente, 
    # "PSEM": executar_analise_psem,  # quando implementar
}

@app.route('/', methods=['GET'])
def home():
    return "Servidor AIDA.ON online e pronto para análise.", 200

@app.route('/analisar', methods=['POST'])
def analisar():
    try:
        data = request.json
        if not data or 'imagem' not in data:
            return jsonify({"status": "erro", "mensagem": "Nenhuma imagem enviada"}), 400

        metodo_escolhido = data.get('metodo')
        print(f"[DEBUG] Método recebido no backend: {metodo_escolhido}")
        
        if not metodo_escolhido:
            return jsonify({"status": "erro", "mensagem": "Método não especificado"}), 400

        image_full_b64 = data.get('imagem')
        image_b64_data = image_full_b64.split(",")[1] if "," in image_full_b64 else image_full_b64
        img_bytes = base64.b64decode(image_b64_data)
        
        # --- PASSO 1: Marcas d'Água Visuais (automático) ---
        print("[DEBUG] Verificando marca d'água...")
        foi_detectado_marca, nome_ia_marca = verificar_marca_dagua(img_bytes)
        if foi_detectado_marca:
            print("[DEBUG] ✓ Detectado por MARCA D'ÁGUA")
            return jsonify({
                "status": "sucesso",
                "imagem_fft": image_full_b64,
                "probabilidade": "100%",
                "energia": "N/A",
                "metodo": f"Marca Visual ({nome_ia_marca})",
                "veredito": "IA DETECTADA"
            })

        # --- PASSO 2: Metadados e Assinaturas (automático) ---
        print("[DEBUG] Verificando metadados...")
        foi_detectado_meta, nome_ia_meta = verificar_ia_nos_metadados(img_bytes)
        if foi_detectado_meta:
            print("[DEBUG] ✓ Detectado por METADADOS")
            return jsonify({
                "status": "sucesso",
                "imagem_fft": image_full_b64,
                "probabilidade": "100%",
                "energia": "N/A",
                "metodo": f"Metadados ({nome_ia_meta})",
                "veredito": "IA DETECTADA"
            })
        

        # --- PASSO 3: Executa o método escolhido pelo usuário ---
        print(f"[DEBUG] Métodos disponíveis: {list(METODOS_PRINCIPAIS.keys())}")
        
        if metodo_escolhido not in METODOS_PRINCIPAIS:
            print(f"[DEBUG] ✗ Método '{metodo_escolhido}' não encontrado!")
            return jsonify({"status": "erro", "mensagem": f"Método '{metodo_escolhido}' não suportado"}), 400

        print(f"[DEBUG] Executando método: {metodo_escolhido}")
        funcao_metodo = METODOS_PRINCIPAIS[metodo_escolhido]
        resultado = funcao_metodo(img_bytes)
        
        print(f"[DEBUG] Resultado - método retornado: {resultado.get('metodo')}")
        print(f"[DEBUG] Resultado - probabilidade: {resultado.get('probabilidade')}")
        
        return jsonify(resultado)

    except Exception as e:
        print(f"[DEBUG] Erro no processamento: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)