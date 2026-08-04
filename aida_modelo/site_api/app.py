from flask import Flask, request, jsonify
from flask_cors import CORS
from pathlib import Path
from PIL import Image
import tempfile
import os
import sys
import uuid

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(BASE_DIR))

from analisar_imagem import analisar_imagem

app = Flask(__name__)

app.config["MAX_CONTENT_LENGTH"] = 15 * 1024 * 1024

CORS(app)

EXTENSOES_PERMITIDAS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}


@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "online",
        "mensagem": "API AIDA.ON funcionando"
    })


def validar_imagem(caminho):
    try:
        with Image.open(caminho) as img:
            img.verify()
        return True
    except Exception:
        return False


@app.route("/analisar", methods=["POST"])
def analisar():
    try:
        if "imagem" not in request.files:
            return jsonify({"erro": "Nenhuma imagem enviada."}), 400

        arquivo = request.files["imagem"]

        if arquivo.filename == "":
            return jsonify({"erro": "Nome de arquivo inválido."}), 400

        extensao = Path(arquivo.filename).suffix.lower()

        if extensao not in EXTENSOES_PERMITIDAS:
            return jsonify({"erro": "Formato de imagem não permitido."}), 400

        historico_habilitado = request.form.get("historico_habilitado", "false").lower() == "true"

        id_analise = str(uuid.uuid4())

        with tempfile.TemporaryDirectory() as pasta_temp:
            caminho_imagem = Path(pasta_temp) / f"{id_analise}{extensao}"
            arquivo.save(caminho_imagem)

            if not validar_imagem(caminho_imagem):
                return jsonify({"erro": "O arquivo enviado não é uma imagem válida."}), 400

            resultado = analisar_imagem(
                caminho_imagem=str(caminho_imagem),
                id_analise=id_analise,
                historico_habilitado=historico_habilitado
            )

        return jsonify(resultado), 200

    except Exception:
        return jsonify({
            "erro": "Erro interno ao analisar a imagem."
        }), 500


@app.route("/analise/<id_analise>", methods=["GET"])
def buscar_analise(id_analise):
    return jsonify({
        "mensagem": "Esta rota deverá buscar a análise no Supabase.",
        "id": id_analise
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)