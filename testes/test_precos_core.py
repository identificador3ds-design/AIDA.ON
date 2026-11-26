"""Regras de preço do site (scripts/aida-precos-core.js), exercitadas pelo Node.

Preço anual, conversão de vídeo em créditos, calculadora (plano mais barato,
com excedente) e formatação de moeda. Os valores esperados saem do próprio
config/pricing.json sempre que possível, para o teste acompanhar um reajuste;
os números escritos aqui são os da tabela aprovada, de propósito: se alguém
mudar o preço sem querer, o teste avisa.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from decimal import Decimal
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
MODULO = RAIZ / "scripts" / "aida-precos-core.js"
CAMINHO_CONFIG = RAIZ / "config" / "pricing.json"
CONFIG = json.loads(CAMINHO_CONFIG.read_text(encoding="utf-8"))

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node ausente")


def js(expressao):
    """Avalia `expressao` com P = módulo e C = config; devolve o JSON."""
    codigo = (
        f"const P=require({json.dumps(str(MODULO))});"
        f"const C=JSON.parse(require('fs').readFileSync({json.dumps(str(CAMINHO_CONFIG))},'utf8'));"
        f"process.stdout.write(JSON.stringify(({expressao})))"
    )
    saida = subprocess.run(["node", "-e", codigo], capture_output=True, check=True)
    return json.loads(saida.stdout.decode("utf-8"))


def plano(mercado, plano_id):
    return next(
        p for seg in ("platform", "api") for p in CONFIG["markets"][mercado][seg] if p["id"] == plano_id
    )


def recomendar(mercado, segmento, imagens, minutos=0, ciclo="monthly"):
    return js(
        f"(()=>{{const r=P.recomendarPlano(P.planosDe(C,{json.dumps(mercado)},{json.dumps(segmento)}),"
        f"P.moedaDe(C,{json.dumps(mercado)}),{{imagens:{imagens},minutosVideo:{minutos}}},{json.dumps(ciclo)},C);"
        "return {creditos:r.creditos, id:r.recomendado&&r.recomendado.id, total:r.custo&&P.arredondar(r.custo.total),"
        "extras:r.custo&&r.custo.creditosExtras, enterprise:r.sugerirEnterprise, indefinidos:r.indefinidos}})()"
    )


# --------------------------------------------------------------------------- #
# Preço anual
# --------------------------------------------------------------------------- #
def test_anual_e_dez_mensalidades_para_todo_plano_pago():
    todos = js(
        "Object.keys(C.markets).flatMap(m=>['platform','api'].flatMap(s=>C.markets[m][s].map(p=>"
        "({id:m+'/'+p.id, mensal:P.precoMensal(p,C.markets[m].currency), anual:P.precoAnual(p,C.markets[m].currency,C)}))))"
    )
    assert todos
    for item in todos:
        if item["mensal"] is None:
            assert item["anual"] is None, item
        else:
            esperado = (Decimal(str(item["mensal"])) * CONFIG["annual_months_charged"]).quantize(Decimal("0.01"))
            assert Decimal(str(item["anual"])) == esperado, item


@pytest.mark.parametrize(
    "mercado,plano_id,anual",
    [("BR", "criador", 249.0), ("BR", "api_scale", 14900.0), ("INTL", "pro", 90.0), ("INTL", "api_scale", 5990.0)],
)
def test_anual_valores_da_tabela(mercado, plano_id, anual):
    moeda = CONFIG["markets"][mercado]["currency"]
    assert js(f"P.precoAnual({json.dumps(plano(mercado, plano_id))},'{moeda}',C)") == anual


def test_economia_anual_e_17_por_cento():
    assert js("P.percentualEconomia(C)") == 17


def test_plano_sem_preco_nao_tem_anual():
    assert js(f"P.precoAnual({json.dumps(plano('BR', 'enterprise'))},'BRL',C)") is None


# --------------------------------------------------------------------------- #
# Vídeo em créditos
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "segundos,creditos",
    [(0, 0), (-5, 0), (1, 10), (59.9, 10), (60, 10), (60.1, 20), (61, 20), (150, 30), (3600, 600)],
)
def test_video_por_minuto_iniciado(segundos, creditos):
    assert js(f"P.creditosVideo({segundos},C)") == creditos


def test_video_invalido_nao_consome():
    assert js("[P.creditosVideo('abc',C), P.creditosVideo(null,C), P.creditosVideo(Infinity,C)]") == [0, 0, 0]


def test_estimativa_soma_imagens_e_minutos():
    assert js("P.creditosEstimados({imagens:120, minutosVideo:3},C)") == 150


def test_estimativa_recusa_valor_negativo_ou_fracionado():
    assert js("(()=>{try{P.creditosEstimados({imagens:-1},C);return 'ok'}catch(e){return e.name}})()") == "RangeError"
    assert js("(()=>{try{P.creditosEstimados({imagens:1.5},C);return 'ok'}catch(e){return e.name}})()") == "RangeError"


# --------------------------------------------------------------------------- #
# Calculadora: plano mais barato, com excedente
# --------------------------------------------------------------------------- #
def test_volume_pequeno_cabe_no_gratis():
    r = recomendar("BR", "api", 50)
    assert r["id"] == "api_free" and r["total"] == 0


def test_limite_exato_do_gratis_e_o_credito_seguinte():
    assert recomendar("BR", "api", 0, minutos=10)["id"] == "api_free"  # 100 créditos
    r = recomendar("BR", "api", 0, minutos=11)  # 110: Free bloqueia, não cobra excedente
    assert r["id"] == "api_starter" and r["creditos"] == 110


def test_excedente_do_starter_ainda_compensa():
    # 5000: Starter 49,90 + 3000 x 0,030 = 139,90 < Pro 149,90
    r = recomendar("BR", "api", 5000)
    assert r["id"] == "api_starter" and r["total"] == 139.9 and r["extras"] == 3000


def test_excedente_passa_do_plano_seguinte():
    # 6000: Starter 49,90 + 4000 x 0,030 = 169,90 > Pro 149,90
    r = recomendar("BR", "api", 6000)
    assert r["id"] == "api_pro" and r["total"] == 149.9


def test_calculadora_em_dolar_com_ciclo_anual():
    # 21000 créditos: Pro 59x10/12 = 49,1667 + 9000 x 0,006 = 54 -> 103,17
    r = recomendar("INTL", "api", 20000, minutos=100, ciclo="annual")
    assert r["creditos"] == 21000 and r["id"] == "api_pro" and r["total"] == 103.17


def test_volume_enterprise_sugere_contato():
    r = recomendar("BR", "api", 600000)
    assert r["enterprise"] is True
    assert r["id"] == "api_scale"  # ainda mostra o mais barato publicado


def test_plataforma_usa_limite_diario_e_bloqueio():
    assert recomendar("BR", "platform", 200)["id"] == "cidadao"   # <= 10 x 30
    assert recomendar("BR", "platform", 400)["id"] == "criador"
    assert recomendar("BR", "platform", 2000)["id"] == "profissional"
    r = recomendar("BR", "platform", 20000)  # Redação inclui 15.000 e bloqueia
    assert r["id"] is None and r["enterprise"] is False


def test_plataforma_em_dolar_pro_e_team_definidos():
    # Decisão 2026-11-25: Pro 1.500 créditos/1 usuário; Team 6.000/5 usuários.
    assert recomendar("INTL", "platform", 200)["id"] == "free"
    assert recomendar("INTL", "platform", 1000)["id"] == "pro"
    assert recomendar("INTL", "platform", 5000)["id"] == "team"
    r = recomendar("INTL", "platform", 7000)  # Team bloqueia no limite, sem excedente
    assert r["id"] is None and r["indefinidos"] == []
    assert plano("INTL", "pro")["users"] == 1 and plano("INTL", "team")["users"] == 5


def test_nenhuma_pendencia_restante_no_config():
    for mercado in CONFIG["markets"].values():
        for segmento in ("platform", "api"):
            for p in mercado[segmento]:
                assert not p.get("pending"), p["id"]


def test_enterprise_tem_o_mesmo_minimo_nos_dois_mercados():
    assert plano("BR", "enterprise")["min_credits"] == 500000
    assert plano("INTL", "enterprise")["min_credits"] == 500000


def test_planos_sem_creditos_definidos_ficam_fora_e_sao_avisados():
    planos = [
        {"id": "x", "price_type": "paid", "price_monthly": {"USD": 9}, "credits_included": None,
         "overage": "block", "features": [], "pending": ["credits_included"]},
        {"id": "y", "price_type": "paid", "price_monthly": {"USD": 19}, "credits_included": 5000,
         "overage": "block", "features": []},
    ]
    r = js(f"P.recomendarPlano({json.dumps(planos)},'USD',{{imagens:1000}},'monthly',C)")
    assert r["recomendado"]["id"] == "y"
    assert r["indefinidos"] == ["x"]


def test_empate_fica_com_o_primeiro_do_config():
    planos = [
        {"id": "a", "price_type": "paid", "price_monthly": {"BRL": 10}, "credits_included": 100,
         "overage": "block", "features": []},
        {"id": "b", "price_type": "paid", "price_monthly": {"BRL": 10}, "credits_included": 200,
         "overage": "block", "features": []},
    ]
    r = js(f"P.recomendarPlano({json.dumps(planos)},'BRL',{{imagens:50}},'monthly',C).recomendado.id")
    assert r == "a"


# --------------------------------------------------------------------------- #
# Moeda e mercado
# --------------------------------------------------------------------------- #
def _sem_espaco_duro(texto):
    return texto.replace(" ", " ").replace(" ", " ")


@pytest.mark.parametrize(
    "valor,moeda,excedente,esperado",
    [
        (24.9, "BRL", False, "R$ 24,90"),
        (1490, "BRL", False, "R$ 1.490,00"),
        (0.03, "BRL", True, "R$ 0,030"),
        (0.022, "BRL", True, "R$ 0,022"),
        (19, "USD", False, "$19.00"),
        (599, "USD", False, "$599.00"),
        (0.0035, "USD", True, "$0.0035"),
        (0.008, "USD", True, "$0.008"),
    ],
)
def test_formatacao_de_moeda(valor, moeda, excedente, esperado):
    opcoes = "{excedente:true}" if excedente else "undefined"
    assert _sem_espaco_duro(js(f"P.formatarMoeda({valor},'{moeda}',C,{opcoes})")) == esperado


def test_moeda_vazia_para_valor_ausente():
    assert js("P.formatarMoeda(null,'BRL',C)") == ""


@pytest.mark.parametrize(
    "ambiente,esperado",
    [
        ({"fusoHorario": "America/Sao_Paulo", "idiomas": ["en-US"]}, "BR"),
        ({"fusoHorario": "America/Manaus", "idiomas": []}, "BR"),
        ({"fusoHorario": "Europe/Lisbon", "idiomas": ["pt-PT"]}, "INTL"),
        ({"fusoHorario": "Europe/Lisbon", "idiomas": ["pt-BR"]}, "BR"),
        ({"fusoHorario": "America/New_York", "idiomas": ["en-US"]}, "INTL"),
        ({"fusoHorario": None, "idiomas": ["pt"]}, "BR"),
        ({}, "INTL"),
    ],
)
def test_mercado_padrao(ambiente, esperado):
    assert js(f"P.mercadoPadrao({json.dumps(ambiente)})") == esperado


@pytest.mark.parametrize(
    "idiomas,esperado",
    [(["pt-BR", "en"], "pt-BR"), (["en-US", "pt"], "pt-BR"), (["en-GB"], "en-US"), ([], "en-US")],
)
def test_idioma_padrao(idiomas, esperado):
    assert js(f"P.idiomaPadrao({json.dumps(idiomas)})") == esperado
