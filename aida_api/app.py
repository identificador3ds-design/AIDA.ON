"""Camada 01: a borda HTTP da AIDA API.

Esta e a unica camada que fala com a internet. Ela autentica a chave, valida
formato e tamanho, aplica a cota, entra na fila, delega ao AIDA Core e devolve
o resultado no contrato /v1. Nao existe aqui nenhuma linha de deteccao — e de
proposito: duas implementacoes da mesma decisao divergem, e a que diverge em
silencio e a que esta em producao.

Rodar local:

    export AIDA_API_DEV_KEYS=aida_teste
    python -m aida_api.app
    curl -X POST http://localhost:8000/v1/analyze/image \\
      -H "Authorization: Bearer aida_teste" -F "image=@foto.jpg"
"""

from __future__ import annotations

import functools
import hashlib
import os
import time
from pathlib import Path

from flask import Flask, g, jsonify, request
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

from . import cache as cache_mod
from . import chaves_api, cobranca, config, core, docs, limites, medicao, registro, usuarios
from .contrato import CONTRATO, VERSAO_CONTRATO, erro, mapear_analise

INICIADO_EM = time.time()

analises = cache_mod.CacheAnalises()
fila = cache_mod.Fila()
limitador = limites.LimitadorEmMemoria()
medidor = medicao.criar_medidor()

# Assinaturas de arquivo dos formatos aceitos. A checagem e barata e derruba na
# borda o que nem deveria ocupar uma vaga da fila; a validacao completa continua
# sendo do Core, que abre a imagem de verdade.
_ASSINATURAS = (
    (b"\xff\xd8\xff", "jpeg"),
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"BM", "bmp"),
)


def _parece_imagem(conteudo):
    if len(conteudo) < 12:
        return False
    for assinatura, _ in _ASSINATURAS:
        if conteudo.startswith(assinatura):
            return True
    marca = conteudo[4:12]
    # RIFF....WEBP (webp) e ....ftyp (heic/heif/avif) — contentores ISO-BMFF.
    if conteudo.startswith(b"RIFF") and conteudo[8:12] == b"WEBP":
        return True
    return marca.startswith(b"ftyp")


def criar_app():
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = config.TAMANHO_MAX_BYTES
    app.config["JSON_SORT_KEYS"] = False
    CORS(app, resources={r"/v1/*": {"origins": config.CORS_ORIGENS}})

    # ----------------------------------------------------------------- #
    # Erros: um formato so, para quem integra nao precisar de dois parsers
    # ----------------------------------------------------------------- #
    def responder_erro(codigo, mensagem, status, detalhes=None, cabecalhos=None):
        resposta = jsonify(erro(codigo, mensagem, detalhes))
        resposta.status_code = status
        for nome, valor in (cabecalhos or {}).items():
            resposta.headers[nome] = valor
        return resposta

    @app.errorhandler(404)
    def _404(_):
        return responder_erro("not_found", "Rota inexistente. Veja GET /v1/docs.", 404)

    @app.errorhandler(405)
    def _405(_):
        return responder_erro("not_found", "Metodo nao permitido nesta rota.", 405)

    @app.errorhandler(413)
    def _413(_):
        return responder_erro(
            "payload_too_large",
            f"O arquivo passa do limite de {config.TAMANHO_MAX_MB} MB.",
            413,
        )

    @app.errorhandler(HTTPException)
    def _http(exc):
        # Erros que o Werkzeug levanta antes da rota (multipart quebrado, por
        # exemplo) tambem saem no formato do contrato.
        codigo = "invalid_field" if exc.code and exc.code < 500 else "internal_error"
        return responder_erro(codigo, exc.description or "Requisicao invalida.", exc.code or 500)

    @app.errorhandler(Exception)
    def _500(exc):
        app.logger.exception("Falha nao tratada: %s", exc)
        return responder_erro(
            "internal_error", "Erro interno ao processar a requisicao.", 500
        )

    # ----------------------------------------------------------------- #
    # Autenticacao e cota
    # ----------------------------------------------------------------- #
    def _chave_do_cabecalho():
        cabecalho = request.headers.get("Authorization", "")
        if not cabecalho.startswith("Bearer "):
            return None
        return cabecalho[7:].strip() or None

    def exigir_chave(rota):
        @functools.wraps(rota)
        def envelope(*args, **kwargs):
            if config.modo_autenticacao() == "ausente":
                return responder_erro(
                    "auth_unavailable",
                    "Autenticacao nao configurada no servidor.",
                    503,
                )

            chave = _chave_do_cabecalho()
            if not chave:
                return responder_erro(
                    "missing_credentials",
                    "Envie a chave em 'Authorization: Bearer <chave>'.",
                    401,
                )

            try:
                registro_chave = chaves_api.validar_chave(chave)
            except chaves_api.AutenticacaoIndisponivel as exc:
                app.logger.error("Validacao indisponivel: %s", exc)
                return responder_erro(
                    "auth_unavailable",
                    "Nao foi possivel validar a chave agora. Tente de novo em instantes.",
                    503,
                )

            if not registro_chave:
                return responder_erro("invalid_key", "Chave invalida ou revogada.", 401)

            g.chave = registro_chave
            g.chave_id = chaves_api.hash_chave(chave)
            g.prefixo_chave = registro_chave.get("prefixo") or chaves_api.prefixo_de(chave)

            if chaves_api.tokens_esgotados(registro_chave):
                registro.registrar(
                    {
                        "route": request.path,
                        "key_prefix": g.prefixo_chave,
                        "status": 402,
                        "error_code": "quota_exhausted",
                    }
                )
                return responder_erro(
                    "quota_exhausted",
                    "Cota de análises do plano esgotada. Contate o suporte para ampliar.",
                    402,
                )

            veredito = limitador.consumir(
                g.chave_id, registro_chave.get("limite_por_janela")
            )
            g.cota = veredito
            if not veredito.permitido:
                registro.registrar(
                    {
                        "route": request.path,
                        "key_prefix": g.prefixo_chave,
                        "status": 429,
                        "error_code": "rate_limited",
                    }
                )
                return responder_erro(
                    "rate_limited",
                    "Cota da chave esgotada nesta janela.",
                    429,
                    cabecalhos=veredito.cabecalhos(),
                )

            resposta = rota(*args, **kwargs)
            try:
                for nome, valor in veredito.cabecalhos().items():
                    resposta.headers.setdefault(nome, valor)
            except AttributeError:
                pass  # resposta em tupla; a cota ja foi contabilizada
            return resposta

        return envelope

    # ----------------------------------------------------------------- #
    # Rotas publicas (sem chave): descobrir e monitorar
    # ----------------------------------------------------------------- #
    @app.get("/")
    def raiz():
        return jsonify(
            {
                "api": "AIDA API",
                "version": VERSAO_CONTRATO,
                "status": "online",
                "contract": "/v1/contract",
                "docs": "/v1/docs",
                "health": "/v1/health",
                "analyze": "POST /v1/analyze/image",
                "notice": "Indicio tecnico, nao prova. A chave e emitida fora de banda.",
            }
        )

    @app.get("/v1/contract")
    def contrato_publico():
        return jsonify(CONTRATO)

    @app.get("/v1/docs")
    def documentacao():
        return docs.pagina_html(), 200, {"Content-Type": "text/html; charset=utf-8"}

    @app.get("/v1/health")
    def saude():
        estado_core = core.saude()
        modulos = estado_core.get("modules")
        degradado = estado_core.get("status") != "ok"
        # Um modulo que deixou de carregar nao derruba o Core: ele responde 200
        # com um modulo a menos. Sem comparar com o esperado, a degradacao passa
        # despercebida ate alguem reclamar do resultado.
        esperados = {"forense", "clip", "rigid"}
        faltando = sorted(esperados - set(modulos)) if isinstance(modulos, list) else []

        corpo = {
            "api_version": VERSAO_CONTRATO,
            "status": "degraded" if (degradado or faltando) else "ok",
            "uptime_seconds": round(time.time() - INICIADO_EM, 1),
            "auth_mode": config.modo_autenticacao(),
            "core": {**estado_core, "url": config.CORE_URL, "missing_modules": faltando},
            "queue": fila.estado(),
            "cache": analises.estado(),
            "rate_limit": limitador.estado(),
            "recent_calls": registro.resumo(),
        }
        return jsonify(corpo), (200 if corpo["status"] == "ok" else 503)

    # ----------------------------------------------------------------- #
    # Creditos (medicao por ciclo) — ver medicao.py
    # ----------------------------------------------------------------- #
    def _debitar_creditos(creditos, tipo, referencia, evento):
        """(resposta_de_recusa | None, debito)."""
        try:
            debito = medidor.debitar(g.chave_id, creditos, tipo, referencia)
        except medicao.MedicaoIndisponivel as exc:
            app.logger.error("Medicao indisponivel: %s", exc)
            registro.registrar({**evento, "status": 503, "error_code": "billing_unavailable"})
            return responder_erro(
                "billing_unavailable",
                "Nao foi possivel consultar os creditos agora. Tente de novo em instantes.",
                503,
                cabecalhos={"Retry-After": "30"},
            ), None

        if debito.permitido:
            return None, debito

        registro.registrar({**evento, "status": 429, "error_code": "credits_exhausted"})
        cabecalhos = {**debito.cabecalhos(), "Retry-After": str(debito.segundos_para_renovar())}
        return responder_erro(
            "credits_exhausted",
            (
                f"Os {debito.incluidos} creditos do plano {debito.plano_id} acabaram neste ciclo. "
                f"Eles renovam em {debito.ciclo_fim.date().isoformat()}. "
                "Para continuar agora, contrate um plano pago em https://aida-on.com.br/precos."
            ),
            429,
            {
                "plan_id": debito.plano_id,
                "credits_included": debito.incluidos,
                "credits_used": debito.usados,
                "credits_requested": creditos,
                "cycle_reset": debito.ciclo_fim.isoformat(),
            },
            cabecalhos=cabecalhos,
        ), debito

    def _estornar_creditos(debito, referencia):
        try:
            medidor.estornar(g.chave_id, debito, referencia)
        except medicao.MedicaoIndisponivel as exc:
            # A analise ja falhou para o cliente; o estorno perdido fica no log
            # para conciliacao manual em vez de mascarar o erro original.
            app.logger.error("Estorno de creditos falhou (%s): %s", referencia, exc)

    @app.get("/v1/usage")
    @exigir_chave
    def uso_da_chave():
        try:
            debito = medidor.uso(g.chave_id)
        except medicao.MedicaoIndisponivel as exc:
            app.logger.error("Medicao indisponivel: %s", exc)
            return responder_erro(
                "billing_unavailable", "Nao foi possivel consultar os creditos agora.", 503
            )
        return jsonify({"api_version": VERSAO_CONTRATO, **debito.resumo()})

    # ----------------------------------------------------------------- #
    # Checkout — o preco sai do servidor, nunca do corpo da requisicao
    # ----------------------------------------------------------------- #
    @app.post("/v1/billing/checkout")
    def checkout():
        token = _chave_do_cabecalho()
        try:
            usuario = usuarios.usuario_do_token(token)
        except usuarios.AutenticacaoIndisponivel as exc:
            app.logger.error("Autenticacao de usuario indisponivel: %s", exc)
            return responder_erro("auth_unavailable", "Nao foi possivel validar a sessao agora.", 503)
        if not usuario:
            return responder_erro(
                "missing_credentials", "Entre na sua conta para contratar um plano.", 401
            )

        try:
            cotacao = cobranca.cotar_checkout(request.get_json(silent=True))
        except cobranca.ErroCheckout as exc:
            registro.registrar({"route": request.path, "status": exc.status, "error_code": exc.codigo})
            return responder_erro(exc.codigo, exc.mensagem, exc.status, exc.detalhes)

        registro.registrar(
            {"route": request.path, "status": 501, "plan_id": cotacao["plan_id"],
             "market": cotacao["market"], "billing_cycle": cotacao["billing_cycle"]}
        )
        # Ponto de integracao do gateway: com checkout.enabled e o price id
        # mapeado no config, aqui entra a criacao da sessao de pagamento com o
        # valor de `cotacao` — nunca com valor vindo do cliente.
        return responder_erro(
            "gateway_not_configured",
            "O pagamento online ainda nao esta disponivel. A equipe conclui a contratacao.",
            501,
            {"quote": cotacao},
        )

    # ----------------------------------------------------------------- #
    # Analise
    # ----------------------------------------------------------------- #
    @app.post("/v1/analyze/image")
    @exigir_chave
    def analisar_imagem():
        inicio = time.perf_counter()

        arquivo = request.files.get("image")
        if arquivo is None or not arquivo.filename:
            return responder_erro(
                "missing_image", "Envie o arquivo no campo 'image'.", 400
            )

        bruto_evidencia = (request.form.get("evidence") or "true").strip().lower()
        if bruto_evidencia not in {"true", "false"}:
            return responder_erro(
                "invalid_field", "O campo 'evidence' aceita 'true' ou 'false'.", 400
            )
        com_evidencias = bruto_evidencia == "true"

        extensao = Path(arquivo.filename).suffix.lower()
        if extensao not in config.EXTENSOES_ACEITAS:
            return responder_erro(
                "unsupported_format",
                "Formato nao aceito.",
                400,
                {"accepted": sorted(config.EXTENSOES_ACEITAS)},
            )

        conteudo = arquivo.read()
        if not conteudo:
            return responder_erro("invalid_image", "O arquivo enviado esta vazio.", 400)
        if len(conteudo) > config.TAMANHO_MAX_BYTES:
            return responder_erro(
                "payload_too_large",
                f"O arquivo passa do limite de {config.TAMANHO_MAX_MB} MB.",
                413,
            )
        if not _parece_imagem(conteudo):
            return responder_erro(
                "invalid_image",
                "O conteudo enviado nao corresponde a uma imagem.",
                400,
            )

        digest = hashlib.sha256(conteudo).hexdigest()
        chave_cache = cache_mod.chave_conteudo(conteudo, com_evidencias)

        evento = {
            "route": "/v1/analyze/image",
            "key_prefix": getattr(g, "prefixo_chave", None),
            "file_sha256": digest,
            "file_bytes": len(conteudo),
            "evidence": com_evidencias,
        }

        # Creditos: debita ANTES do Core (duas chamadas simultaneas nao passam
        # juntas do limite do plano gratis) e estorna se a analise falhar.
        recusa, debito = _debitar_creditos(cobranca.creditos_imagem(), "image", digest, evento)
        if recusa is not None:
            return recusa

        def estornar():
            _estornar_creditos(debito, digest)

        em_cache = analises.obter(chave_cache)
        if em_cache:
            id_analise, resposta_core = em_cache
            corpo = mapear_analise(
                resposta_core,
                analysis_id=id_analise,
                duracao_borda_s=time.perf_counter() - inicio,
            )
            registro.registrar(
                {**evento, "status": 200, "cache": "hit", "result": corpo["result"],
                 "analysis_id": id_analise,
                 "duration_seconds": round(time.perf_counter() - inicio, 4)}
            )
            resposta = jsonify(corpo)
            resposta.headers["X-AIDA-Cache"] = "hit"
            resposta.headers.update(debito.cabecalhos())
            return resposta

        # O nome original nao vai para o Core: ele nao muda a analise e costuma
        # carregar dado pessoal. So a extensao viaja, porque decide o decoder.
        nome_neutro = f"{digest[:16]}{extensao}"

        try:
            with fila:
                resposta_core, duracao_core = core.analisar(
                    conteudo, nome_neutro, evidencias=com_evidencias
                )
        except cache_mod.FilaCheia:
            estornar()
            registro.registrar({**evento, "status": 503, "error_code": "busy"})
            return responder_erro(
                "busy",
                "A API esta com todas as vagas de analise ocupadas.",
                503,
                cabecalhos={"Retry-After": "30"},
            )
        except core.CoreIndisponivel as exc:
            app.logger.error("Core indisponivel: %s", exc)
            estornar()
            registro.registrar({**evento, "status": 503, "error_code": "core_unavailable"})
            return responder_erro(
                "core_unavailable",
                "O motor de analise nao respondeu. Tente novamente em instantes.",
                503,
                cabecalhos={"Retry-After": "30"},
            )
        except core.CoreErro as exc:
            # 4xx do Core e problema da requisicao: repassa o significado em vez
            # de virar 500 e mandar o integrador procurar defeito no servidor.
            mapa = {
                400: ("invalid_image", "O Core recusou a imagem enviada.", 400),
                413: ("payload_too_large", "Arquivo acima do limite aceito pelo Core.", 413),
                415: ("unsupported_format", "Formato nao aceito pelo Core.", 400),
                # 502/503/504 aqui ja passaram pelas novas tentativas de core.py.
                502: ("core_unavailable", "O motor de analise esta iniciando ou indisponivel. Tente novamente em instantes.", 503),
                503: ("core_unavailable", "O motor de analise esta iniciando ou indisponivel. Tente novamente em instantes.", 503),
                504: ("core_unavailable", "O motor de analise esta iniciando ou indisponivel. Tente novamente em instantes.", 503),
            }
            codigo, mensagem, status = mapa.get(
                exc.status, ("core_error", "O motor de analise respondeu com erro.", 502)
            )
            app.logger.error("Core respondeu %s: %s", exc.status, exc.corpo)
            estornar()
            registro.registrar({**evento, "status": status, "error_code": codigo})
            cabecalhos = {"Retry-After": "30"} if status == 503 else None
            return responder_erro(codigo, mensagem, status, cabecalhos=cabecalhos)

        id_analise = resposta_core.get("id_analise") or digest[:32]
        analises.guardar(chave_cache, id_analise, resposta_core)

        corpo = mapear_analise(
            resposta_core,
            analysis_id=id_analise,
            duracao_borda_s=time.perf_counter() - inicio,
        )
        registro.registrar(
            {
                **evento,
                "status": 200,
                "cache": "miss",
                "result": corpo["result"],
                "analysis_id": id_analise,
                "core_seconds": round(duracao_core, 4),
                "duration_seconds": round(time.perf_counter() - inicio, 4),
            }
        )
        resposta = jsonify(corpo)
        resposta.headers["X-AIDA-Cache"] = "miss"
        resposta.headers.update(debito.cabecalhos())
        return resposta

    @app.get("/v1/analysis/<analysis_id>")
    @exigir_chave
    def recuperar_analise(analysis_id):
        resposta_core = analises.obter_por_id(analysis_id)
        if not resposta_core:
            # Recalcular aqui devolveria numeros possivelmente diferentes dos que
            # o integrador ja recebeu. Uma consulta que contradiz a analise que a
            # originou e pior do que consulta nenhuma.
            return responder_erro(
                "not_found",
                "Analise fora do cache. Envie a imagem novamente em POST /v1/analyze/image.",
                404,
            )
        return jsonify(mapear_analise(resposta_core, analysis_id=analysis_id))

    @app.get("/v1/evidence/<analysis_id>/<mapa>")
    @exigir_chave
    def evidencia(analysis_id, mapa):
        try:
            conteudo, tipo = core.mapa_evidencia(analysis_id, mapa)
        except core.CoreIndisponivel:
            return responder_erro("core_unavailable", "O motor de analise nao respondeu.", 503)
        except core.CoreErro as exc:
            if exc.status == 404:
                return responder_erro(
                    "not_found", "Mapa de evidencia inexistente ou expirado.", 404
                )
            return responder_erro("core_error", "Falha ao obter o mapa de evidencia.", 502)
        return conteudo, 200, {"Content-Type": tipo, "Cache-Control": "private, max-age=300"}

    return app


app = criar_app()


if __name__ == "__main__":
    porta = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=porta)
