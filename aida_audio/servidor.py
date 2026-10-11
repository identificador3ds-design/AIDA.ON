"""Rotas HTTP do AIDA Audio, penduradas no servidor do AIDA Video.

Antes o audio so era analisado como trilha de um video. Agora tem rota propria,
usada pela pagina index-audio.html e pelo envio unificado do site:

    POST /audio/analisar   (campo "audio", ate TAMANHO_MAX_MB)
    GET  /audio/saude

Resposta sincrona (alguns segundos). O arquivo vai para uma pasta temporaria so
para o FFmpeg decodificar e e apagado em seguida; nada fica guardado.
"""

from __future__ import annotations

import tempfile
import threading
from pathlib import Path

from flask import jsonify, request
from werkzeug.utils import secure_filename

from .analisar import MAX_SEGUNDOS_ANALISE, analisar_audio
from .carregar import AudioAusente
from .modelo import ARQUIVO_MODELO

TAMANHO_MAX_MB = 30
EXTENSOES = {".wav", ".mp3", ".m4a", ".aac", ".ogg", ".opus", ".flac", ".webm", ".amr", ".3gp"}
# Um CPU basico: duas analises ao mesmo tempo ja dobram o tempo de cada uma.
_VAGAS = threading.BoundedSemaphore(2)


def registrar(app):
    def erro(mensagem, status):
        return jsonify({"erro": mensagem}), status

    @app.get("/audio/saude")
    def audio_saude():
        return jsonify({"status": "online", "servico": "AIDA Audio", "tamanho_max_mb": TAMANHO_MAX_MB,
                        "max_segundos": MAX_SEGUNDOS_ANALISE, "extensoes": sorted(EXTENSOES),
                        "modelo_disponivel": ARQUIVO_MODELO.is_file()})

    @app.post("/audio/analisar")
    def audio_analisar():
        arquivo = request.files.get("audio")
        if arquivo is None or not arquivo.filename:
            return erro("Envie o arquivo no campo 'audio'.", 400)
        extensao = Path(arquivo.filename).suffix.lower()
        if extensao not in EXTENSOES:
            return erro(f"Formato '{extensao or '?'}' não suportado. Use: {', '.join(sorted(EXTENSOES))}.", 400)
        dados = arquivo.read(TAMANHO_MAX_MB * 1024 * 1024 + 1)
        if len(dados) > TAMANHO_MAX_MB * 1024 * 1024:
            return erro(f"O áudio passa de {TAMANHO_MAX_MB} MB.", 413)
        if not _VAGAS.acquire(timeout=30):
            return erro("Há análises de áudio em andamento. Tente de novo em instantes.", 429)
        try:
            with tempfile.TemporaryDirectory(prefix="aida_audio_srv_") as pasta:
                caminho = Path(pasta) / (secure_filename(arquivo.filename) or f"audio{extensao}")
                caminho.write_bytes(dados)
                resultado = analisar_audio(caminho)
        except AudioAusente as exc:
            return erro(str(exc), 422)
        except ValueError as exc:
            return erro(str(exc), 400)
        except Exception:
            app.logger.exception("falha ao analisar audio")
            return erro("Não foi possível analisar este áudio.", 500)
        finally:
            _VAGAS.release()
        resultado.pop("caracteristicas", None)      # ~200 numeros internos: so pesam na resposta
        resultado["arquivo"] = arquivo.filename
        return jsonify(resultado)
