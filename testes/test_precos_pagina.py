"""Página de preços: componente (jsdom), traduções, HTML gerado e publicação.

O teste de componente roda testes/js/componente_precos.cjs no Node com jsdom
(devDependency do package.json; `npm ci` na raiz). Ele aciona a página como um
usuário — troca de moeda, mensal/anual, idioma, abas, calculadora e
formulário — e devolve o que a tela mostrou em cada passo.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
PAGINA = RAIZ / "pages" / "index-precos.html"
CONFIG = json.loads((RAIZ / "config" / "pricing.json").read_text(encoding="utf-8"))
PT = json.loads((RAIZ / "i18n" / "precos.pt-BR.json").read_text(encoding="utf-8"))
EN = json.loads((RAIZ / "i18n" / "precos.en-US.json").read_text(encoding="utf-8"))

sys.path.insert(0, str(RAIZ / "docs"))
import gerar_pagina_precos  # noqa: E402

TEM_JSDOM = shutil.which("node") is not None and (RAIZ / "node_modules" / "jsdom").is_dir()


# --------------------------------------------------------------------------- #
# Componente
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def tela():
    if not TEM_JSDOM:
        pytest.skip("node ou jsdom ausente (rode `npm ci` na raiz)")
    saida = subprocess.run(
        ["node", str(RAIZ / "testes" / "js" / "componente_precos.cjs")],
        capture_output=True, check=True, cwd=RAIZ,
    )
    return json.loads(saida.stdout.decode("utf-8"))


def test_pagina_carrega_sem_erro(tela):
    assert tela["inicial"]["erro"] is None
    assert tela["inicial"]["statusOculto"] is True
    assert tela["inicial"]["lang"] == "pt-BR"


def test_precos_iniciais_em_reais_vem_do_config(tela):
    assert tela["inicial"]["criador"] == "R$ 24,90/mês"
    assert tela["inicial"]["cidadao"] == "Grátis"
    assert tela["inicial"]["apiStarter"] == "R$ 49,90/mês"
    assert "Excedente: R$ 0,030 por crédito" in tela["inicial"]["excedenteStarter"]
    assert tela["inicial"]["economia"] == "Economize 17%"


def test_troca_de_moeda_mostra_os_planos_em_dolar(tela):
    usd = tela["usdMensal"]
    assert usd["pro"] == "$9.00/mês"
    assert usd["team"] == "$39.00/mês"
    assert usd["apiScale"] == "$599.00/mês"
    assert "$0.0035 por crédito" in usd["excedenteScale"]
    assert usd["planosPlataforma"] == ["free", "pro", "team"]
    # Decisões 2026-11-25: créditos, usuários e "sem excedente" sem "a definir".
    assert "1.500 créditos por mês" in usd["fatosPro"] and "1 usuário" in usd["fatosPro"]
    assert "6.000 créditos por mês" in usd["fatosTeam"] and "5 usuários" in usd["fatosTeam"]
    for fatos in (usd["fatosPro"], usd["fatosTeam"]):
        assert "Sem excedente: bloqueia no limite" in fatos and "a definir" not in fatos
    assert "A partir de 500.000 créditos por mês" in usd["fatosEnterprise"]
    assert usd["preferencia"] == "INTL"


def test_troca_para_anual_cobra_dez_meses(tela):
    assert tela["usdAnual"]["pro"] == "$90.00/ano"
    assert "$7.50/mês" in tela["usdAnual"]["notaPro"] and "$18.00" in tela["usdAnual"]["notaPro"]
    assert tela["brlAnual"]["criador"] == "R$ 249,00/ano"
    assert "R$ 20,75/mês" in tela["brlAnual"]["notaCriador"]
    assert tela["brlAnual"]["apiBusiness"] == "R$ 4.990,00/ano"


def test_volta_para_mensal(tela):
    assert tela["brlMensal"]["criador"] == "R$ 24,90/mês"


def test_abas_por_clique_e_teclado(tela):
    assert tela["abaApi"] == {"selecionada": "true", "painelApiOculto": False, "painelPlataformaOculto": True}
    assert tela["teclado"] == {"selecionadaPlataforma": "true", "foco": "aba-platform", "tabindexApi": -1}


def test_calculadora_na_tela(tela):
    assert tela["calc5000"]["recomendado"] == "api_starter"
    assert "R$ 139,90" in tela["calc5000"]["texto"]
    assert tela["calcInvalida"]["invalido"] == "true"
    assert tela["calc50"]["recomendado"] == "api_free"


def test_troca_de_idioma(tela):
    en = tela["ingles"]
    assert en["lang"] == "en-US"
    assert en["titulo"] == EN["hero.title"]
    assert en["nomeCriador"] == EN["plan.criador.name"]
    assert en["criador"] == "R$ 24,90/mo", "moeda segue o locale do mercado, não o do idioma"
    assert en["tituloDocumento"] == EN["meta.title"]


def test_formulario_valida_antes_de_enviar(tela):
    assert tela["dialogo"]["aberto"] and tela["dialogo"]["tipo"] == "enterprise"
    assert tela["dialogo"]["foco"] == "contatoNome"
    vazio = tela["formVazio"]
    assert vazio["resumoVisivel"] and vazio["enviados"] == 0
    assert set(vazio["invalidos"]) == {
        "contatoNome", "contatoEmpresa", "contatoEmail", "contatoVolume", "contatoConsentimento",
    }


def test_formulario_envia_so_os_campos_do_contato(tela):
    valido = tela["formValido"]
    assert valido["invalidos"] == []
    assert valido["estado"] == PT["contact.success"]
    (envio,) = valido["enviados"]
    assert envio["url"].endswith("/rest/v1/contatos_comerciais") and envio["metodo"] == "POST"
    assert envio["cabecalhos"]["Prefer"] == "return=minimal"
    assert set(envio["corpo"]) == {
        "tipo", "plano_id", "mercado", "idioma", "nome", "empresa", "email",
        "volume_estimado", "mensagem", "consentimento",
    }
    assert envio["corpo"]["volume_estimado"] == 600000


def test_formulario_avisa_quando_o_limite_anti_spam_recusa(tela):
    assert tela["formLimite"]["enviados"] == 2
    assert tela["formLimite"]["estado"] == PT["contact.error_rate_limit"]


# --------------------------------------------------------------------------- #
# Traduções
# --------------------------------------------------------------------------- #
def test_idiomas_tem_as_mesmas_chaves():
    assert set(PT) == set(EN), f"só pt: {set(PT) - set(EN)}; só en: {set(EN) - set(PT)}"


def test_placeholders_iguais_nos_dois_idiomas():
    for chave in PT:
        assert set(re.findall(r"\{(\w+)\}", PT[chave])) == set(re.findall(r"\{(\w+)\}", EN[chave])), chave


def test_toda_chave_do_html_existe():
    html = PAGINA.read_text(encoding="utf-8")
    chaves = set(re.findall(r'data-i18n="([^"]+)"', html))
    for pares in re.findall(r'data-i18n-attr="([^"]+)"', html):
        chaves |= {p.split(":")[1] for p in pares.split(";")}
    assert chaves - set(PT) == set()


def test_toda_chave_do_config_e_do_script_existe():
    chaves = set()
    for mercado in CONFIG["markets"].values():
        for segmento in ("platform", "api"):
            for plano in mercado[segmento]:
                chaves |= {plano["name_key"], plano["audience_key"], plano["cta"]["label_key"]}
                chaves |= {f"feature.{f}" for f in plano["features"]}
    for segmento, linhas in CONFIG["comparison_rows"].items():
        chaves.add(f"segment.{segmento}")
        for linha in linhas:
            chaves.add(f"row.{linha}" if f"row.{linha}" in PT else f"feature.{linha}")

    script = (RAIZ / "scripts" / "script-precos.js").read_text(encoding="utf-8")
    chaves |= set(re.findall(r'\bt\("([a-z_]+\.[a-zA-Z_.]+)"', script))
    chaves |= {f"contact.title.{t}" for t in ("enterprise", "checagem_ong", "subscribe", "api_free")}

    faltando = sorted(c for c in chaves if c not in PT)
    assert not faltando, f"chaves sem texto: {faltando}"


def test_script_da_pagina_nao_tem_preco_escrito():
    """Preço só no config: um número com cara de dinheiro no script é suspeito."""
    script = (RAIZ / "scripts" / "script-precos.js").read_text(encoding="utf-8")
    assert not re.search(r"(R\$|\$)\s?\d|\b\d+[.,]\d{2}\b", script)


# --------------------------------------------------------------------------- #
# HTML gerado, SEO e publicação
# --------------------------------------------------------------------------- #
def test_pagina_precos_em_sincronia():
    """Editou config ou i18n? Rode: python docs/gerar_pagina_precos.py"""
    atual = PAGINA.read_text(encoding="utf-8")
    assert gerar_pagina_precos.gerar(atual) == atual


def test_html_ja_sai_com_texto_em_portugues():
    html = PAGINA.read_text(encoding="utf-8")
    vazios = re.findall(r'data-i18n="([^"]+)"[^>]*></', html)
    assert not vazios, f"elementos sem texto pré-preenchido: {vazios}"
    assert f"<title>{PT['meta.title']}</title>" in html


def test_dados_estruturados_cobrem_os_planos_com_preco():
    html = PAGINA.read_text(encoding="utf-8")
    bloco = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S).group(1)
    dados = json.loads(bloco)
    assert dados["@context"] == "https://schema.org"
    ofertas = dados["offers"]
    assert all(o["@type"] == "Offer" for o in ofertas)
    pares = {(o["name"], o["priceCurrency"], o["price"]) for o in ofertas}
    assert ("Criador", "BRL", "24.90") in pares
    assert ("API Scale", "USD", "599.00") in pares
    assert ("API Free", "BRL", "0.00") in pares
    # Sob consulta / validação não têm preço publicável.
    assert not any(o["name"] in {"Enterprise", "Checagem/ONG"} for o in ofertas)


def test_meta_tags_de_compartilhamento():
    html = PAGINA.read_text(encoding="utf-8")
    for trecho in ('property="og:title"', 'property="og:description"', 'property="og:url"',
                   'name="description"', 'rel="canonical" href="https://aida-on.com.br/precos"'):
        assert trecho in html


def test_rotas_da_pagina_de_precos():
    vercel = json.loads((RAIZ / "vercel.json").read_text(encoding="utf-8"))
    destinos = {r["source"]: r["destination"] for r in vercel["rewrites"]}
    assert destinos["/precos"] == "/pages/index-precos"
    assert destinos["/pricing"] == "/pages/index-precos"


def test_vercel_publica_config_e_traducoes_mas_nao_o_package_json():
    linhas = (RAIZ / ".vercelignore").read_text(encoding="utf-8").splitlines()
    assert "!/config" in linhas and "!/i18n" in linhas
    assert "!/package.json" not in linhas and "!/node_modules" not in linhas


def test_service_worker_busca_json_na_rede():
    """Cache-first num JSON de preço mostraria valor antigo depois de um reajuste."""
    sw = (RAIZ / "service-worker.js").read_text(encoding="utf-8")
    assert 'requestUrl.pathname.endsWith(".json")' in sw


def test_toggles_sao_acessiveis():
    html = PAGINA.read_text(encoding="utf-8")
    for grupo in ("mercado", "ciclo", "idioma"):
        assert html.count(f'name="{grupo}"') == 2
    assert html.count("<legend") == 3
    assert 'role="tablist"' in html and html.count('role="tab"') == 2
    assert 'aria-describedby="precosEconomia"' in html
