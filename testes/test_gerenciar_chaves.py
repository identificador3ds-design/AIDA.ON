"""CLI de chaves: `assinar` e `cancelar-assinatura` (aida_api/gerenciar_chaves.py).

O Supabase é dublado no nível do `requests`: cada chamada é gravada e respondida
por uma tabela em memória. Verifica-se o que vai para o banco (termos copiados
do pricing.json, desativação da assinatura anterior, tokens_total zerado) e as
recusas antes de qualquer escrita.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from aida_api import config, gerenciar_chaves  # noqa: E402

URL = "https://exemplo.supabase.co"
CHAVE = {"id": "11111111-1111-1111-1111-111111111111", "prefixo": "aida_ab12cd", "descricao": "app",
         "revogada": False, "tokens_total": 500}


class Resposta:
    def __init__(self, status, corpo):
        self.status_code = status
        self._corpo = corpo
        self.text = str(corpo)

    def json(self):
        return self._corpo


class SupabaseFalso:
    """Responde como o PostgREST para as tabelas usadas pela CLI."""

    def __init__(self, chaves=(CHAVE,), assinaturas_ativas=1, falhar_post=False):
        self.chaves = [dict(c) for c in chaves]
        self.ativas = assinaturas_ativas
        self.falhar_post = falhar_post
        self.chamadas = []

    def _tabela(self, url):
        return url.rsplit("/", 1)[-1]

    def get(self, url, params=None, headers=None, timeout=None):
        self.chamadas.append(("GET", self._tabela(url), params, None, headers))
        prefixo = params["prefixo"].removeprefix("eq.")
        return Resposta(200, [c for c in self.chaves if c["prefixo"] == prefixo])

    def patch(self, url, params=None, json=None, headers=None, timeout=None):
        self.chamadas.append(("PATCH", self._tabela(url), params, json, headers))
        if self._tabela(url) == "assinaturas_api":
            linhas = [{"ativa": False}] * self.ativas
            self.ativas = 0
            return Resposta(200, linhas)
        return Resposta(204, None)

    def post(self, url, json=None, headers=None, timeout=None):
        self.chamadas.append(("POST", self._tabela(url), None, json, headers))
        if self.falhar_post:
            return Resposta(409, {"message": "conflito"})
        return Resposta(201, [dict(json, id="nova")])


@pytest.fixture
def supabase(monkeypatch):
    monkeypatch.setattr(config, "SUPABASE_URL", URL)
    monkeypatch.setattr(config, "SUPABASE_SERVICE_ROLE_KEY", "service-role-de-teste")

    def instalar(**kwargs):
        falso = SupabaseFalso(**kwargs)
        for metodo in ("get", "patch", "post"):
            monkeypatch.setattr(gerenciar_chaves.requests, metodo, getattr(falso, metodo))
        return falso

    return instalar


def _escritas(falso):
    return [(m, t) for m, t, *_ in falso.chamadas if m != "GET"]


def test_assinar_copia_os_termos_do_config_e_zera_tokens(supabase, capsys):
    falso = supabase()
    assert gerenciar_chaves.main(["assinar", "aida_ab12cd", "api_starter", "BR"]) == 0

    # Ordem importa: o índice único permite só uma assinatura ativa por chave.
    assert _escritas(falso) == [("PATCH", "assinaturas_api"), ("POST", "assinaturas_api"), ("PATCH", "api_keys")]
    _, _, params, corpo, cabecalhos = falso.chamadas[1]
    assert params == {"chave_id": f"eq.{CHAVE['id']}", "ativa": "is.true"}
    assert corpo["ativa"] is False and corpo["cancelada_em"]
    assert cabecalhos["Authorization"] == "Bearer service-role-de-teste"

    linha = falso.chamadas[2][3]
    assert linha["chave_id"] == CHAVE["id"]
    assert (linha["plano_id"], linha["mercado"], linha["moeda"]) == ("api_starter", "BR", "BRL")
    assert linha["creditos_incluidos"] == 2000
    assert linha["excedente"] == "charge" and linha["preco_excedente"] == "0.03"
    assert linha["ciclo_cobranca"] == "monthly" and linha["ativa"] is True and linha["ancora_ciclo"]

    _, _, params, corpo, _ = falso.chamadas[3]
    assert params == {"id": f"eq.{CHAVE['id']}"} and corpo == {"tokens_total": 0}

    saida = capsys.readouterr().out
    assert "api_starter" in saida and "1 assinatura(s) anterior(es) desativada(s)" in saida


def test_assinar_anual_em_dolar_e_plano_que_bloqueia(supabase):
    falso = supabase(assinaturas_ativas=0)
    assert gerenciar_chaves.main(["assinar", "aida_ab12cd", "api_free", "intl", "--anual"]) == 0
    linha = falso.chamadas[2][3]
    assert (linha["mercado"], linha["moeda"], linha["ciclo_cobranca"]) == ("INTL", "USD", "annual")
    assert linha["excedente"] == "block" and linha["preco_excedente"] is None
    assert linha["creditos_incluidos"] == 100


@pytest.mark.parametrize("plano,mercado", [
    ("enterprise", "BR"),     # créditos negociados: sem termos no config
    ("criador", "BR"),        # plano da plataforma, não da API
    ("api_inexistente", "INTL"),
])
def test_assinar_recusa_plano_invalido_sem_escrever(supabase, capsys, plano, mercado):
    falso = supabase()
    assert gerenciar_chaves.main(["assinar", "aida_ab12cd", plano, mercado]) == 1
    assert falso.chamadas == []
    assert "Erro:" in capsys.readouterr().err


@pytest.mark.parametrize("chaves,mensagem", [
    ((), "Nenhuma chave"),
    ((CHAVE, dict(CHAVE, id="outra")), "prefixo unico"),
    ((dict(CHAVE, revogada=True),), "revogada"),
])
def test_assinar_recusa_chave_ausente_ambigua_ou_revogada(supabase, capsys, chaves, mensagem):
    falso = supabase(chaves=chaves)
    assert gerenciar_chaves.main(["assinar", "aida_ab12cd", "api_pro", "BR"]) == 1
    assert _escritas(falso) == []
    assert mensagem in capsys.readouterr().err


def test_falha_ao_criar_avisa_para_rodar_de_novo(supabase, capsys):
    falso = supabase(falhar_post=True)
    assert gerenciar_chaves.main(["assinar", "aida_ab12cd", "api_pro", "BR"]) == 1
    assert ("PATCH", "api_keys") not in _escritas(falso), "tokens_total só zera com a assinatura criada"
    assert "rode o comando de novo" in capsys.readouterr().err


def test_cancelar_assinatura(supabase, capsys):
    falso = supabase()
    assert gerenciar_chaves.main(["cancelar-assinatura", "aida_ab12cd"]) == 0
    assert _escritas(falso) == [("PATCH", "assinaturas_api")]
    assert "cancelada" in capsys.readouterr().out

    assert gerenciar_chaves.main(["cancelar-assinatura", "aida_ab12cd"]) == 0
    assert "nao tinha assinatura ativa" in capsys.readouterr().out


def test_sem_service_role_explica_o_que_falta(monkeypatch, capsys):
    monkeypatch.setattr(config, "SUPABASE_URL", "")
    monkeypatch.setattr(config, "SUPABASE_SERVICE_ROLE_KEY", "")
    assert gerenciar_chaves.main(["cancelar-assinatura", "aida_ab12cd"]) == 2
    assert "SUPABASE_SERVICE_ROLE_KEY" in capsys.readouterr().err
