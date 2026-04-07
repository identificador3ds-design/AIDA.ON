from flask import Flask, request, jsonify, make_response
from flask_cors import CORS
import base64
import os

from metadados import verificar_ia_nos_metadados
from fft import executar_analise_completa_fft
from marca_dagua import verificar_marca_dagua
from m4 import executar_analise_m4
from grad import executar_analise_gradiente

app = Flask(__name__)

CORS(app, resources={r"/*": {"origins": "*"}})


def normalizar_flag_analise(valor, padrao=True):
    if valor is None:
        return padrao

    if isinstance(valor, bool):
        return valor

    if isinstance(valor, str):
        return valor.strip().lower() not in {"false", "0", "nao", "off"}

    return bool(valor)


@app.before_request
def handle_preflight():
    if request.method == "OPTIONS":
        response = make_response()
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add("Access-Control-Allow-Headers", "*")
        response.headers.add("Access-Control-Allow-Methods", "*")
        return response, 200


METODOS_PRINCIPAIS = {
    "FFT": executar_analise_completa_fft,
    "M4": executar_analise_m4,
    "GRAD": executar_analise_gradiente,
    # "PSEM": executar_analise_psem,
}


@app.route("/", methods=["GET"])
def home():
    return "Servidor AIDA.ON online e pronto para analise.", 200


@app.route("/analisar", methods=["POST"])
def analisar():
    try:
        data = request.json
        if not data or "imagem" not in data:
            return jsonify({"status": "erro", "mensagem": "Nenhuma imagem enviada"}), 400

        metodo_escolhido = data.get("metodo")
        analisar_marca_dagua = normalizar_flag_analise(data.get("analisarMarcaDagua"), True)
        analisar_metadados = normalizar_flag_analise(data.get("analisarMetadados"), True)

        print(f"[DEBUG] Metodo recebido no backend: {metodo_escolhido}")
        print(
            f"[DEBUG] Opcoes auxiliares - marca d'agua: {analisar_marca_dagua}, "
            f"metadados: {analisar_metadados}"
        )

        if not metodo_escolhido:
            return jsonify({"status": "erro", "mensagem": "Metodo nao especificado"}), 400

        image_full_b64 = data.get("imagem")
        image_b64_data = image_full_b64.split(",")[1] if "," in image_full_b64 else image_full_b64
        img_bytes = base64.b64decode(image_b64_data)

        if analisar_marca_dagua:
            print("[DEBUG] Verificando marca d'agua...")
            foi_detectado_marca, nome_ia_marca = verificar_marca_dagua(img_bytes)
            if foi_detectado_marca:
                print("[DEBUG] Detectado por MARCA D'AGUA")
                return jsonify({
                    "status": "sucesso",
                    "imagem_fft": image_full_b64,
                    "probabilidade": "100%",
                    "energia": "N/A",
                    "metodo": f"Marca Visual ({nome_ia_marca})",
                    "veredito": "IA DETECTADA"
                })
        else:
            print("[DEBUG] Verificacao de marca d'agua ignorada pelo usuario.")

        if analisar_metadados:
            print("[DEBUG] Verificando metadados...")
            foi_detectado_meta, nome_ia_meta = verificar_ia_nos_metadados(img_bytes)
            if foi_detectado_meta:
                print("[DEBUG] Detectado por METADADOS")
                return jsonify({
                    "status": "sucesso",
                    "imagem_fft": image_full_b64,
                    "probabilidade": "100%",
                    "energia": "N/A",
                    "metodo": f"Metadados ({nome_ia_meta})",
                    "veredito": "IA DETECTADA"
                })
        else:
            print("[DEBUG] Verificacao de metadados ignorada pelo usuario.")

        print(f"[DEBUG] Metodos disponiveis: {list(METODOS_PRINCIPAIS.keys())}")

        if metodo_escolhido not in METODOS_PRINCIPAIS:
            print(f"[DEBUG] Metodo '{metodo_escolhido}' nao encontrado.")
            return jsonify({
                "status": "erro",
                "mensagem": f"Metodo '{metodo_escolhido}' nao suportado"
            }), 400

        print(f"[DEBUG] Executando metodo: {metodo_escolhido}")
        funcao_metodo = METODOS_PRINCIPAIS[metodo_escolhido]
        resultado = funcao_metodo(img_bytes)

        print(f"[DEBUG] Resultado - metodo retornado: {resultado.get('metodo')}")
        print(f"[DEBUG] Resultado - probabilidade: {resultado.get('probabilidade')}")

        return jsonify(resultado)

    except Exception as e:
        print(f"[DEBUG] Erro no processamento: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
from flask import Flask, request, jsonify, make_response
from flask_cors import CORS
import base64
import os

from metadados import verificar_ia_nos_metadados
from fft import executar_analise_completa_fft
from marca_dagua import verificar_marca_dagua
from m4 import executar_analise_m4
from grad import executar_analise_gradiente

app = Flask(__name__)

CORS(app, resources={r"/*": {"origins": "*"}})


def normalizar_flag_analise(valor, padrao=True):
    if valor is None:
        return padrao

    if isinstance(valor, bool):
        return valor

    if isinstance(valor, str):
        return valor.strip().lower() not in {"false", "0", "nao", "off"}

    return bool(valor)


@app.before_request
def handle_preflight():
    if request.method == "OPTIONS":
        response = make_response()
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add("Access-Control-Allow-Headers", "*")
        response.headers.add("Access-Control-Allow-Methods", "*")
        return response, 200


METODOS_PRINCIPAIS = {
    "FFT": executar_analise_completa_fft,
    "M4": executar_analise_m4,
    "GRAD": executar_analise_gradiente,
    # "PSEM": executar_analise_psem,
}


@app.route("/", methods=["GET"])
def home():
    return "Servidor AIDA.ON online e pronto para analise.", 200


@app.route("/analisar", methods=["POST"])
def analisar():
    try:
        data = request.json
        if not data or "imagem" not in data:
            return jsonify({"status": "erro", "mensagem": "Nenhuma imagem enviada"}), 400

        metodo_escolhido = data.get("metodo")
        analisar_marca_dagua = normalizar_flag_analise(data.get("analisarMarcaDagua"), True)
        analisar_metadados = normalizar_flag_analise(data.get("analisarMetadados"), True)

        print(f"[DEBUG] Metodo recebido no backend: {metodo_escolhido}")
        print(
            f"[DEBUG] Opcoes auxiliares - marca d'agua: {analisar_marca_dagua}, "
            f"metadados: {analisar_metadados}"
        )

        if not metodo_escolhido:
            return jsonify({"status": "erro", "mensagem": "Metodo nao especificado"}), 400

        image_full_b64 = data.get("imagem")
        image_b64_data = image_full_b64.split(",")[1] if "," in image_full_b64 else image_full_b64
        img_bytes = base64.b64decode(image_b64_data)

        if analisar_marca_dagua:
            print("[DEBUG] Verificando marca d'agua...")
            foi_detectado_marca, nome_ia_marca, dados_marca = verificar_marca_dagua(img_bytes)
            if foi_detectado_marca:
                print("[DEBUG] Detectado por MARCA D'AGUA")
                return jsonify({
                    "status": "sucesso",
                    "imagem_fft": image_full_b64,
                    "probabilidade": "100%",
                    "energia": "N/A",
                    "metodo": f"Marca Visual ({nome_ia_marca})",
                    "marca_visual": dados_marca,
                    "veredito": "IA DETECTADA"
                })
        else:
            print("[DEBUG] Verificacao de marca d'agua ignorada pelo usuario.")

        if analisar_metadados:
            print("[DEBUG] Verificando metadados...")
            foi_detectado_meta, nome_ia_meta = verificar_ia_nos_metadados(img_bytes)
            if foi_detectado_meta:
                print("[DEBUG] Detectado por METADADOS")
                return jsonify({
                    "status": "sucesso",
                    "imagem_fft": image_full_b64,
                    "probabilidade": "100%",
                    "energia": "N/A",
                    "metodo": f"Metadados ({nome_ia_meta})",
                    "veredito": "IA DETECTADA"
                })
        else:
            print("[DEBUG] Verificacao de metadados ignorada pelo usuario.")

        print(f"[DEBUG] Metodos disponiveis: {list(METODOS_PRINCIPAIS.keys())}")

        if metodo_escolhido not in METODOS_PRINCIPAIS:
            print(f"[DEBUG] Metodo '{metodo_escolhido}' nao encontrado.")
            return jsonify({
                "status": "erro",
                "mensagem": f"Metodo '{metodo_escolhido}' nao suportado"
            }), 400

        print(f"[DEBUG] Executando metodo: {metodo_escolhido}")
        funcao_metodo = METODOS_PRINCIPAIS[metodo_escolhido]
        resultado = funcao_metodo(img_bytes)

        print(f"[DEBUG] Resultado - metodo retornado: {resultado.get('metodo')}")
        print(f"[DEBUG] Resultado - probabilidade: {resultado.get('probabilidade')}")

        return jsonify(resultado)

    except Exception as e:
        print(f"[DEBUG] Erro no processamento: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
