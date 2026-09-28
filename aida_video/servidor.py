"""Servidor HTTP do AIDA Video, para a pagina pages/index-video.html.

Um video leva minutos (cada frame passa pelo AIDA Core), entao a analise nao
cabe numa unica requisicao: o navegador desistiria e o usuario nao veria nada
acontecendo. O fluxo e por tarefa:

    POST /video/analisar          -> 202 {"tarefa": id}
    GET  /video/tarefa/<id>       -> estado, progresso, frames ja analisados, relatorio no fim
    GET  /video/tarefa/<id>/frame/<arquivo>  -> miniatura JPEG (?tamanho=original: PNG cheio)
    GET  /video/saude             -> Core configurado, modelo de audio, limites

As tarefas ficam em memoria e as pastas de trabalho sao apagadas depois de
TTL_TAREFA_S. E um servidor de desenvolvimento/demonstracao: um processo,
sem fila persistente.

Rodar (a partir da raiz AIDA.ON):
    python -m aida_video.servidor            # porta 7870
    AIDA_CORE_URL=http://localhost:7860 python -m aida_video.servidor
"""

from __future__ import annotations

import os
import re
import shutil
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path

if __package__ in (None, ""):
    # Permite `python aida_video/servidor.py`, alem de `python -m aida_video.servidor`.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    __package__ = "aida_video"

from PIL import Image
from flask import Flask, abort, jsonify, request, send_from_directory
from flask_cors import CORS
from werkzeug.exceptions import HTTPException
from werkzeug.utils import secure_filename

from .analisadores import CORE_URL_PADRAO, AnalisadorCore
from .analisar_video import analisar_video
from .extrair_frames import EXTENSOES_VIDEO, TAMANHO_MAX_MB

PORTA_PADRAO = 7870
MAX_FRAMES_LIMITE = 120
TTL_TAREFA_S = 60 * 60
MAX_TAREFAS_SIMULTANEAS = 2
# O Space do Core atende 4 requisicoes ao mesmo tempo (gunicorn --threads 4).
FRAMES_EM_PARALELO = int(os.environ.get("AIDA_VIDEO_PARALELO", "2"))
LADO_MINIATURA = 480
NOME_FRAME = re.compile(r"^frame_\d{4}_[\d.]+s\.png$")


class Tarefas:
    """Registro em memoria das analises em andamento e concluidas."""

    def __init__(self):
        self._dados = {}
        self._trava = threading.Lock()

    def criar(self, pasta, nome_video):
        id_ = uuid.uuid4().hex
        with self._trava:
            self._dados[id_] = {
                "id": id_,
                "estado": "extraindo",
                "video": nome_video,
                "pasta": pasta,
                "criada_em": time.time(),
                "progresso": {"feitos": 0, "total": None},
                "frames": [],
                "relatorio": None,
                "erro": None,
            }
        return id_

    def atualizar(self, id_, **campos):
        with self._trava:
            if id_ in self._dados:
                self._dados[id_].update(campos)

    def adicionar_frame(self, id_, feitos, total, registro):
        with self._trava:
            tarefa = self._dados.get(id_)
            if tarefa:
                tarefa["estado"] = "analisando"
                tarefa["progresso"] = {"feitos": feitos, "total": total}
                tarefa["frames"].append(registro)

    def ler(self, id_):
        with self._trava:
            tarefa = self._dados.get(id_)
            if not tarefa:
                return None
            # Copia a lista: a thread da analise continua acrescentando frames.
            return {**tarefa, "frames": list(tarefa["frames"])}

    def ativas(self):
        with self._trava:
            return sum(1 for t in self._dados.values() if t["estado"] in ("extraindo", "analisando"))

    def limpar_antigas(self, agora=None):
        agora = agora or time.time()
        with self._trava:
            vencidas = [
                id_ for id_, t in self._dados.items()
                if agora - t["criada_em"] > TTL_TAREFA_S and t["estado"] in ("concluida", "erro")
            ]
            removidas = [self._dados.pop(id_) for id_ in vencidas]
        for tarefa in removidas:
            shutil.rmtree(tarefa["pasta"], ignore_errors=True)
        return len(removidas)


def _url_core():
    return (os.environ.get("AIDA_CORE_URL") or CORE_URL_PADRAO).rstrip("/")


def _numero(valor, padrao, minimo, maximo, tipo=float):
    try:
        numero = tipo(valor)
    except (TypeError, ValueError):
        return padrao
    return min(max(numero, minimo), maximo)


def criar_app(fabrica_analisador=None, executar_em_thread=True, tamanho_max_mb=TAMANHO_MAX_MB):
    """fabrica_analisador: callable sem argumentos que devolve o analisador de frames.
    Os testes passam um AnalisadorFixo; em producao e o AnalisadorCore."""
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = tamanho_max_mb * 1024 * 1024
    # AIDA_VIDEO_CORS: origens separadas por virgula (no Space, so o site publicado).
    origens = [o.strip() for o in os.environ.get("AIDA_VIDEO_CORS", "*").split(",") if o.strip()]
    CORS(app, origins=origens or "*")
    tarefas = Tarefas()
    app.config["TAREFAS"] = tarefas
    fabrica_analisador = fabrica_analisador or (lambda: AnalisadorCore())

    def erro(mensagem, status):
        return jsonify({"erro": mensagem}), status

    @app.errorhandler(413)
    def _413(_):
        return erro(f"O vídeo passa do limite de {tamanho_max_mb} MB.", 413)

    @app.errorhandler(404)
    def _404(_):
        return erro("Rota ou recurso não encontrado.", 404)

    @app.errorhandler(HTTPException)
    def _http(exc):
        return erro(exc.description or exc.name, exc.code)

    @app.errorhandler(Exception)
    def _500(exc):
        app.logger.exception("erro nao tratado")
        return erro("Erro interno no servidor de vídeo.", 500)

    @app.get("/")
    @app.get("/video/saude")
    def saude():
        import importlib.util

        from aida_audio.modelo import ARQUIVO_MODELO

        from . import trajetoria

        return jsonify(
            {
                "status": "online",
                "servico": "AIDA Video",
                "core_url": _url_core(),
                "modelo_audio_disponivel": ARQUIVO_MODELO.is_file(),
                # Movimento (DINOv2) precisa do modelo treinado E de torch + timm neste Python.
                "trajetoria_disponivel": trajetoria.ARQUIVO_MODELO.is_file()
                and all(importlib.util.find_spec(m) for m in ("torch", "timm")),
                "tamanho_max_mb": tamanho_max_mb,
                "max_frames": MAX_FRAMES_LIMITE,
                "extensoes": sorted(EXTENSOES_VIDEO),
                "tarefas_ativas": tarefas.ativas(),
            }
        )

    def _rodar(id_, caminho_video, pasta, parametros, com_audio):
        def progresso(feitos, total, registro):
            tarefas.adicionar_frame(id_, feitos, total, registro)

        try:
            relatorio = analisar_video(
                caminho_video,
                analisador=fabrica_analisador(),
                pasta_saida=pasta,
                com_audio=com_audio,
                parametros_extracao=parametros,
                progresso=progresso,
                paralelo=FRAMES_EM_PARALELO,
            )
            tarefas.atualizar(id_, estado="concluida", relatorio=relatorio)
        except (FileNotFoundError, ValueError) as exc:
            tarefas.atualizar(id_, estado="erro", erro=str(exc))
        except Exception as exc:
            app.logger.exception("falha na tarefa %s", id_)
            tarefas.atualizar(id_, estado="erro", erro=f"Falha inesperada: {type(exc).__name__}")
        finally:
            try:
                caminho_video.unlink()  # o video original nao precisa ficar guardado
            except OSError:
                pass

    @app.post("/video/analisar")
    def iniciar():
        tarefas.limpar_antigas()
        arquivo = request.files.get("video")
        if arquivo is None or not arquivo.filename:
            return erro("Envie o arquivo no campo 'video'.", 400)
        extensao = Path(arquivo.filename).suffix.lower()
        if extensao not in EXTENSOES_VIDEO:
            return erro(f"Formato '{extensao or '?'}' não suportado. Use: {', '.join(sorted(EXTENSOES_VIDEO))}.", 400)
        if tarefas.ativas() >= MAX_TAREFAS_SIMULTANEAS:
            return erro("Já há análises de vídeo em andamento. Tente de novo em alguns minutos.", 429)

        parametros = {
            "intervalo_s": _numero(request.form.get("intervalo_s"), 1.0, 0.2, 30.0),
            "max_frames": _numero(request.form.get("max_frames"), 40, 1, MAX_FRAMES_LIMITE, int),
        }
        com_audio = request.form.get("audio", "true").lower() != "false"

        pasta = Path(tempfile.mkdtemp(prefix="aida_video_srv_"))
        nome = secure_filename(arquivo.filename) or f"video{extensao}"
        if not nome.lower().endswith(extensao):
            nome += extensao
        caminho_video = pasta / "_entrada" / nome
        caminho_video.parent.mkdir()
        arquivo.save(caminho_video)

        id_ = tarefas.criar(pasta, arquivo.filename)
        if executar_em_thread:
            threading.Thread(
                target=_rodar, args=(id_, caminho_video, pasta, parametros, com_audio), daemon=True
            ).start()
        else:
            _rodar(id_, caminho_video, pasta, parametros, com_audio)
        return jsonify({"tarefa": id_, "estado": tarefas.ler(id_)["estado"]}), 202

    @app.get("/video/tarefa/<id_>")
    def consultar(id_):
        tarefa = tarefas.ler(id_)
        if tarefa is None:
            return erro("Tarefa não encontrada (ou expirada).", 404)
        tarefa.pop("pasta")
        return jsonify(tarefa)

    @app.get("/video/tarefa/<id_>/frame/<arquivo>")
    def frame(id_, arquivo):
        tarefa = tarefas.ler(id_)
        # So nomes gerados pelo extrator: nada de ../ nem arquivos arbitrarios.
        if tarefa is None or not NOME_FRAME.match(arquivo):
            abort(404)
        if request.args.get("tamanho") == "original":
            return send_from_directory(tarefa["pasta"], arquivo, mimetype="image/png", max_age=3600)
        # Padrao: miniatura JPEG. Um frame 4K em PNG tem ~20 MB; a linha do
        # tempo de um video de 30 s puxaria centenas de MB para exibir 150 px.
        miniatura = Path(tarefa["pasta"]) / "miniaturas" / arquivo.replace(".png", ".jpg")
        if not miniatura.is_file():
            original = Path(tarefa["pasta"]) / arquivo
            if not original.is_file():
                abort(404)
            miniatura.parent.mkdir(exist_ok=True)
            with Image.open(original) as imagem:
                imagem = imagem.convert("RGB")
                imagem.thumbnail((LADO_MINIATURA, LADO_MINIATURA), Image.Resampling.LANCZOS)
                imagem.save(miniatura, "JPEG", quality=82)
        return send_from_directory(miniatura.parent, miniatura.name, mimetype="image/jpeg", max_age=3600)

    return app


def main():
    porta = int(os.environ.get("PORT", PORTA_PADRAO))
    app = criar_app()
    print(f"AIDA Video em http://127.0.0.1:{porta}  (Core: {_url_core()})")
    app.run(host="127.0.0.1", port=porta, debug=False, threaded=True)


if __name__ == "__main__":
    main()
