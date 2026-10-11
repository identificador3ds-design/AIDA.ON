"""P1-3: bloqueio de conta no servidor e nenhum e-mail na configuração pública.

Antes: `admin_config` (leitura pública) publicava `accountStates` — o e-mail de cada conta
bloqueada ou excluída — e o bloqueio só era aplicado no navegador.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
ADMIN = (RAIZ / "scripts" / "script-administrador.js").read_text(encoding="utf-8")
REMOTA = (RAIZ / "scripts" / "aida-config-remota.js").read_text(encoding="utf-8")
SQL = (RAIZ / "docs" / "migracao-status-conta.sql").read_text(encoding="utf-8").lower()


def test_admin_nao_publica_accountstates():
    trecho = ADMIN[ADMIN.index("function salvarAdminConfig"):ADMIN.index("return configNormalizado;")]
    assert "accountStates: _privado, ...configPublica" in trecho
    assert "config: configPublica" in trecho and "config: configNormalizado" not in trecho


def test_admin_grava_status_no_banco_e_nao_apaga_a_linha():
    assert 'from("usuarios").delete()' not in ADMIN
    assert ".update({ status })" in ADMIN
    corpo = ADMIN[ADMIN.index("function aplicarAlteracaoConta"):]
    assert "publicarStatusConta(email" in corpo[:corpo.index("salvarAdminConfig(config)")]


def test_painel_funciona_antes_da_migracao():
    assert '.select("nome,email,status"' in ADMIN and '.select("nome,email",' in ADMIN


def test_migracao_trava_status_e_historico():
    assert "add column if not exists status" in SQL
    assert "status de conta só pode ser alterado pelo administrador" in SQL
    assert "config - 'accountstates'" in SQL
    assert "u.status <> 'active'" in SQL


def test_config_remota_nao_poe_email_na_url():
    assert "usuarios?select=email,status" in REMOTA
    assert "email=eq" not in REMOTA


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js não instalado")
def test_config_remota_guarda_so_a_propria_conta():
    """Configuração pública antiga com e-mails de terceiros não pode ficar no navegador."""
    script = """
    const armazenado = {
      "sb-nwzijdudhemuibsyzpub-auth-token": JSON.stringify({access_token: "t", user: {email: "Eu@x.com"}}),
      "AIDA_ADMIN_CONFIG": JSON.stringify({accountStates: {"outra@x.com": {status: "blocked"}}}),
    };
    global.window = global;
    global.localStorage = {getItem: k => armazenado[k] ?? null, setItem: (k, v) => { armazenado[k] = v; }};
    global.fetch = (url) => Promise.resolve({ok: true, json: () => Promise.resolve(
      url.includes("admin_config")
        ? [{config: {maintenanceMode: false, accountStates: {"terceiro@x.com": {status: "deleted"}}}}]
        : [{email: "eu@x.com", status: "blocked"}])});
    require(process.argv[1]);
    setTimeout(() => console.log(armazenado["AIDA_ADMIN_CONFIG"]), 50);
    """
    saida = subprocess.run(["node", "-e", script, str(RAIZ / "scripts" / "aida-config-remota.js")],
                           capture_output=True, text=True, encoding="utf-8", check=True).stdout
    config = json.loads(saida.strip().splitlines()[-1])
    assert config["accountStates"] == {"eu@x.com": {"status": "blocked"}}
