"""Camada 03: cliente do AIDA Core.

O Core e o servico que ja roda hoje (Space no Hugging Face, porta 7860) e que
contem TODA a logica de deteccao: extracao, modulos, fusao calibrada e politica
de decisao. Esta camada nao duplica nada disso — ela so fala HTTP com ele.

Trocar o Core de lugar (Space, container proprio, maquina local) e mudar
AIDA_CORE_URL. Nenhuma outra parte da borda sabe onde ele esta.
"""

from __future__ import annotations

import time

import requests

from . import config


class CoreIndisponivel(RuntimeError):
    """O Core nao respondeu: rede, DNS, timeout ou Space hibernando."""


class CoreErro(RuntimeError):
    """O Core respondeu, mas com erro. `status` e `corpo` vem dele."""

    def __init__(self, status, corpo=None, mensagem=None):
        super().__init__(mensagem or f"O AIDA Core respondeu {status}.")
        self.status = status
        self.corpo = corpo if isinstance(corpo, dict) else {}


def _url(caminho):
    return f"{config.CORE_URL}{caminho}"


def _json_ou_vazio(resposta):
    try:
        dados = resposta.json()
        return dados if isinstance(dados, dict) else {}
    except ValueError:
        return {}


def analisar(conteudo, nome_arquivo, evidencias=True, timeout=None):
    """POST /analisar no Core. Devolve (resposta_bruta, duracao_s)."""
    inicio = time.perf_counter()
    try:
        resposta = requests.post(
            _url("/analisar"),
            files={"imagem": (nome_arquivo, conteudo)},
            data={
                "evidencias": "true" if evidencias else "false",
                # A borda nunca pede gravacao no historico do Core: quem integra
                # e dono do proprio armazenamento, e guardar do lado de ca criaria
                # uma copia de dado do usuario que ninguem pediu.
                "historico_habilitado": "false",
            },
            timeout=timeout or config.CORE_TIMEOUT_S,
        )
    except requests.RequestException as exc:
        raise CoreIndisponivel(str(exc)) from exc

    duracao = time.perf_counter() - inicio

    if resposta.status_code >= 400:
        raise CoreErro(resposta.status_code, _json_ou_vazio(resposta))

    dados = _json_ou_vazio(resposta)
    if not dados:
        raise CoreErro(502, {}, "O AIDA Core devolveu um corpo que nao e JSON.")
    return dados, duracao


def mapa_evidencia(id_analise, nome_mapa, timeout=None):
    """GET /evidencia/<id>/<mapa> no Core. Devolve (bytes, content_type)."""
    try:
        resposta = requests.get(
            _url(f"/evidencia/{id_analise}/{nome_mapa}"),
            timeout=timeout or config.SUPABASE_TIMEOUT_S * 3,
        )
    except requests.RequestException as exc:
        raise CoreIndisponivel(str(exc)) from exc

    if resposta.status_code >= 400:
        raise CoreErro(resposta.status_code, _json_ou_vazio(resposta))
    return resposta.content, resposta.headers.get("Content-Type", "image/png")


def saude(timeout=8.0):
    """Estado do Core, para o /v1/health. Nunca levanta: devolve o diagnostico."""
    inicio = time.perf_counter()
    try:
        resposta = requests.get(_url("/saude"), timeout=timeout)
        latencia = round(time.perf_counter() - inicio, 4)
        corpo = _json_ou_vazio(resposta)
        if resposta.status_code >= 400:
            return {
                "reachable": True,
                "status": "degraded",
                "http_status": resposta.status_code,
                "latency_seconds": latencia,
                "detail": corpo or None,
            }
        # O Core chama a lista de 'modulos_carregados' em /saude e de 'modulos'
        # na raiz; aceitamos as duas para o /v1/health nao ficar refem de qual
        # rota respondeu.
        modulos = corpo.get("modulos_carregados") or corpo.get("modulos") or corpo.get("modules")
        politica = corpo.get("politica") if isinstance(corpo.get("politica"), dict) else {}
        pronto = corpo.get("pronto")
        return {
            "reachable": True,
            # `pronto: false` e o caso em que o Core responde 200 sem modelo
            # carregado: alcancavel e inutil ao mesmo tempo.
            "status": "ok" if pronto is not False else "degraded",
            "http_status": resposta.status_code,
            "latency_seconds": latencia,
            "ready": pronto,
            "modules": modulos,
            "model_version": corpo.get("versao_modelo") or politica.get("versao_modelo"),
            "warnings": corpo.get("avisos") or [],
        }
    except requests.RequestException as exc:
        return {
            "reachable": False,
            "status": "unreachable",
            "latency_seconds": round(time.perf_counter() - inicio, 4),
            "detail": str(exc),
        }
