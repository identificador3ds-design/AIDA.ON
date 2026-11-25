"""Quem esta comprando: o usuario logado no site (Supabase Auth).

O checkout nao usa chave de API — quem contrata e uma pessoa com conta no
site. O front-end manda o access token da sessao do Supabase, e a borda
confirma com o proprio Supabase (GET /auth/v1/user) em vez de decodificar o
JWT localmente: assim uma sessao encerrada ou uma conta apagada deixa de valer
na hora, sem a borda precisar do segredo de assinatura.

Sem Supabase, `AIDA_API_DEV_USUARIOS` (tokens separados por virgula) libera o
checkout local. Nunca definir em producao.
"""

from __future__ import annotations

import os

import requests

from . import config


class AutenticacaoIndisponivel(RuntimeError):
    pass


def _tokens_dev():
    return [t.strip() for t in os.environ.get("AIDA_API_DEV_USUARIOS", "").split(",") if t.strip()]


def usuario_do_token(token):
    """Devolve {'id', 'email'} ou None. Levanta AutenticacaoIndisponivel se nao ha como validar."""
    if not token:
        return None

    dev = _tokens_dev()
    if dev and not config.supabase_configurado():
        return {"id": f"dev:{token}", "email": None} if token in dev else None

    if not config.supabase_configurado():
        raise AutenticacaoIndisponivel("Supabase nao configurado.")

    try:
        resposta = requests.get(
            f"{config.SUPABASE_URL}/auth/v1/user",
            headers={"apikey": config.SUPABASE_SERVICE_ROLE_KEY, "Authorization": f"Bearer {token}"},
            timeout=config.SUPABASE_TIMEOUT_S,
        )
    except requests.RequestException as exc:
        raise AutenticacaoIndisponivel(str(exc)) from exc

    if resposta.status_code in (401, 403):
        return None
    if resposta.status_code >= 400:
        raise AutenticacaoIndisponivel(f"Supabase respondeu {resposta.status_code}.")
    dados = resposta.json()
    return {"id": dados.get("id"), "email": dados.get("email")} if dados.get("id") else None
