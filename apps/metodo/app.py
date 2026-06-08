import base64
import os
import traceback

from flask import Flask, jsonify, request
from flask_cors import CORS

from fft import executar_analise_completa_fft
from grad import executar_analise_gradiente
from m4 import executar_analise_m4
from marca_dagua import verificar_marca_dagua
from metadados import verificar_ia_nos_metadados


def inteiro_ambiente(nome, padrao):
    try:
        return int(os.environ.get(nome, padrao))
    except (TypeError, ValueError):
        return padrao


def obter_origens_permitidas():
    valor = os.environ.get("ALLOWED_ORIGINS", "*").strip()

    if valor == "*":
        return "*"

    origens = [origem.strip() for origem in valor.split(",") if origem.strip()]
    return origens or "*"


app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = inteiro_ambiente("MAX_REQUEST_BYTES", 12 * 1024 * 1024)

CORS(app, resources={r"/*": {"origins": obter_origens_permitidas()}})

MAX_IMAGE_BYTES = inteiro_ambiente("MAX_IMAGE_BYTES", 8 * 1024 * 1024)

METODOS_PRINCIPAIS = {
    "FFT": executar_analise_completa_fft,
    "M4": executar_analise_m4,
    "GRAD": executar_analise_gradiente,
}


def normalizar_flag_analise(valor, padrao=True):
    if valor is None:
        return padrao

    if isinstance(valor, bool):
        return valor

    if isinstance(valor, str):
        return valor.strip().lower() not in {"false", "0", "nao", "não", "off"}

    return bool(valor)


def decodificar_imagem_base64(valor):
    if not isinstance(valor, str) or not valor.strip():
        raise ValueError("Imagem invalida.")

    imagem_base64 = valor.strip()
    dados_base64 = imagem_base64.split(",", 1)[1] if "," in imagem_base64 else imagem_base64

    try:
        img_bytes = base64.b64decode(dados_base64, validate=True)
    except Exception as erro:
        raise ValueError("Imagem em base64 invalida.") from erro

    if not img_bytes:
        raise ValueError("Imagem vazia.")

    if len(img_bytes) > MAX_IMAGE_BYTES:
        raise ValueError("Imagem excede o tamanho maximo permitido.")

    return img_bytes, imagem_base64


@app.errorhandler(413)
def payload_grande(_erro):
    return jsonify({
        "status": "erro",
        "mensagem": "Arquivo ou requisicao excede o tamanho maximo permitido.",
    }), 413


@app.route("/", methods=["GET"])
def home():
    return "Servidor AIDA.ON online e pronto para analise.", 200


@app.route("/analisar", methods=["POST"])
def analisar():
    try:
        data = request.get_json(silent=True)

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

        img_bytes, image_full_b64 = decodificar_imagem_base64(data.get("imagem"))

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
                    "veredito": "IA DETECTADA",
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
                    "veredito": "IA DETECTADA",
                })
        else:
            print("[DEBUG] Verificacao de metadados ignorada pelo usuario.")

        print(f"[DEBUG] Metodos disponiveis: {list(METODOS_PRINCIPAIS.keys())}")

        if metodo_escolhido not in METODOS_PRINCIPAIS:
            print(f"[DEBUG] Metodo '{metodo_escolhido}' nao encontrado.")
            return jsonify({
                "status": "erro",
                "mensagem": f"Metodo '{metodo_escolhido}' nao suportado",
            }), 400

        print(f"[DEBUG] Executando metodo: {metodo_escolhido}")
        resultado = METODOS_PRINCIPAIS[metodo_escolhido](img_bytes)

        print(f"[DEBUG] Resultado - metodo retornado: {resultado.get('metodo')}")
        print(f"[DEBUG] Resultado - probabilidade: {resultado.get('probabilidade')}")

        return jsonify(resultado)

    except ValueError as erro:
        return jsonify({"status": "erro", "mensagem": str(erro)}), 400
    except Exception as erro:
        print(f"[DEBUG] Erro no processamento: {erro}")
        traceback.print_exc()
        return jsonify({
            "status": "erro",
            "mensagem": "Nao foi possivel processar a imagem agora.",
        }), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "false").strip().lower() in {"1", "true", "sim", "yes"}
    app.run(host="0.0.0.0", port=port, debug=debug)
