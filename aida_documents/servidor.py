"""Rotas HTTP do AIDA Documents, penduradas no servidor do AIDA Video.

O site so fala com dois servidores (Core e Video). Em vez de um terceiro Space, as
rotas de documento entram no Flask do video:

    POST /documento/analisar   (campo "documento": PDF, DOCX, DOC ou TXT de ate TAMANHO_MAX_MB)
    GET  /documento/saude

A analise leva menos de um segundo, entao a resposta e sincrona. O arquivo fica so em
memoria: nao e gravado em disco nem guardado depois da resposta.
"""

from __future__ import annotations

from flask import jsonify, request

from .analisar import analisar_bytes

TAMANHO_MAX_MB = 20
EXTENSOES = {".pdf", ".docx", ".doc", ".txt"}


def registrar(app):
    def erro(mensagem, status):
        return jsonify({"erro": mensagem}), status

    @app.get("/documento/saude")
    def documento_saude():
        return jsonify({"status": "online", "servico": "AIDA Documents", "tamanho_max_mb": TAMANHO_MAX_MB,
                        "extensoes": sorted(EXTENSOES)})

    @app.post("/documento/analisar")
    def documento_analisar():
        arquivo = request.files.get("documento")
        if arquivo is None or not arquivo.filename:
            return erro("Envie o arquivo no campo 'documento'.", 400)
        if not arquivo.filename.lower().endswith(tuple(EXTENSOES)):
            return erro("Envie um arquivo PDF, DOCX, DOC ou TXT.", 400)
        dados = arquivo.read(TAMANHO_MAX_MB * 1024 * 1024 + 1)
        if len(dados) > TAMANHO_MAX_MB * 1024 * 1024:
            return erro(f"O arquivo passa de {TAMANHO_MAX_MB} MB.", 413)
        try:
            resultado = analisar_bytes(dados, arquivo.filename)
        except ValueError as exc:
            return erro(str(exc), 400)
        except Exception:
            app.logger.exception("falha ao ler documento")
            return erro("Não foi possível ler este arquivo (corrompido ou protegido por senha).", 422)
        resultado["documento"] = arquivo.filename
        return jsonify(resultado)
