import os
import sys
import traceback
from pathlib import Path

from flask import Flask, jsonify, request
from flask_cors import CORS
from werkzeug.utils import secure_filename


AIDA_MODELO_DIR = Path(__file__).resolve().parents[3] / "aida_modelo"
if str(AIDA_MODELO_DIR) not in sys.path:
    sys.path.insert(0, str(AIDA_MODELO_DIR))

try:
    from analisar_imagem import analisar_imagem
    from config import (
        EXTENSOES_ACEITAS,
        TAMANHO_MAX_BYTES,
        TAMANHO_MAX_MB,
        UPLOADS_DIR,
        criar_estrutura,
    )
    from historico import buscar_analise_por_id
except ImportError as exc:
    raise RuntimeError(
        "Nao foi possivel carregar o metodo novo. Verifique se a pasta "
        "'aida_modelo' esta ao lado da pasta 'AIDA.ON'."
    ) from exc


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
app.config["MAX_CONTENT_LENGTH"] = inteiro_ambiente("MAX_REQUEST_BYTES", TAMANHO_MAX_BYTES)
CORS(app, resources={r"/*": {"origins": obter_origens_permitidas()}})


def erro(mensagem, status=400):
    return jsonify({"sucesso": False, "erro": mensagem}), status


def historico_habilitado():
    valor = request.form.get("historico", "true")
    return str(valor).strip().lower() in {"true", "1", "sim", "on", "yes"}


def caminho_upload_disponivel(nome_original, extensao):
    nome_seguro = secure_filename(nome_original) or f"imagem{extensao}"
    caminho = UPLOADS_DIR / nome_seguro
    contador = 1

    while caminho.exists():
        caminho = UPLOADS_DIR / f"{Path(nome_seguro).stem}_{contador}{extensao}"
        contador += 1

    return caminho


@app.errorhandler(413)
def payload_grande(_erro):
    return erro(f"A imagem ultrapassa o limite de {TAMANHO_MAX_MB} MB.", 413)


@app.route("/", methods=["GET"])
def home():
    return jsonify(
        {
            "sucesso": True,
            "mensagem": "Servidor AIDA.ON online usando o metodo novo de identificacao.",
            "modelo": str(AIDA_MODELO_DIR),
        }
    )


@app.route("/analisar", methods=["POST"])
def analisar():
    criar_estrutura()

    if "imagem" not in request.files:
        return erro("Nenhuma imagem foi enviada.")

    arquivo = request.files["imagem"]
    if not arquivo or arquivo.filename == "":
        return erro("Arquivo de imagem invalido.")

    extensao = Path(arquivo.filename).suffix.lower()
    if extensao not in EXTENSOES_ACEITAS:
        return erro(f"Formato invalido. Use: {', '.join(sorted(EXTENSOES_ACEITAS))}")

    arquivo.seek(0, 2)
    tamanho = arquivo.tell()
    arquivo.seek(0)
    if tamanho > TAMANHO_MAX_BYTES:
        return erro(f"A imagem ultrapassa o limite de {TAMANHO_MAX_MB} MB.")

    salvar_historico = historico_habilitado()
    caminho = caminho_upload_disponivel(arquivo.filename, extensao)
    arquivo.save(caminho)

    try:
        resultado = analisar_imagem(
            caminho,
            historico_habilitado=salvar_historico,
            imagem_mantida=salvar_historico,
        )

        if not salvar_historico and caminho.exists():
            caminho.unlink()

        return jsonify(
            {
                "sucesso": True,
                "id_analise": resultado["id_analise"],
                "resultado": resultado["resultado"],
                "probabilidade_real": round(resultado["probabilidade_real"], 6),
                "probabilidade_ia": round(resultado["probabilidade_ia"], 6),
                "confianca": resultado["confianca"],
                "explicacao": resultado["explicacao"],
                "modelo_utilizado": resultado["modelo_utilizado"],
                "historico_habilitado": salvar_historico,
                "imagem_mantida_no_historico": salvar_historico,
                "relatorio_json": resultado["relatorio_json"],
                "relatorio_txt": resultado.get("relatorio_txt"),
                "principais_metricas": resultado.get("principais_metricas", {}),
            }
        )
    except Exception as exc:
        if caminho.exists() and not salvar_historico:
            caminho.unlink()
        print("[AIDA.ON] Erro ao processar imagem com o metodo novo:", exc)
        traceback.print_exc()
        return erro(str(exc), 500)


@app.route("/analise/<id_analise>", methods=["GET"])
def analise_por_id(id_analise):
    registro = buscar_analise_por_id(id_analise)
    if not registro:
        return erro("Analise nao encontrada.", 404)
    return jsonify({"sucesso": True, "analise": registro})


if __name__ == "__main__":
    criar_estrutura()
    port = inteiro_ambiente("PORT", 5000)
    debug = os.environ.get("FLASK_DEBUG", "false").strip().lower() in {"1", "true", "sim", "yes"}
    app.run(host="0.0.0.0", port=port, debug=debug)
