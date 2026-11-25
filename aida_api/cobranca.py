"""Regras de preco e de checkout, lidas de config/pricing.json.

O mesmo JSON alimenta a pagina de precos (scripts/aida-precos-core.js). La os
numeros sao para EXIBIR; aqui sao os que valem. O preco cobrado sai sempre
deste modulo (ou, quando houver, do gateway de pagamento), nunca de um valor
enviado pelo cliente: o corpo do checkout carrega o plano e o ciclo, e
qualquer campo de valor que venha junto e ignorado.

Anti-arbitragem: os planos em reais sao mais baratos que os em dolar. Checkout
em BRL so passa com CPF ou CNPJ valido e endereco de cobranca no Brasil. O
seletor de moeda do site e so visual; a decisao e daqui.

Dinheiro em Decimal, carregado do JSON como Decimal: 0.1 + 0.2 em float nao e
0.3, e uma fatura nao pode depender disso.
"""

from __future__ import annotations

import json
import math
import os
import re
from decimal import ROUND_HALF_UP, Decimal
from functools import lru_cache
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
CAMINHO_PADRAO = RAIZ / "config" / "pricing.json"

CICLOS = ("monthly", "annual")
SEGMENTOS = ("platform", "api")
CENTAVO = Decimal("0.01")

UFS = frozenset(
    "AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split()
)


class ErroCheckout(Exception):
    """Pedido de checkout recusado. `codigo` entra no contrato de erro /v1."""

    def __init__(self, codigo, mensagem, status=422, detalhes=None):
        super().__init__(mensagem)
        self.codigo = codigo
        self.mensagem = mensagem
        self.status = status
        self.detalhes = detalhes


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=4)
def _ler(caminho):
    return json.loads(Path(caminho).read_text(encoding="utf-8"), parse_float=Decimal)


def carregar_config(caminho=None):
    """Config de precos. `AIDA_PRICING_PATH` aponta outro arquivo (deploy fora do repo)."""
    return _ler(str(caminho or os.environ.get("AIDA_PRICING_PATH") or CAMINHO_PADRAO))


def limpar_cache():
    _ler.cache_clear()


def planos(config, mercado):
    m = config["markets"].get(mercado)
    if m is None:
        return []
    return [p for segmento in SEGMENTOS for p in m[segmento]]


def encontrar_plano(config, plano_id, mercado):
    return next((p for p in planos(config, mercado) if p["id"] == plano_id), None)


def moeda_do_mercado(config, mercado):
    return config["markets"][mercado]["currency"]


# --------------------------------------------------------------------------- #
# Creditos
# --------------------------------------------------------------------------- #
def creditos_imagem(config=None):
    config = config or carregar_config()
    return int(config["credit_rules"]["image"])


def creditos_video(segundos, config=None):
    """Creditos por minuto INICIADO: 60 s = 10, 61 s = 20. Zero ou invalido = 0."""
    config = config or carregar_config()
    try:
        s = float(segundos)
    except (TypeError, ValueError):
        return 0
    if not math.isfinite(s) or s <= 0:
        return 0
    return math.ceil(s / 60) * int(config["credit_rules"]["video_per_started_minute"])


# --------------------------------------------------------------------------- #
# Preco
# --------------------------------------------------------------------------- #
def preco_mensal(plano, moeda):
    valor = (plano.get("price_monthly") or {}).get(moeda)
    return Decimal(valor) if valor is not None else None


def preco_do_ciclo(plano, moeda, ciclo, config=None):
    """Mensal, ou anual = annual_months_charged x mensal (10 = dois meses gratis)."""
    if ciclo not in CICLOS:
        raise ValueError(f"ciclo desconhecido: {ciclo}")
    mensal = preco_mensal(plano, moeda)
    if mensal is None:
        return None
    if ciclo == "annual":
        config = config or carregar_config()
        mensal = mensal * int(config["annual_months_charged"])
    return mensal.quantize(CENTAVO, rounding=ROUND_HALF_UP)


# --------------------------------------------------------------------------- #
# Documentos brasileiros
# --------------------------------------------------------------------------- #
def _so_digitos(texto):
    return re.sub(r"\D", "", texto or "")


def cpf_valido(texto):
    cpf = _so_digitos(texto)
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    for posicao in (9, 10):
        soma = sum(int(cpf[i]) * (posicao + 1 - i) for i in range(posicao))
        dv = (soma * 10) % 11 % 10
        if dv != int(cpf[posicao]):
            return False
    return True


def _normalizar_cnpj(texto):
    # Desde 07/2026 a Receita emite CNPJ alfanumerico: as 12 primeiras posicoes
    # aceitam [0-9A-Z] e os dois digitos verificadores seguem numericos.
    return re.sub(r"[.\-/\s]", "", (texto or "").upper())


def cnpj_valido(texto):
    cnpj = _normalizar_cnpj(texto)
    if not re.fullmatch(r"[0-9A-Z]{12}[0-9]{2}", cnpj) or cnpj == cnpj[0] * 14:
        return False
    valores = [ord(c) - 48 for c in cnpj]  # '0'..'9' -> 0..9, 'A'..'Z' -> 17..42
    for tamanho in (12, 13):
        pesos = [(i % 8) + 2 for i in range(tamanho)][::-1]
        soma = sum(v * p for v, p in zip(valores[:tamanho], pesos))
        resto = soma % 11
        dv = 0 if resto < 2 else 11 - resto
        if dv != valores[tamanho]:
            return False
    return True


def tipo_documento(texto):
    """'cpf' | 'cnpj' | None."""
    if cpf_valido(texto):
        return "cpf"
    if cnpj_valido(texto):
        return "cnpj"
    return None


# --------------------------------------------------------------------------- #
# Checkout
# --------------------------------------------------------------------------- #
def _validar_endereco_brasil(endereco):
    if not isinstance(endereco, dict):
        raise ErroCheckout("billing_address_required", "Informe o endereco de cobranca.", 422)
    pais = str(endereco.get("country") or "").strip().upper()
    if pais != "BR":
        raise ErroCheckout(
            "billing_country_mismatch",
            "Planos em reais exigem endereco de cobranca no Brasil.",
            422,
            {"expected_country": "BR"},
        )
    if len(_so_digitos(endereco.get("postal_code"))) != 8:
        raise ErroCheckout("invalid_postal_code", "CEP invalido: use 8 digitos.", 422)
    if str(endereco.get("state") or "").strip().upper() not in UFS:
        raise ErroCheckout("invalid_state", "UF invalida no endereco de cobranca.", 422)
    for campo in ("city", "line1"):
        if not str(endereco.get(campo) or "").strip():
            raise ErroCheckout(
                "billing_address_required", f"Campo '{campo}' do endereco e obrigatorio.", 422
            )


def cotar_checkout(pedido, config=None):
    """Valida o pedido e devolve a cotacao calculada NO SERVIDOR.

    `pedido`: {plan_id, market, billing_cycle, tax_id, billing_address}. Campos
    de valor (price, amount, currency...) sao ignorados de proposito.
    """
    config = config or carregar_config()
    if not isinstance(pedido, dict):
        raise ErroCheckout("invalid_field", "Envie um objeto JSON.", 400)

    mercado = str(pedido.get("market") or "").strip().upper()
    if mercado not in config["markets"]:
        raise ErroCheckout(
            "invalid_field", "Campo 'market' deve ser 'BR' ou 'INTL'.", 400,
            {"accepted": sorted(config["markets"])},
        )

    ciclo = pedido.get("billing_cycle") or "monthly"
    if ciclo not in CICLOS:
        raise ErroCheckout("invalid_field", "Campo 'billing_cycle' deve ser 'monthly' ou 'annual'.", 400)

    plano = encontrar_plano(config, pedido.get("plan_id"), mercado)
    if plano is None:
        raise ErroCheckout("plan_not_found", "Plano inexistente neste mercado.", 404)
    if plano["price_type"] in ("contact", "validation"):
        raise ErroCheckout("plan_requires_contact", "Este plano e contratado pelo formulario comercial.", 422)
    if plano["price_type"] != "paid":
        raise ErroCheckout("plan_not_purchasable", "Planos gratuitos nao passam pelo checkout.", 422)

    moeda = moeda_do_mercado(config, mercado)
    documento = None
    if moeda == "BRL":
        bruto = pedido.get("tax_id")
        if not bruto:
            raise ErroCheckout("tax_id_required", "Planos em reais exigem CPF ou CNPJ.", 422)
        documento = tipo_documento(str(bruto))
        if documento is None:
            raise ErroCheckout("invalid_tax_id", "CPF ou CNPJ invalido.", 422)
        _validar_endereco_brasil(pedido.get("billing_address"))

    valor = preco_do_ciclo(plano, moeda, ciclo, config)
    excedente = plano.get("overage_price")
    return {
        "plan_id": plano["id"],
        "market": mercado,
        "currency": moeda,
        "billing_cycle": ciclo,
        "amount": str(valor),
        "credits_included": plano.get("credits_included"),
        "overage_price": str(excedente) if excedente is not None else None,
        "tax_id_type": documento,
        "gateway_price_id": (plano.get("gateway_price_ids") or {}).get(ciclo),
    }


def checkout_habilitado(config=None):
    config = config or carregar_config()
    return bool((config.get("checkout") or {}).get("enabled"))
