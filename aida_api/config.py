"""Configuracao da borda, toda por variavel de ambiente.

Nada de segredo em codigo: o repositorio ja carrega a chave anon do Supabase
no front-end, e essa e justamente a chave que NAO serve aqui. A borda usa a
service role, que so existe no ambiente de deploy.
"""

from __future__ import annotations

import os


def _int(nome, padrao):
    try:
        return int(os.environ.get(nome, padrao))
    except (TypeError, ValueError):
        return padrao


def _float(nome, padrao):
    try:
        return float(os.environ.get(nome, padrao))
    except (TypeError, ValueError):
        return padrao


def _bool(nome, padrao=False):
    valor = os.environ.get(nome)
    if valor is None:
        return padrao
    return valor.strip().lower() in {"1", "true", "sim", "yes", "on"}


# --- Camada 03: onde vive o Core ------------------------------------------- #
# O Core e o Space no Hugging Face (porta 7860). O Flask antigo em
# aida_modelo/site_api/app.py responde em dois estados e nao conhece
# INCONCLUSIVO: apontar para ele quebraria o contrato de tres estados.
CORE_URL = os.environ.get("AIDA_CORE_URL", "https://aidaon-aida-api.hf.space").rstrip("/")
CORE_TIMEOUT_S = _float("AIDA_CORE_TIMEOUT_S", 180.0)

# --- Camada 01: borda HTTP -------------------------------------------------- #
TAMANHO_MAX_MB = _int("AIDA_API_MAX_MB", 15)
TAMANHO_MAX_BYTES = TAMANHO_MAX_MB * 1024 * 1024
EXTENSOES_ACEITAS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".heic", ".heif", ".avif"}
CORS_ORIGENS = os.environ.get("AIDA_API_CORS", "*")

# Autenticacao. Em producao: Supabase (tabela api_keys, so o hash da chave).
SUPABASE_URL = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or ""
SUPABASE_TIMEOUT_S = _float("SUPABASE_TIMEOUT_S", 10.0)
TABELA_CHAVES = os.environ.get("AIDA_API_TABELA_CHAVES", "api_keys")
TABELA_CHAMADAS = os.environ.get("AIDA_API_TABELA_CHAMADAS", "api_calls")

# Chaves de desenvolvimento, separadas por virgula. Existem para rodar local
# sem Supabase; nunca devem ser definidas em producao.
CHAVES_DEV = [c.strip() for c in os.environ.get("AIDA_API_DEV_KEYS", "").split(",") if c.strip()]

PREFIXO_CHAVE = "aida_"

# --- Camada 02: orquestracao ------------------------------------------------ #
CACHE_TTL_S = _int("AIDA_API_CACHE_TTL_S", 900)
CACHE_MAX_ITENS = _int("AIDA_API_CACHE_MAX", 128)
CONCORRENCIA_MAX = _int("AIDA_API_CONCORRENCIA", 2)
ESPERA_FILA_S = _float("AIDA_API_ESPERA_FILA_S", 30.0)

# --- Limites de uso --------------------------------------------------------- #
LIMITE_PADRAO = _int("AIDA_API_LIMITE", 60)
JANELA_LIMITE_S = _int("AIDA_API_JANELA_S", 3600)

# --- Logs ------------------------------------------------------------------- #
# Retencao declarada no aviso de privacidade: o log guarda metadado da chamada
# (chave, rota, status, duracao, hash do arquivo), nunca a imagem enviada.
LOG_CHAMADAS = _bool("AIDA_API_LOG_CHAMADAS", True)
LOG_RETENCAO_DIAS = _int("AIDA_API_LOG_RETENCAO_DIAS", 90)


def supabase_configurado():
    return bool(SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY)


def modo_autenticacao():
    """'supabase' | 'dev' | 'ausente'."""
    if supabase_configurado():
        return "supabase"
    if CHAVES_DEV:
        return "dev"
    return "ausente"
