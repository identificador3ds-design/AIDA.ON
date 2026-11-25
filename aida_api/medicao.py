"""Medicao de uso: debito de creditos por analise, por ciclo de cobranca.

Regra (config/pricing.json -> credit_rules): imagem = 1 credito; video = 10
creditos por minuto iniciado (cobranca.creditos_video).

Cada chave de API pode ter uma assinatura (plano + mercado + ancora do ciclo).
O ciclo e mensal, contado a partir da ancora. Por ciclo ficam registrados o
total usado e o excedente:

* overage = "block" (API Free): o debito que passaria do incluido e RECUSADO —
  a rota responde 429 `quota_exhausted`, com a data de renovacao;
* overage = "charge" (planos pagos): o debito passa e o que ultrapassar o
  incluido conta como excedente, cobrado pelo preco do plano;
* chave sem assinatura: nao e medida (comportamento anterior, inclusive a cota
  legada `tokens_total` do painel admin).

O debito acontece ANTES de chamar o Core e e estornado se a analise falhar.
Debitar depois deixaria duas chamadas simultaneas passarem do limite do plano
gratis; debitar antes sem estorno cobraria por analise que nao aconteceu.

Duas implementacoes com a mesma interface: em memoria (desenvolvimento e
testes) e Supabase (producao, debito atomico na RPC `cobranca_debitar` de
docs/migracao-cobranca.sql — o contador de processo nao serve para cobrar,
porque com varias instancias cada uma teria o seu).
"""

from __future__ import annotations

import calendar
import os
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal

import requests

from . import cobranca, config


class MedicaoIndisponivel(RuntimeError):
    """Nao foi possivel consultar ou debitar creditos (banco fora do ar)."""


# --------------------------------------------------------------------------- #
# Ciclo
# --------------------------------------------------------------------------- #
def _somar_meses(data, meses):
    """Mesmo dia `meses` depois; dia 31 vira o ultimo dia do mes mais curto."""
    total = data.month - 1 + meses
    ano, mes = data.year + total // 12, total % 12 + 1
    dia = min(data.day, calendar.monthrange(ano, mes)[1])
    return data.replace(year=ano, month=mes, day=dia)


def ciclo_atual(ancora, agora=None):
    """(inicio, fim) do ciclo mensal ancorado em `ancora` que contem `agora`."""
    agora = agora or datetime.now(timezone.utc)
    if agora < ancora:
        return ancora, _somar_meses(ancora, 1)
    meses = (agora.year - ancora.year) * 12 + (agora.month - ancora.month)
    inicio = _somar_meses(ancora, meses)
    if inicio > agora:
        meses -= 1
        inicio = _somar_meses(ancora, meses)
    return inicio, _somar_meses(ancora, meses + 1)


# --------------------------------------------------------------------------- #
# Tipos
# --------------------------------------------------------------------------- #
@dataclass
class Assinatura:
    plano_id: str
    mercado: str
    creditos_incluidos: int
    excedente: str  # "block" | "charge" | "negotiated"
    preco_excedente: Decimal | None
    moeda: str
    ancora: datetime

    @classmethod
    def do_plano(cls, plano_id, mercado, ancora=None, cfg=None):
        """Assinatura com os termos do config NO MOMENTO da contratacao."""
        cfg = cfg or cobranca.carregar_config()
        plano = cobranca.encontrar_plano(cfg, plano_id, mercado)
        if plano is None or plano.get("credits_included") is None:
            raise ValueError(f"plano sem creditos definidos: {mercado}/{plano_id}")
        preco = plano.get("overage_price")
        return cls(
            plano_id=plano_id,
            mercado=mercado,
            creditos_incluidos=int(plano["credits_included"]),
            excedente=plano["overage"],
            preco_excedente=Decimal(preco) if preco is not None else None,
            moeda=cobranca.moeda_do_mercado(cfg, mercado),
            ancora=ancora or datetime.now(timezone.utc),
        )


@dataclass
class Debito:
    medido: bool
    permitido: bool = True
    creditos: int = 0
    usados: int = 0
    incluidos: int = 0
    plano_id: str | None = None
    excedente_politica: str | None = None
    ciclo_inicio: datetime | None = None
    ciclo_fim: datetime | None = None
    preco_excedente: Decimal | None = None
    moeda: str | None = None
    extras: dict = field(default_factory=dict)

    @property
    def restantes(self):
        return max(0, self.incluidos - self.usados)

    @property
    def creditos_excedentes(self):
        return max(0, self.usados - self.incluidos)

    def segundos_para_renovar(self, agora=None):
        if not self.ciclo_fim:
            return 0
        agora = agora or datetime.now(timezone.utc)
        return max(1, int((self.ciclo_fim - agora).total_seconds()) + 1)

    def cabecalhos(self):
        if not self.medido:
            return {}
        return {
            "X-AIDA-Plan": self.plano_id or "",
            "X-AIDA-Credits-Included": str(self.incluidos),
            "X-AIDA-Credits-Used": str(self.usados),
            "X-AIDA-Credits-Remaining": str(self.restantes),
            "X-AIDA-Overage-Credits": str(self.creditos_excedentes),
            "X-AIDA-Cycle-Reset": self.ciclo_fim.isoformat() if self.ciclo_fim else "",
        }

    def resumo(self):
        """Corpo de GET /v1/usage."""
        if not self.medido:
            return {"metered": False}
        valor_excedente = None
        if self.preco_excedente is not None:
            valor_excedente = str((self.preco_excedente * self.creditos_excedentes).quantize(Decimal("0.01")))
        return {
            "metered": True,
            "plan_id": self.plano_id,
            "cycle_start": self.ciclo_inicio.isoformat(),
            "cycle_end": self.ciclo_fim.isoformat(),
            "credits_included": self.incluidos,
            "credits_used": self.usados,
            "credits_remaining": self.restantes,
            "overage_policy": self.excedente_politica,
            "overage_credits": self.creditos_excedentes,
            "overage_amount": valor_excedente,
            "currency": self.moeda,
            "rollover": False,
        }


def _debito(assinatura, usados, creditos, inicio, fim, permitido=True):
    return Debito(
        medido=True,
        permitido=permitido,
        creditos=creditos,
        usados=usados,
        incluidos=assinatura.creditos_incluidos,
        plano_id=assinatura.plano_id,
        excedente_politica=assinatura.excedente,
        ciclo_inicio=inicio,
        ciclo_fim=fim,
        preco_excedente=assinatura.preco_excedente,
        moeda=assinatura.moeda,
    )


# --------------------------------------------------------------------------- #
# Em memoria (desenvolvimento e testes)
# --------------------------------------------------------------------------- #
class MedidorEmMemoria:
    def __init__(self, assinaturas=None, assinatura_padrao=None):
        self._assinaturas = dict(assinaturas or {})
        self._padrao = assinatura_padrao
        self._usos = {}
        self._lancamentos = []
        self._lock = threading.Lock()

    def definir_assinatura(self, chave_id, assinatura):
        with self._lock:
            self._assinaturas[chave_id] = assinatura

    def _assinatura(self, chave_id):
        return self._assinaturas.get(chave_id, self._padrao)

    def debitar(self, chave_id, creditos, tipo, referencia=None, agora=None):
        assinatura = self._assinatura(chave_id)
        if assinatura is None:
            return Debito(medido=False)
        inicio, fim = ciclo_atual(assinatura.ancora, agora)
        with self._lock:
            usados = self._usos.get((chave_id, inicio), 0)
            if assinatura.excedente == "block" and usados + creditos > assinatura.creditos_incluidos:
                return _debito(assinatura, usados, 0, inicio, fim, permitido=False)
            usados += creditos
            self._usos[(chave_id, inicio)] = usados
            self._lancamentos.append((chave_id, inicio, tipo, creditos, referencia))
        return _debito(assinatura, usados, creditos, inicio, fim)

    def estornar(self, chave_id, debito, referencia=None):
        if not debito.medido or not debito.creditos:
            return
        with self._lock:
            chave = (chave_id, debito.ciclo_inicio)
            self._usos[chave] = max(0, self._usos.get(chave, 0) - debito.creditos)
            self._lancamentos.append((chave_id, debito.ciclo_inicio, "estorno", -debito.creditos, referencia))

    def uso(self, chave_id, agora=None):
        assinatura = self._assinatura(chave_id)
        if assinatura is None:
            return Debito(medido=False)
        inicio, fim = ciclo_atual(assinatura.ancora, agora)
        with self._lock:
            usados = self._usos.get((chave_id, inicio), 0)
        return _debito(assinatura, usados, 0, inicio, fim)

    def lancamentos(self):
        with self._lock:
            return list(self._lancamentos)


# --------------------------------------------------------------------------- #
# Supabase (producao)
# --------------------------------------------------------------------------- #
def _data(texto):
    return datetime.fromisoformat(str(texto).replace("Z", "+00:00"))


class MedidorSupabase:
    """Chama as RPCs de docs/migracao-cobranca.sql com a service role."""

    def _rpc(self, nome, corpo):
        try:
            resposta = requests.post(
                f"{config.SUPABASE_URL}/rest/v1/rpc/{nome}",
                json=corpo,
                headers={
                    "apikey": config.SUPABASE_SERVICE_ROLE_KEY,
                    "Authorization": f"Bearer {config.SUPABASE_SERVICE_ROLE_KEY}",
                    "Content-Type": "application/json",
                },
                timeout=config.SUPABASE_TIMEOUT_S,
            )
        except requests.RequestException as exc:
            raise MedicaoIndisponivel(str(exc)) from exc
        if resposta.status_code >= 400:
            raise MedicaoIndisponivel(f"{nome}: HTTP {resposta.status_code}")
        return resposta.json()

    @staticmethod
    def _converter(linha, creditos=0):
        if not linha or not linha.get("medido"):
            return Debito(medido=False)
        preco = linha.get("preco_excedente")
        return Debito(
            medido=True,
            permitido=bool(linha.get("permitido", True)),
            creditos=creditos if linha.get("permitido", True) else 0,
            usados=int(linha["usados"]),
            incluidos=int(linha["incluidos"]),
            plano_id=linha.get("plano_id"),
            excedente_politica=linha.get("excedente"),
            ciclo_inicio=_data(linha["ciclo_inicio"]),
            ciclo_fim=_data(linha["ciclo_fim"]),
            preco_excedente=Decimal(str(preco)) if preco is not None else None,
            moeda=linha.get("moeda"),
            extras={"lancamento_id": linha.get("lancamento_id")},
        )

    def debitar(self, chave_id, creditos, tipo, referencia=None, agora=None):
        linha = self._rpc("cobranca_debitar", {
            "p_hash_chave": chave_id, "p_creditos": int(creditos),
            "p_tipo": tipo, "p_referencia": referencia,
        })
        return self._converter(linha, creditos)

    def estornar(self, chave_id, debito, referencia=None):
        if not debito.medido or not debito.creditos:
            return
        self._rpc("cobranca_estornar", {
            "p_hash_chave": chave_id, "p_creditos": int(debito.creditos),
            "p_ciclo_inicio": debito.ciclo_inicio.isoformat(), "p_referencia": referencia,
        })

    def uso(self, chave_id, agora=None):
        return self._converter(self._rpc("cobranca_uso", {"p_hash_chave": chave_id}))


def criar_medidor():
    """Supabase em producao; em memoria no desenvolvimento.

    `AIDA_API_DEV_PLANO` (ex.: api_free) e `AIDA_API_DEV_MERCADO` (BR | INTL)
    dao uma assinatura a todas as chaves de desenvolvimento, para testar o 429
    do plano gratis sem banco.
    """
    if config.supabase_configurado():
        return MedidorSupabase()
    plano = os.environ.get("AIDA_API_DEV_PLANO")
    padrao = None
    if plano:
        padrao = Assinatura.do_plano(plano, os.environ.get("AIDA_API_DEV_MERCADO", "BR"))
    return MedidorEmMemoria(assinatura_padrao=padrao)
