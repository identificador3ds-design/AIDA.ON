"""Cobrança no servidor: preço, créditos, anti-arbitragem e medição por ciclo.

A integração usa o test client do Flask com o Core dublado — nenhuma chamada
de rede. O que se verifica:

* checkout em BRL só com CPF/CNPJ válido e endereço de cobrança no Brasil;
* o valor cotado sai do config, nunca de um campo enviado pelo cliente;
* API Free bloqueia com 429 no limite; plano pago segue e registra excedente;
* análise que falha devolve o crédito;
* resposta servida do cache não consome crédito.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from aida_api import app as modulo_app  # noqa: E402
from aida_api import chaves_api, cobranca, config, core, limites, medicao  # noqa: E402

CHAVE = "aida_chave_cobranca"
TOKEN_USUARIO = "sessao-de-teste"
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 128
CPF_VALIDO = "529.982.247-25"
CNPJ_VALIDO = "11.222.333/0001-81"
CNPJ_ALFANUMERICO = "12.ABC.345/01DE-35"
ENDERECO_BR = {"country": "BR", "postal_code": "01310-100", "state": "SP", "city": "São Paulo",
               "line1": "Av. Paulista, 1000"}

RESPOSTA_CORE = {
    "id_analise": "abc123", "resultado": "REAL", "inconclusivo": False, "fora_de_dominio": False,
    "confianca": "alta", "probabilidade_ia": 0.1, "probabilidade_ia_exibicao": 0.1,
    "probabilidade_real_exibicao": 0.9, "limiar": 0.5, "limiar_exibicao": 0.5,
    "scores_modulos": {}, "qualidade": {}, "limitacoes": [], "evidencias": {},
    "ressalva": "Indicio tecnico, nao prova.", "versao_modelo": "AIDA-2.0",
}


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture
def api(monkeypatch):
    monkeypatch.setattr(config, "CHAVES_DEV", [CHAVE])
    # A cota de taxa (60/h por chave) é outro mecanismo; aqui só interessam os créditos.
    monkeypatch.setattr(config, "LIMITE_PADRAO", 10_000)
    monkeypatch.setattr(config, "SUPABASE_URL", "")
    monkeypatch.setattr(config, "SUPABASE_SERVICE_ROLE_KEY", "")
    monkeypatch.setenv("AIDA_API_DEV_USUARIOS", TOKEN_USUARIO)
    chaves_api.limpar_cache()
    modulo_app.analises.limpar()
    # monkeypatch devolve o original no fim, mesmo se o teste trocar o medidor.
    monkeypatch.setattr(modulo_app, "limitador", limites.LimitadorEmMemoria(limite_padrao=10_000, janela_s=60))
    monkeypatch.setattr(modulo_app, "medidor", medicao.MedidorEmMemoria())

    estado = {"falhar": False, "chamadas": 0}

    def core_falso(conteudo, nome, evidencias=True, timeout=None):
        estado["chamadas"] += 1
        if estado["falhar"]:
            raise core.CoreIndisponivel("fora do ar")
        return dict(RESPOSTA_CORE, id_analise=f"id{estado['chamadas']}"), 1.0

    monkeypatch.setattr(modulo_app.core, "analisar", core_falso)
    cliente = modulo_app.app.test_client()
    cliente.estado = estado
    return cliente


def assinar(plano_id, mercado="BR", ancora=None):
    assinatura = medicao.Assinatura.do_plano(plano_id, mercado, ancora=ancora)
    modulo_app.medidor.definir_assinatura(chaves_api.hash_chave(CHAVE), assinatura)
    return assinatura


def analisar(cliente, conteudo=PNG):
    # Bytes diferentes a cada chamada evitam o cache por conteúdo.
    return cliente.post(
        "/v1/analyze/image",
        headers={"Authorization": f"Bearer {CHAVE}"},
        data={"image": (__import__("io").BytesIO(conteudo), "foto.png")},
        content_type="multipart/form-data",
    )


def checkout(cliente, corpo, token=TOKEN_USUARIO):
    cabecalhos = {"Authorization": f"Bearer {token}"} if token else {}
    return cliente.post("/v1/billing/checkout", json=corpo, headers=cabecalhos)


# --------------------------------------------------------------------------- #
# Regras puras
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("segundos,creditos", [(0, 0), (None, 0), (1, 10), (60, 10), (61, 20), (150, 30)])
def test_video_em_creditos(segundos, creditos):
    assert cobranca.creditos_video(segundos) == creditos


def test_imagem_vale_um_credito():
    assert cobranca.creditos_imagem() == 1


def test_preco_anual_e_decimal_exato():
    cfg = cobranca.carregar_config()
    criador = cobranca.encontrar_plano(cfg, "criador", "BR")
    assert cobranca.preco_do_ciclo(criador, "BRL", "monthly") == Decimal("24.90")
    assert cobranca.preco_do_ciclo(criador, "BRL", "annual") == Decimal("249.00")
    scale = cobranca.encontrar_plano(cfg, "api_scale", "INTL")
    assert cobranca.preco_do_ciclo(scale, "USD", "annual") == Decimal("5990.00")


@pytest.mark.skipif(shutil.which("node") is None, reason="node ausente")
def test_servidor_e_site_calculam_o_mesmo_anual():
    """Os dois leem o mesmo JSON; se divergirem, a tela promete um preço e a fatura cobra outro."""
    modulo = RAIZ / "scripts" / "aida-precos-core.js"
    caminho = RAIZ / "config" / "pricing.json"
    codigo = (
        f"const P=require({json.dumps(str(modulo))});"
        f"const C=JSON.parse(require('fs').readFileSync({json.dumps(str(caminho))},'utf8'));"
        "const s={};for(const m in C.markets){const cur=C.markets[m].currency;"
        "for(const g of ['platform','api'])for(const p of C.markets[m][g])s[m+'/'+p.id]=P.precoAnual(p,cur,C);}"
        "process.stdout.write(JSON.stringify(s))"
    )
    site = json.loads(subprocess.run(["node", "-e", codigo], capture_output=True, check=True).stdout)
    cfg = cobranca.carregar_config()
    for mercado in cfg["markets"]:
        moeda = cobranca.moeda_do_mercado(cfg, mercado)
        for plano in cobranca.planos(cfg, mercado):
            servidor = cobranca.preco_do_ciclo(plano, moeda, "annual", cfg)
            no_site = site[f"{mercado}/{plano['id']}"]
            assert (servidor is None and no_site is None) or Decimal(str(no_site)) == servidor, plano["id"]


@pytest.mark.parametrize("cpf", ["529.982.247-25", "52998224725", "111.444.777-35"])
def test_cpf_valido(cpf):
    assert cobranca.cpf_valido(cpf)


@pytest.mark.parametrize("cpf", ["529.982.247-24", "111.111.111-11", "123", "", None])
def test_cpf_invalido(cpf):
    assert not cobranca.cpf_valido(cpf)


@pytest.mark.parametrize("cnpj", [CNPJ_VALIDO, "11222333000181", CNPJ_ALFANUMERICO, "12abc34501de35"])
def test_cnpj_valido_inclusive_alfanumerico(cnpj):
    assert cobranca.cnpj_valido(cnpj)


@pytest.mark.parametrize("cnpj", ["11.222.333/0001-80", "00.000.000/0000-00", "12.ABC.345/01DE-36", "ABC"])
def test_cnpj_invalido(cnpj):
    assert not cobranca.cnpj_valido(cnpj)


# --------------------------------------------------------------------------- #
# Checkout: anti-arbitragem (integração)
# --------------------------------------------------------------------------- #
def test_checkout_exige_sessao(api):
    r = checkout(api, {"plan_id": "criador", "market": "BR"}, token=None)
    assert r.status_code == 401 and r.get_json()["error"]["code"] == "missing_credentials"
    r = checkout(api, {"plan_id": "criador", "market": "BR"}, token="sessao-falsa")
    assert r.status_code == 401


def test_checkout_brl_sem_documento_e_recusado(api):
    r = checkout(api, {"plan_id": "criador", "market": "BR", "billing_address": ENDERECO_BR})
    assert r.status_code == 422 and r.get_json()["error"]["code"] == "tax_id_required"


def test_checkout_brl_com_documento_invalido_e_recusado(api):
    r = checkout(api, {"plan_id": "criador", "market": "BR", "tax_id": "123.456.789-00",
                       "billing_address": ENDERECO_BR})
    assert r.status_code == 422 and r.get_json()["error"]["code"] == "invalid_tax_id"


@pytest.mark.parametrize("pais", ["US", "PT", "", None])
def test_checkout_brl_com_endereco_fora_do_brasil_e_recusado(api, pais):
    endereco = {**ENDERECO_BR, "country": pais}
    r = checkout(api, {"plan_id": "api_pro", "market": "BR", "tax_id": CPF_VALIDO, "billing_address": endereco})
    assert r.status_code == 422 and r.get_json()["error"]["code"] == "billing_country_mismatch"


def test_checkout_brl_sem_endereco_e_recusado(api):
    r = checkout(api, {"plan_id": "api_pro", "market": "BR", "tax_id": CPF_VALIDO})
    assert r.status_code == 422 and r.get_json()["error"]["code"] == "billing_address_required"


@pytest.mark.parametrize("campo,valor,codigo", [("postal_code", "123", "invalid_postal_code"),
                                                 ("state", "XX", "invalid_state")])
def test_checkout_brl_com_endereco_malformado(api, campo, valor, codigo):
    endereco = {**ENDERECO_BR, campo: valor}
    r = checkout(api, {"plan_id": "api_pro", "market": "BR", "tax_id": CPF_VALIDO, "billing_address": endereco})
    assert r.get_json()["error"]["code"] == codigo


@pytest.mark.parametrize("documento,tipo", [(CPF_VALIDO, "cpf"), (CNPJ_VALIDO, "cnpj"), (CNPJ_ALFANUMERICO, "cnpj")])
def test_checkout_brl_valido_chega_ao_gateway_com_preco_do_servidor(api, documento, tipo):
    r = checkout(api, {"plan_id": "criador", "market": "BR", "billing_cycle": "annual",
                       "tax_id": documento, "billing_address": ENDERECO_BR})
    corpo = r.get_json()
    assert r.status_code == 501 and corpo["error"]["code"] == "gateway_not_configured"
    cotacao = corpo["error"]["details"]["quote"]
    assert cotacao == {**cotacao, "plan_id": "criador", "currency": "BRL", "amount": "249.00",
                       "billing_cycle": "annual", "tax_id_type": tipo}


def test_valor_enviado_pelo_cliente_e_ignorado(api):
    r = checkout(api, {"plan_id": "api_scale", "market": "BR", "tax_id": CNPJ_VALIDO,
                       "billing_address": ENDERECO_BR, "amount": "0.01", "price": 0.01,
                       "currency": "USD", "price_monthly": {"BRL": 1}})
    cotacao = r.get_json()["error"]["details"]["quote"]
    assert cotacao["amount"] == "1490.00" and cotacao["currency"] == "BRL"


def test_moeda_vem_do_mercado_nao_do_cliente(api):
    """Pedir 'BRL' no mercado internacional não barateia nada."""
    r = checkout(api, {"plan_id": "api_starter", "market": "INTL", "currency": "BRL"})
    cotacao = r.get_json()["error"]["details"]["quote"]
    assert cotacao["currency"] == "USD" and cotacao["amount"] == "19.00"


def test_checkout_em_dolar_nao_exige_documento_brasileiro(api):
    r = checkout(api, {"plan_id": "team", "market": "INTL", "billing_address": {"country": "US"}})
    assert r.status_code == 501
    assert r.get_json()["error"]["details"]["quote"]["amount"] == "39.00"


@pytest.mark.parametrize("plano,mercado,codigo,status", [
    ("api_free", "BR", "plan_not_purchasable", 422),
    ("cidadao", "BR", "plan_not_purchasable", 422),
    ("enterprise", "BR", "plan_requires_contact", 422),
    ("checagem_ong", "BR", "plan_requires_contact", 422),
    ("criador", "INTL", "plan_not_found", 404),
    ("pro", "BR", "plan_not_found", 404),
])
def test_planos_fora_do_checkout(api, plano, mercado, codigo, status):
    r = checkout(api, {"plan_id": plano, "market": mercado, "tax_id": CPF_VALIDO, "billing_address": ENDERECO_BR})
    assert r.status_code == status and r.get_json()["error"]["code"] == codigo


def test_checkout_com_corpo_invalido(api):
    assert checkout(api, {"plan_id": "criador", "market": "XX"}).status_code == 400
    assert checkout(api, {"plan_id": "criador", "market": "BR", "billing_cycle": "weekly"}).status_code == 400
    r = api.post("/v1/billing/checkout", data="nao-json", headers={"Authorization": f"Bearer {TOKEN_USUARIO}"})
    assert r.status_code == 400


# --------------------------------------------------------------------------- #
# Medição de créditos (integração)
# --------------------------------------------------------------------------- #
def test_chave_sem_assinatura_nao_e_medida(api):
    r = analisar(api)
    assert r.status_code == 200 and "X-AIDA-Credits-Used" not in r.headers
    assert api.get("/v1/usage", headers={"Authorization": f"Bearer {CHAVE}"}).get_json()["metered"] is False


def test_api_free_bloqueia_com_429_no_limite(api):
    assinar("api_free")
    for i in range(100):
        r = analisar(api, PNG + str(i).encode())
        assert r.status_code == 200, i
    assert r.headers["X-AIDA-Credits-Remaining"] == "0"

    r = analisar(api, PNG + b"extra")
    corpo = r.get_json()
    assert r.status_code == 429
    assert corpo["error"]["code"] == "credits_exhausted"
    assert "100 creditos" in corpo["error"]["message"] and "renovam em" in corpo["error"]["message"]
    assert corpo["error"]["details"]["credits_used"] == 100
    assert int(r.headers["Retry-After"]) > 0
    assert api.estado["chamadas"] == 100, "a chamada recusada não pode chegar ao Core"


def test_plano_pago_segue_e_registra_excedente(api):
    assinatura = assinar("api_starter")
    medidor = modulo_app.medidor
    chave_id = chaves_api.hash_chave(CHAVE)
    # Leva o ciclo até o limite sem 2000 chamadas HTTP.
    for _ in range(assinatura.creditos_incluidos):
        medidor.debitar(chave_id, 1, "image")

    r = analisar(api)
    assert r.status_code == 200
    assert r.headers["X-AIDA-Overage-Credits"] == "1"

    uso = api.get("/v1/usage", headers={"Authorization": f"Bearer {CHAVE}"}).get_json()
    assert uso["metered"] is True and uso["plan_id"] == "api_starter"
    assert uso["credits_used"] == 2001 and uso["overage_credits"] == 1
    assert uso["overage_amount"] == "0.03" and uso["currency"] == "BRL"
    assert uso["rollover"] is False


def test_falha_do_core_devolve_o_credito(api):
    assinar("api_free")
    api.estado["falhar"] = True
    assert analisar(api).status_code == 503
    uso = api.get("/v1/usage", headers={"Authorization": f"Bearer {CHAVE}"}).get_json()
    assert uso["credits_used"] == 0
    tipos = [l[2] for l in modulo_app.medidor.lancamentos()]
    assert tipos == ["image", "estorno"]


def test_resposta_do_cache_nao_consome_credito(api):
    assinar("api_free")
    primeira = analisar(api)
    assert primeira.status_code == 200 and primeira.headers["X-AIDA-Cache"] == "miss"
    assert primeira.headers["X-AIDA-Credits-Used"] == "1"

    segunda = analisar(api)  # mesmo arquivo, dentro do TTL
    assert segunda.status_code == 200 and segunda.headers["X-AIDA-Cache"] == "hit"
    assert segunda.headers["X-AIDA-Credits-Used"] == "1", "cache hit informa o saldo sem debitar"

    uso = api.get("/v1/usage", headers={"Authorization": f"Bearer {CHAVE}"}).get_json()
    assert uso["credits_used"] == 1
    assert [l[2] for l in modulo_app.medidor.lancamentos()] == ["image"]
    assert api.estado["chamadas"] == 1


def test_cache_hit_e_servido_mesmo_com_creditos_esgotados(api):
    assinatura = assinar("api_free")
    assert analisar(api).status_code == 200  # guarda no cache (1 crédito)
    chave_id = chaves_api.hash_chave(CHAVE)
    for _ in range(assinatura.creditos_incluidos - 1):
        modulo_app.medidor.debitar(chave_id, 1, "image")

    assert analisar(api).status_code == 200  # repetido: sem crédito em jogo
    assert analisar(api, PNG + b"novo").status_code == 429  # arquivo novo: bloqueia


def test_cache_hit_nao_depende_da_medicao(api):
    assinar("api_free")
    assert analisar(api).status_code == 200

    class Quebrado(medicao.MedidorEmMemoria):
        def debitar(self, *a, **k):
            raise medicao.MedicaoIndisponivel("banco fora")

        def uso(self, *a, **k):
            raise medicao.MedicaoIndisponivel("banco fora")

    modulo_app.medidor = Quebrado()
    r = analisar(api)
    assert r.status_code == 200 and r.headers["X-AIDA-Cache"] == "hit"
    assert "X-AIDA-Credits-Used" not in r.headers


def test_medicao_fora_do_ar_responde_503_sem_chamar_o_core(api):
    class Quebrado(medicao.MedidorEmMemoria):
        def debitar(self, *a, **k):
            raise medicao.MedicaoIndisponivel("banco fora")

    modulo_app.medidor = Quebrado()
    r = analisar(api)
    assert r.status_code == 503 and r.get_json()["error"]["code"] == "billing_unavailable"
    assert api.estado["chamadas"] == 0


# --------------------------------------------------------------------------- #
# Ciclo e saldo (unidade)
# --------------------------------------------------------------------------- #
def utc(*a):
    return datetime(*a, tzinfo=timezone.utc)


@pytest.mark.parametrize("ancora,agora,inicio,fim", [
    (utc(2026, 1, 20), utc(2026, 1, 25), utc(2026, 1, 20), utc(2026, 2, 20)),
    (utc(2026, 1, 20), utc(2026, 3, 10), utc(2026, 2, 20), utc(2026, 3, 20)),
    (utc(2026, 1, 20), utc(2026, 3, 20), utc(2026, 3, 20), utc(2026, 4, 20)),
    (utc(2026, 1, 31), utc(2026, 2, 28, 12), utc(2026, 2, 28), utc(2026, 3, 31)),
    (utc(2026, 1, 31), utc(2026, 3, 1), utc(2026, 2, 28), utc(2026, 3, 31)),
    (utc(2025, 11, 15), utc(2026, 1, 1), utc(2025, 12, 15), utc(2026, 1, 15)),
])
def test_ciclo_mensal_ancorado(ancora, agora, inicio, fim):
    assert medicao.ciclo_atual(ancora, agora) == (inicio, fim)


def test_creditos_nao_acumulam_para_o_ciclo_seguinte():
    medidor = medicao.MedidorEmMemoria()
    assinatura = medicao.Assinatura.do_plano("api_free", "BR", ancora=utc(2026, 1, 1))
    medidor.definir_assinatura("k", assinatura)

    d = medidor.debitar("k", 30, "image", agora=utc(2026, 1, 10))
    assert d.restantes == 70
    # Ciclo seguinte: volta aos 100 incluídos, não 170.
    d = medidor.uso("k", agora=utc(2026, 2, 2))
    assert d.usados == 0 and d.restantes == 100


def test_video_debita_pela_regra_de_minuto_iniciado():
    medidor = medicao.MedidorEmMemoria()
    medidor.definir_assinatura("k", medicao.Assinatura.do_plano("api_free", "BR", ancora=utc(2026, 1, 1)))
    agora = utc(2026, 1, 5)
    assert medidor.debitar("k", cobranca.creditos_video(95), "video", agora=agora).usados == 20
    # 81 s = 2 minutos iniciados = 20 créditos (total 40). Mais 6 min 40 s = 70
    # créditos levaria a 110 > 100: o plano grátis recusa e nada é debitado.
    assert medidor.debitar("k", cobranca.creditos_video(81), "video", agora=agora).usados == 40
    bloqueado = medidor.debitar("k", cobranca.creditos_video(400), "video", agora=agora)
    assert not bloqueado.permitido and bloqueado.usados == 40


def test_assinatura_copia_os_termos_do_config():
    a = medicao.Assinatura.do_plano("api_scale", "INTL")
    assert (a.creditos_incluidos, a.excedente, a.preco_excedente, a.moeda) == (200000, "charge", Decimal("0.0035"), "USD")
    with pytest.raises(ValueError):
        medicao.Assinatura.do_plano("enterprise", "BR")


def test_contrato_documenta_os_codigos_novos():
    from aida_api.contrato import CODIGOS_DE_ERRO, CONTRATO

    for codigo in ("credits_exhausted", "billing_unavailable", "tax_id_required", "invalid_tax_id",
                   "billing_country_mismatch", "gateway_not_configured"):
        assert codigo in CODIGOS_DE_ERRO
    assert "GET /v1/usage" in CONTRATO["endpoints"] and "POST /v1/billing/checkout" in CONTRATO["endpoints"]


# --------------------------------------------------------------------------- #
# Migração: anti-spam do formulário comercial
# --------------------------------------------------------------------------- #
def test_migracao_limita_envios_do_formulario():
    import re

    sql = (RAIZ / "docs" / "migracao-cobranca.sql").read_text(encoding="utf-8").lower()
    sql = re.sub(r"\s+", " ", sql)
    assert "before insert on public.contatos_comerciais" in sql
    # idempotente: recria a função e o trigger sem erro na segunda execução
    assert "create or replace function public.contatos_comerciais_limita_envios()" in sql
    assert "drop trigger if exists contatos_comerciais_limita_envios on public.contatos_comerciais" in sql
    assert "create index if not exists contatos_comerciais_email_hora_idx" in sql
    # 3 por e-mail (sem diferenciar maiúsculas) e 20 no total, por hora
    assert "lower(email) = lower(new.email)" in sql
    assert "v_por_email >= 3" in sql and "v_total >= 20" in sql
    assert sql.count("interval '1 hour'") >= 2
    assert sql.count("errcode = 'p0001'") >= 2
    # anon não lê a tabela: a contagem precisa rodar como dono da função
    trecho = sql.split("function public.contatos_comerciais_limita_envios()", 1)[1]
    assert "security definer" in trecho.split("$$", 1)[0]

