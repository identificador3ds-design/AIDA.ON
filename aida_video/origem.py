"""Checagem de origem no SERVIDOR (auditoria P2-1).

O CORS do app não basta no Hugging Face: o proxy do ``*.hf.space`` acrescenta
``Access-Control-Allow-Origin`` refletindo qualquer origem por cima da resposta
(medido em 11/10/2026: com ``ALLOWED_ORIGINS`` definido, uma página de outro
domínio continuava lendo as respostas). Aqui a requisição de navegador vinda de
origem não autorizada é recusada com 403 antes de chegar à rota.

Regras, só quando a variável de origens está definida (``*`` ou vazia = desligado):

* sem cabeçalho ``Origin`` → passa. Navegadores mandam ``Origin`` em todo POST e em
  chamadas ``fetch`` de outro domínio; quem não manda é cliente de servidor (curl,
  o AIDA Video chamando o Core), que o CORS também nunca barrou;
* origem igual ao próprio host → passa (páginas servidas pelo Space, como ``/teste``);
* origem na lista → passa; qualquer outra, inclusive ``null`` → 403.

Não é autenticação: um cliente fora do navegador forja ``Origin`` à vontade. O que
isto impede é outro site usar a API pelo navegador dos visitantes dele.
"""

from __future__ import annotations

import os
from urllib.parse import urlsplit

from flask import jsonify, request


def _normalizar(origem: str) -> str:
    return origem.strip().rstrip("/").lower()


def origens_configuradas(variavel: str) -> set[str] | None:
    """Origens autorizadas, ou None se a checagem está desligada."""
    valor = os.environ.get(variavel, "*").strip()
    origens = {_normalizar(o) for o in valor.split(",") if o.strip()}
    if not origens or "*" in origens:
        return None
    return origens


def origem_permitida(origem: str | None, permitidas: set[str], host: str) -> bool:
    if not origem:
        return True
    origem = _normalizar(origem)
    if origem == "null":
        return False
    if urlsplit(origem).netloc and urlsplit(origem).netloc == (host or "").lower():
        return True
    return origem in permitidas


def instalar(app, variavel: str, isenta=None) -> None:
    """Registra a checagem em ``app``. ``isenta(request)`` libera chamadas internas."""

    @app.before_request
    def _checar_origem():
        permitidas = origens_configuradas(variavel)
        if permitidas is None or (isenta is not None and isenta(request)):
            return None
        if origem_permitida(request.headers.get("Origin"), permitidas, request.host):
            return None
        return jsonify({"erro": "Origem não autorizada a usar esta API."}), 403
