"""Logs de chamada: auditoria e diagnostico.

O que entra no registro e METADADO: prefixo da chave, rota, status, duracao,
tamanho e hash do arquivo, resultado devolvido. A imagem NAO entra, nem o nome
original do arquivo — o nome costuma carregar dado pessoal ("cpf-joao.jpg") e
nao ajuda em nada a diagnosticar.

O hash serve para reconhecer que duas chamadas trataram do mesmo arquivo sem
guardar o arquivo. A retencao declarada esta em AIDA_API_LOG_RETENCAO_DIAS e
precisa bater com o que o aviso de privacidade do site diz (docs/lgpd-inventario.md).
"""

from __future__ import annotations

import json
import logging
import sys
import threading
from datetime import datetime, timezone

import requests

from . import config

_logger = logging.getLogger("aida.api")
if not _logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter("%(message)s"))
    _logger.addHandler(_handler)
    _logger.setLevel(logging.INFO)


# Amostra recente em memoria: alimenta GET /v1/health sem exigir consulta ao
# banco a cada checagem de monitoramento.
_ultimas = []
_lock = threading.Lock()
_MAX_MEMORIA = 50


def ultimas(n=10):
    with _lock:
        return list(_ultimas[-n:])


def resumo():
    with _lock:
        amostra = list(_ultimas)
    if not amostra:
        return {"sample_size": 0}
    duracoes = [c.get("duration_seconds") or 0 for c in amostra]
    erros = [c for c in amostra if (c.get("status") or 0) >= 500]
    return {
        "sample_size": len(amostra),
        "avg_duration_seconds": round(sum(duracoes) / len(duracoes), 4),
        "max_duration_seconds": round(max(duracoes), 4),
        "server_errors": len(erros),
        "last_call_at": amostra[-1].get("at"),
    }


def registrar(evento):
    """Grava uma chamada: stdout sempre, Supabase quando configurado."""
    evento = dict(evento)
    evento.setdefault("at", datetime.now(timezone.utc).isoformat())

    with _lock:
        _ultimas.append(evento)
        del _ultimas[:-_MAX_MEMORIA]

    _logger.info(json.dumps({"aida_api": evento}, ensure_ascii=False, default=str))

    if config.LOG_CHAMADAS and config.supabase_configurado():
        threading.Thread(target=_gravar_supabase, args=(evento,), daemon=True).start()


def _gravar_supabase(evento):
    """Best-effort: o log e importante, mas nao a ponto de derrubar a analise."""
    try:
        requests.post(
            f"{config.SUPABASE_URL}/rest/v1/{config.TABELA_CHAMADAS}",
            json={
                "criada_em": evento.get("at"),
                "prefixo_chave": evento.get("key_prefix"),
                "rota": evento.get("route"),
                "status": evento.get("status"),
                "codigo_erro": evento.get("error_code"),
                "duracao_s": evento.get("duration_seconds"),
                "duracao_core_s": evento.get("core_seconds"),
                "hash_arquivo": evento.get("file_sha256"),
                "tamanho_bytes": evento.get("file_bytes"),
                "resultado": evento.get("result"),
                "cache": evento.get("cache"),
                "id_analise": evento.get("analysis_id"),
            },
            headers={
                "apikey": config.SUPABASE_SERVICE_ROLE_KEY,
                "Authorization": f"Bearer {config.SUPABASE_SERVICE_ROLE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal",
            },
            timeout=config.SUPABASE_TIMEOUT_S,
        )
    except requests.RequestException as exc:
        _logger.warning(json.dumps({"aida_api_log_falhou": str(exc)}))
