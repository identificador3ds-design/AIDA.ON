"""Rotas HTTP da analise de texto, registradas por `aida_documents.servidor`.

Um documento longo leva de segundos a minutos (o modelo de linguagem roda em CPU),
entao a analise e por tarefa, como no AIDA Video:

    POST /documento/texto/analisar       -> 202 {"tarefa": id}   (campo "documento")
    GET  /documento/texto/tarefa/<id>    -> estado, progresso e, no fim, o relatorio
    GET  /documento/texto/saude          -> formatos, limites, modelo e calibracao por idioma

Uma analise por vez (o modelo ocupa todos os nucleos), com fila curta. O arquivo
fica so em memoria. O relatorio traz os trechos do texto, necessarios para o
destaque na tela; ele tambem fica so em memoria e e apagado depois de TTL_TAREFA_S.
"""

from __future__ import annotations

import importlib.util
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from flask import jsonify, request

from .detector import carregar_calibracao
from .extracao import EXTENSOES_TEXTO, FormatoNaoSuportado
from .perplexidade import nome_do_modelo

TAMANHO_MAX_MB = 20
TTL_TAREFA_S = 15 * 60
MAX_NA_FILA = 4
IDIOMAS = ("pt", "en")


class TarefasTexto:
    def __init__(self):
        self._dados = {}
        self._trava = threading.Lock()

    def criar(self, nome):
        id_ = uuid.uuid4().hex
        with self._trava:
            self._dados[id_] = {
                "id": id_, "estado": "fila", "documento": nome, "criada_em": time.time(),
                "progresso": {"feitos": 0, "total": None}, "relatorio": None, "erro": None,
            }
        return id_

    def atualizar(self, id_, **campos):
        with self._trava:
            if id_ in self._dados:
                self._dados[id_].update(campos)

    def ler(self, id_):
        with self._trava:
            tarefa = self._dados.get(id_)
            return dict(tarefa) if tarefa else None

    def pendentes(self):
        with self._trava:
            return sum(t["estado"] in ("fila", "analisando") for t in self._dados.values())

    def limpar_antigas(self, agora=None):
        agora = agora or time.time()
        with self._trava:
            vencidas = [i for i, t in self._dados.items()
                        if agora - t["criada_em"] > TTL_TAREFA_S and t["estado"] in ("concluida", "erro")]
            for id_ in vencidas:
                del self._dados[id_]
        return len(vencidas)


def registrar(app):
    """app.config aceita, para os testes: TEXTO_MODELO (modelo falso), TEXTO_CALIBRACAO
    (dict) e TEXTO_SINCRONO (roda a analise dentro do POST)."""
    tarefas = TarefasTexto()
    fila = ThreadPoolExecutor(max_workers=1, thread_name_prefix="aida-texto")
    app.config["TAREFAS_TEXTO"] = tarefas

    def erro(mensagem, status):
        return jsonify({"erro": mensagem}), status

    def executar(id_, dados, nome):
        from .detector import analisar_texto_bytes

        tarefas.atualizar(id_, estado="analisando")
        try:
            relatorio = analisar_texto_bytes(
                dados, nome,
                modelo=app.config.get("TEXTO_MODELO"),
                calibracao=app.config.get("TEXTO_CALIBRACAO"),
                progresso=lambda feitos, total: tarefas.atualizar(id_, progresso={"feitos": feitos, "total": total}),
            )
            relatorio["documento"] = nome
            tarefas.atualizar(id_, estado="concluida", relatorio=relatorio)
        except FormatoNaoSuportado as exc:
            tarefas.atualizar(id_, estado="erro", erro=str(exc))
        except Exception:
            app.logger.exception("falha na análise de texto")
            tarefas.atualizar(id_, estado="erro", erro="Não foi possível ler este documento (arquivo corrompido ou protegido).")

    @app.get("/documento/texto/saude")
    def texto_saude():
        calibracao = app.config.get("TEXTO_CALIBRACAO")
        calibracao = carregar_calibracao() if calibracao is None else calibracao
        tem_modelo = app.config.get("TEXTO_MODELO") is not None or all(
            importlib.util.find_spec(m) is not None for m in ("torch", "transformers")
        )
        return jsonify({
            "status": "online",
            "servico": "AIDA Documents · texto",
            "tamanho_max_mb": TAMANHO_MAX_MB,
            "extensoes": sorted(EXTENSOES_TEXTO),
            "modelo_de_linguagem": tem_modelo,
            "idiomas": {i: {"modelo": nome_do_modelo(i), "calibrado": bool(calibracao.get(i, {}).get("calibrado"))}
                        for i in IDIOMAS},
            "fila": tarefas.pendentes(),
        })

    @app.post("/documento/texto/analisar")
    def texto_analisar():
        tarefas.limpar_antigas()
        arquivo = request.files.get("documento")
        if arquivo is None or not arquivo.filename:
            return erro("Envie o arquivo no campo 'documento'.", 400)
        if Path(arquivo.filename).suffix.lower() not in EXTENSOES_TEXTO:
            return erro("Envie um arquivo PDF, DOCX ou TXT.", 400)
        dados = arquivo.read(TAMANHO_MAX_MB * 1024 * 1024 + 1)
        if len(dados) > TAMANHO_MAX_MB * 1024 * 1024:
            return erro(f"O arquivo passa de {TAMANHO_MAX_MB} MB.", 413)
        if tarefas.pendentes() >= MAX_NA_FILA:
            return erro("O servidor está ocupado com outras análises. Tente de novo em um minuto.", 429)
        id_ = tarefas.criar(arquivo.filename)
        if app.config.get("TEXTO_SINCRONO"):
            executar(id_, dados, arquivo.filename)
        else:
            fila.submit(executar, id_, dados, arquivo.filename)
        return jsonify({"tarefa": id_}), 202

    @app.get("/documento/texto/tarefa/<id_>")
    def texto_tarefa(id_):
        tarefa = tarefas.ler(id_)
        if tarefa is None:
            return erro("Análise não encontrada (pode ter expirado). Envie o documento de novo.", 404)
        tarefa.pop("criada_em", None)
        return jsonify(tarefa)
