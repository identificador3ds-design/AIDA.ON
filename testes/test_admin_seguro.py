"""Painel administrativo: as defesas que não podem regredir.

O site é estático e público. Estes testes travam o que garante que o painel
não dependa de segredo no front-end nem de decisão tomada no navegador.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
PAGINA = (RAIZ / "pages" / "index-admin.html").read_text(encoding="utf-8")
SCRIPT = (RAIZ / "scripts" / "script-administrador.js").read_text(encoding="utf-8")
SQL = (RAIZ / "docs" / "migracao-admin-seguro.sql").read_text(encoding="utf-8").lower()
SW = (RAIZ / "service-worker.js").read_text(encoding="utf-8")


def _arquivos_publicados():
    """Arquivos versionados que a Vercel serve (pastas liberadas no .vercelignore)."""
    saida = subprocess.run(["git", "ls-files"], cwd=RAIZ, capture_output=True, text=True, check=True).stdout
    publicados = {"pages", "scripts", "styles", "index.html", "service-worker.js", "vercel.json", "manifest.webmanifest"}
    return [RAIZ / caminho for caminho in saida.splitlines() if caminho.split("/")[0] in publicados
            and caminho.endswith((".html", ".js", ".css", ".json", ".webmanifest"))]


def test_nenhuma_senha_ou_email_administrativo_no_site_publicado():
    """Senha nunca vai para o repositório; o e-mail de login do painel não é publicado."""
    for arquivo in _arquivos_publicados():
        conteudo = arquivo.read_text(encoding="utf-8", errors="ignore").lower()
        assert "admin3ds" not in conteudo, f"senha em {arquivo}"
        assert "aida@gmail.com.br" not in conteudo, f"e-mail administrativo em {arquivo}"
        assert "service_role" not in conteudo, f"chave de serviço citada em {arquivo}"


def test_migracao_nao_contem_senha():
    assert "admin3ds" not in SQL
    assert "encrypted_password" not in SQL


def test_pagina_sem_script_inline_nem_handlers():
    """Com CSP sem 'unsafe-inline', qualquer script embutido seria bloqueado — e é XSS em potencial."""
    assert not re.search(r"<script(?![^>]*\bsrc=)[^>]*>", PAGINA)
    assert not re.search(r"\son[a-z]+\s*=", PAGINA, re.I)
    assert 'name="robots" content="noindex' in PAGINA


def test_sessao_do_painel_fica_na_aba_e_nao_no_localstorage():
    assert 'storageKey: "aida-admin-auth"' in SCRIPT
    assert "storage: ARMAZENAMENTO" in SCRIPT
    assert "window.sessionStorage" in SCRIPT
    assert 'localStorage.setItem("usuarioTipo"' not in SCRIPT


def test_painel_so_abre_depois_do_servidor_confirmar():
    corpo = SCRIPT[SCRIPT.index("async function abrirPainel"):]
    assert corpo.index('rpc("admin_registrar_acesso")') < corpo.index('mostrarEtapa("painel")')


def test_painel_exige_segundo_fator_e_expira():
    assert "mfa.challengeAndVerify" in SCRIPT and "mfa.enroll" in SCRIPT
    assert "INATIVIDADE_MS" in SCRIPT and "SESSAO_MAXIMA_MS" in SCRIPT
    assert 'signOut({ scope: "global" })' in SCRIPT


def test_login_nao_revela_se_a_conta_existe():
    mensagens = re.findall(r'mensagemPortao\("E-mail ou senha inválidos\."\)', SCRIPT)
    assert len(mensagens) >= 2  # senha errada e conta sem papel admin: mesma resposta


def test_e_admin_exige_papel_2fa_e_lista():
    funcao = SQL[SQL.index("create or replace function public.e_admin()"):]
    funcao = funcao[:funcao.index("$$;")]
    assert "'role') = 'admin'" in funcao
    assert "->> 'aal') = 'aal2'" in funcao
    assert "public.admin_contas" in funcao


def test_navegador_so_le_chaves_e_escreve_pelas_funcoes():
    assert "revoke all on public.api_keys from anon, authenticated;" in SQL
    assert not re.search(r"grant\s+(insert|update|delete|all)[^;]*on public\.api_keys", SQL)
    assert "hash_chave" not in SQL[SQL.index("grant select (id"):SQL.index("on public.api_keys to authenticated")]
    for funcao in ("admin_emitir_chave", "admin_atualizar_chave", "admin_adicionar_tokens",
                   "admin_zerar_uso_chave", "admin_revogar_chave", "admin_resumo"):
        corpo = SQL[SQL.index(f"function public.{funcao}("):]
        corpo = corpo[:corpo.index("$$;")]
        assert "perform public.exigir_admin();" in corpo, funcao


def test_auditoria_e_somente_acrescimo():
    assert "before update or delete on public.admin_audit" in SQL
    assert not re.search(r"grant\s+(insert|update|delete|all)[^;]*on public\.admin_audit", SQL)


def test_chave_emitida_no_banco_tem_o_formato_da_api():
    from aida_api import config

    assert config.PREFIXO_CHAVE == "aida_"
    assert "'aida_' || rtrim(translate(encode(extensions.gen_random_bytes(32), 'base64')" in SQL
    assert f"left(v_chave, {len(config.PREFIXO_CHAVE) + 6})" in SQL
    assert "encode(extensions.digest(v_chave, 'sha256'), 'hex')" in SQL


def test_rota_admin_sem_cache_e_com_csp_restrita():
    vercel = json.loads((RAIZ / "vercel.json").read_text(encoding="utf-8"))
    regras = {regra["source"]: {h["key"]: h["value"] for h in regra["headers"]} for regra in vercel["headers"]}

    for rota in ("/admin", "/pages/index-admin(.html)?"):
        cabecalhos = regras[rota]
        assert cabecalhos["Cache-Control"].startswith("no-store")
        assert "noindex" in cabecalhos["X-Robots-Tag"]
        csp = cabecalhos["Content-Security-Policy"]
        assert "frame-ancestors 'none'" in csp and "default-src 'none'" in csp
        assert "unsafe-inline" not in csp and "unsafe-eval" not in csp


def test_service_worker_nao_guarda_o_painel():
    assert "index-admin.html" not in SW[SW.index("APP_SHELL"):SW.index("];")]
    assert "script-administrador" in SW[SW.index("addEventListener(\"fetch\""):]
