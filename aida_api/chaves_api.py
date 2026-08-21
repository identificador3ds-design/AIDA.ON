"""Chaves de API: emissao, validacao, revogacao e listagem.

O banco guarda o HASH da chave, nunca o valor bruto. O valor aparece uma unica
vez, no momento da emissao — perdeu, emite outra. Um vazamento da tabela
`api_keys` nao entrega nenhuma chave utilizavel.

Sem Supabase configurado, a borda aceita chaves de desenvolvimento vindas de
AIDA_API_DEV_KEYS. Isso e para rodar local; em producao, o modo e supabase e a
ausencia das variaveis derruba a rota com 503 em vez de abrir a porta.
"""

from __future__ import annotations

import hashlib
import secrets
import threading
import time
from datetime import datetime, timezone

import requests

from . import config


class AutenticacaoIndisponivel(RuntimeError):
    """Nem Supabase nem chaves de desenvolvimento estao configurados."""


def _agora_iso():
    return datetime.now(timezone.utc).isoformat()


def hash_chave(chave):
    return hashlib.sha256(chave.encode("utf-8")).hexdigest()


def prefixo_de(chave):
    """Trecho exibivel da chave, para identifica-la em listagens e logs."""
    return chave[: len(config.PREFIXO_CHAVE) + 6]


def _cabecalhos():
    return {
        "apikey": config.SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {config.SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
    }


def _url_tabela(tabela=None):
    return f"{config.SUPABASE_URL}/rest/v1/{tabela or config.TABELA_CHAVES}"


def _exigir_supabase():
    if not config.supabase_configurado():
        raise AutenticacaoIndisponivel(
            "SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY nao estao definidos."
        )


# --------------------------------------------------------------------------- #
# Cache de validacao
#
# Uma consulta ao Supabase por requisicao coloca a latencia da rede no caminho
# critico de toda chamada. O cache guarda o resultado por poucos segundos: uma
# revogacao passa a valer depois desse intervalo, e esse atraso e o preco
# declarado. Para revogar na hora, reinicie o processo.
# --------------------------------------------------------------------------- #
_TTL_CACHE_VALIDACAO = 60
_cache_validacao = {}
_lock_cache = threading.Lock()


def limpar_cache():
    with _lock_cache:
        _cache_validacao.clear()


def _do_cache(hash_):
    with _lock_cache:
        item = _cache_validacao.get(hash_)
    if not item:
        return None
    expira, registro = item
    if expira <= time.time():
        with _lock_cache:
            _cache_validacao.pop(hash_, None)
        return None
    return registro


def _guardar_cache(hash_, registro):
    with _lock_cache:
        _cache_validacao[hash_] = (time.time() + _TTL_CACHE_VALIDACAO, registro)


# --------------------------------------------------------------------------- #
# Operacoes
# --------------------------------------------------------------------------- #
def gerar_chave(descricao, escopo="analyze:image", limite_por_janela=None, dias_validade=None):
    """Emite uma chave. Devolve (chave_bruta, registro).

    A chave bruta nao e recuperavel depois desta chamada.
    """
    _exigir_supabase()
    chave = config.PREFIXO_CHAVE + secrets.token_urlsafe(32)
    registro = {
        "hash_chave": hash_chave(chave),
        "prefixo": prefixo_de(chave),
        "descricao": descricao,
        "escopo": escopo,
        "limite_por_janela": limite_por_janela or config.LIMITE_PADRAO,
        "revogada": False,
        "criada_em": _agora_iso(),
    }
    if dias_validade:
        registro["expira_em"] = datetime.fromtimestamp(
            time.time() + int(dias_validade) * 86400, tz=timezone.utc
        ).isoformat()

    resposta = requests.post(
        _url_tabela(),
        json=registro,
        headers={**_cabecalhos(), "Prefer": "return=representation"},
        timeout=config.SUPABASE_TIMEOUT_S,
    )
    if resposta.status_code >= 400:
        raise RuntimeError(f"Supabase recusou a emissao ({resposta.status_code}): {resposta.text}")
    dados = resposta.json()
    return chave, (dados[0] if isinstance(dados, list) and dados else registro)


def validar_chave(chave):
    """Devolve o registro da chave, ou None se ela nao vale.

    Levanta AutenticacaoIndisponivel quando nao ha como validar — situacao de
    servidor mal configurado, que a rota traduz em 503, nunca em 401: dizer
    "chave invalida" quando o problema e o servidor manda o integrador procurar
    defeito no lugar errado.
    """
    if not chave:
        return None

    if config.CHAVES_DEV:
        if chave in config.CHAVES_DEV:
            return {
                "prefixo": prefixo_de(chave),
                "descricao": "chave de desenvolvimento (AIDA_API_DEV_KEYS)",
                "escopo": "analyze:image",
                "limite_por_janela": config.LIMITE_PADRAO,
                "revogada": False,
                "origem": "dev",
            }
        # Com chaves de desenvolvimento e sem Supabase, a lista local e a
        # unica fonte: chave fora dela e chave invalida (401), nao servidor
        # mal configurado (503).
        if not config.supabase_configurado():
            return None

    _exigir_supabase()

    hash_ = hash_chave(chave)
    registro = _do_cache(hash_)
    if registro is not None:
        return registro or None

    resposta = requests.get(
        _url_tabela(),
        params={"hash_chave": f"eq.{hash_}", "select": "*", "limit": "1"},
        headers=_cabecalhos(),
        timeout=config.SUPABASE_TIMEOUT_S,
    )
    if resposta.status_code >= 400:
        raise AutenticacaoIndisponivel(
            f"Supabase respondeu {resposta.status_code} ao validar a chave."
        )

    linhas = resposta.json()
    registro = linhas[0] if isinstance(linhas, list) and linhas else None

    if registro and _esta_valida(registro):
        registro["origem"] = "supabase"
        _guardar_cache(hash_, registro)
        _marcar_uso(hash_)
        return registro

    # Guarda tambem a negativa: senao, uma chave errada em repeticao vira uma
    # enxurrada de consultas ao Supabase — que e exatamente o que um ataque de
    # forca bruta produz.
    _guardar_cache(hash_, {})
    return None


def _esta_valida(registro):
    if registro.get("revogada"):
        return False
    expira_em = registro.get("expira_em")
    if expira_em:
        try:
            limite = datetime.fromisoformat(str(expira_em).replace("Z", "+00:00"))
            if limite <= datetime.now(timezone.utc):
                return False
        except ValueError:
            return False
    return True


def _marcar_uso(hash_):
    """Atualiza `ultimo_uso_em` sem segurar a resposta do usuario."""

    def tarefa():
        try:
            requests.patch(
                _url_tabela(),
                params={"hash_chave": f"eq.{hash_}"},
                json={"ultimo_uso_em": _agora_iso()},
                headers=_cabecalhos(),
                timeout=config.SUPABASE_TIMEOUT_S,
            )
        except requests.RequestException:
            pass  # metadado de conveniencia: falhar aqui nao invalida a chamada

    threading.Thread(target=tarefa, daemon=True).start()


def revogar_chave(prefixo):
    """Revoga por prefixo. Devolve quantas linhas foram afetadas."""
    _exigir_supabase()
    resposta = requests.patch(
        _url_tabela(),
        params={"prefixo": f"eq.{prefixo}"},
        json={"revogada": True, "revogada_em": _agora_iso()},
        headers={**_cabecalhos(), "Prefer": "return=representation"},
        timeout=config.SUPABASE_TIMEOUT_S,
    )
    if resposta.status_code >= 400:
        raise RuntimeError(f"Supabase recusou a revogacao ({resposta.status_code}): {resposta.text}")
    limpar_cache()
    linhas = resposta.json()
    return len(linhas) if isinstance(linhas, list) else 0


def listar_chaves(incluir_revogadas=False):
    """Lista as chaves. O hash nunca sai daqui — e material de verificacao."""
    _exigir_supabase()
    params = {
        "select": "prefixo,descricao,escopo,limite_por_janela,revogada,criada_em,ultimo_uso_em,expira_em",
        "order": "criada_em.desc",
    }
    if not incluir_revogadas:
        params["revogada"] = "eq.false"
    resposta = requests.get(
        _url_tabela(), params=params, headers=_cabecalhos(), timeout=config.SUPABASE_TIMEOUT_S
    )
    if resposta.status_code >= 400:
        raise RuntimeError(f"Supabase recusou a listagem ({resposta.status_code}): {resposta.text}")
    linhas = resposta.json()
    return linhas if isinstance(linhas, list) else []
