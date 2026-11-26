"""CLI de chaves de API.

De proposito NAO e um endpoint HTTP. Uma rota publica que emite chaves precisa
da sua propria autenticacao — e essa autenticacao (login de desenvolvedor,
painel, verificacao de identidade) nao existe no projeto. Emitir por linha de
comando, com a service role em maos, e o que corresponde a realidade de hoje.

    python -m aida_api.gerenciar_chaves emitir "app de teste"
    python -m aida_api.gerenciar_chaves listar
    python -m aida_api.gerenciar_chaves revogar aida_ab12cd
    python -m aida_api.gerenciar_chaves assinar aida_ab12cd api_starter BR [--anual]
    python -m aida_api.gerenciar_chaves cancelar-assinatura aida_ab12cd

`assinar` liga a chave a um plano da API em `assinaturas_api`, com os termos
(creditos incluidos, excedente, moeda) copiados de config/pricing.json NESTE
momento (medicao.Assinatura.do_plano): reajustar o JSON depois nao muda o que
ja foi vendido. A assinatura ativa anterior da mesma chave e desativada e
`tokens_total` da chave volta a 0, porque chave com assinatura e medida por
creditos, nao pela cota legada do painel.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

import requests

from . import chaves_api, cobranca, config, medicao

TABELA_ASSINATURAS = "assinaturas_api"
MERCADOS = ("BR", "INTL")


# --------------------------------------------------------------------------- #
# Assinaturas (service role; a tabela tem RLS sem policy de escrita)
# --------------------------------------------------------------------------- #
def _agora_iso():
    return datetime.now(timezone.utc).isoformat()


def _checar(resposta, acao):
    if resposta.status_code >= 400:
        raise RuntimeError(f"Supabase recusou {acao} ({resposta.status_code}): {resposta.text}")
    return resposta


def _chave_pelo_prefixo(prefixo):
    """A linha de api_keys com esse prefixo. Exige exatamente uma, nao revogada."""
    chaves_api._exigir_supabase()
    resposta = _checar(
        requests.get(
            chaves_api._url_tabela(),
            params={"prefixo": f"eq.{prefixo}", "select": "id,prefixo,descricao,revogada,tokens_total"},
            headers=chaves_api._cabecalhos(),
            timeout=config.SUPABASE_TIMEOUT_S,
        ),
        "a busca da chave",
    )
    linhas = resposta.json() if isinstance(resposta.json(), list) else []
    if not linhas:
        raise RuntimeError(f"Nenhuma chave encontrada com o prefixo {prefixo}.")
    if len(linhas) > 1:
        raise RuntimeError(f"O prefixo {prefixo} corresponde a {len(linhas)} chaves; use um prefixo unico.")
    chave = linhas[0]
    if chave.get("revogada"):
        raise RuntimeError(f"A chave {prefixo} esta revogada.")
    return chave


def _desativar_assinaturas(chave_id):
    resposta = _checar(
        requests.patch(
            chaves_api._url_tabela(TABELA_ASSINATURAS),
            params={"chave_id": f"eq.{chave_id}", "ativa": "is.true"},
            json={"ativa": False, "cancelada_em": _agora_iso()},
            headers={**chaves_api._cabecalhos(), "Prefer": "return=representation"},
            timeout=config.SUPABASE_TIMEOUT_S,
        ),
        "a desativacao da assinatura anterior",
    )
    linhas = resposta.json()
    return len(linhas) if isinstance(linhas, list) else 0


def assinar_chave(prefixo, plano_id, mercado, anual=False, cfg=None):
    """Cria a assinatura da chave. Devolve (linha_criada, assinaturas_desativadas)."""
    mercado = mercado.upper()
    if mercado not in MERCADOS:
        raise ValueError(f"Mercado deve ser BR ou INTL, nao {mercado}.")
    cfg = cfg or cobranca.carregar_config()
    ids_api = [p["id"] for p in cfg["markets"][mercado]["api"]]
    if plano_id not in ids_api:
        raise ValueError(f"{plano_id} nao e um plano da API em {mercado}. Opcoes: {', '.join(ids_api)}.")
    # Levanta ValueError para plano sem creditos definidos (Enterprise: termos negociados).
    assinatura = medicao.Assinatura.do_plano(plano_id, mercado, cfg=cfg)

    chave = _chave_pelo_prefixo(prefixo)
    desativadas = _desativar_assinaturas(chave["id"])

    linha = {
        "chave_id": chave["id"],
        "plano_id": assinatura.plano_id,
        "mercado": assinatura.mercado,
        "moeda": assinatura.moeda,
        "ciclo_cobranca": "annual" if anual else "monthly",
        "creditos_incluidos": assinatura.creditos_incluidos,
        "excedente": assinatura.excedente,
        "preco_excedente": str(assinatura.preco_excedente) if assinatura.preco_excedente is not None else None,
        "ancora_ciclo": assinatura.ancora.isoformat(),
        "ativa": True,
    }
    resposta = _checar(
        requests.post(
            chaves_api._url_tabela(TABELA_ASSINATURAS),
            json=linha,
            headers={**chaves_api._cabecalhos(), "Prefer": "return=representation"},
            timeout=config.SUPABASE_TIMEOUT_S,
        ),
        "a criacao da assinatura (a anterior ja foi desativada; rode o comando de novo)",
    )
    criada = resposta.json()
    criada = criada[0] if isinstance(criada, list) and criada else linha

    _checar(
        requests.patch(
            chaves_api._url_tabela(),
            params={"id": f"eq.{chave['id']}"},
            json={"tokens_total": 0},
            headers=chaves_api._cabecalhos(),
            timeout=config.SUPABASE_TIMEOUT_S,
        ),
        "o zeramento de tokens_total",
    )
    chaves_api.limpar_cache()
    return criada, desativadas


def cancelar_assinatura(prefixo):
    """Desativa a assinatura ativa da chave. Devolve quantas foram desativadas."""
    chave = _chave_pelo_prefixo(prefixo)
    return _desativar_assinaturas(chave["id"])


def _emitir(args):
    chave, registro = chaves_api.gerar_chave(
        args.descricao,
        escopo=args.escopo,
        limite_por_janela=args.limite,
        dias_validade=args.dias,
    )
    print("Chave emitida. Ela NAO sera exibida de novo — guarde agora:\n")
    print(f"    {chave}\n")
    print(f"prefixo ...... {registro.get('prefixo')}")
    print(f"descricao .... {registro.get('descricao')}")
    print(f"escopo ....... {registro.get('escopo')}")
    print(f"limite ....... {registro.get('limite_por_janela')} chamadas por janela")
    if registro.get("expira_em"):
        print(f"expira em .... {registro['expira_em']}")


def _listar(args):
    linhas = chaves_api.listar_chaves(incluir_revogadas=args.todas)
    if not linhas:
        print("Nenhuma chave.")
        return
    print(f"{'PREFIXO':<14} {'LIMITE':>7}  {'REVOGADA':<9} {'ULTIMO USO':<28} DESCRICAO")
    for linha in linhas:
        print(
            f"{str(linha.get('prefixo','')):<14} "
            f"{str(linha.get('limite_por_janela','')):>7}  "
            f"{str(bool(linha.get('revogada'))):<9} "
            f"{str(linha.get('ultimo_uso_em') or '-'):<28} "
            f"{linha.get('descricao','')}"
        )


def _revogar(args):
    total = chaves_api.revogar_chave(args.prefixo)
    if total:
        print(f"{total} chave(s) revogada(s) para o prefixo {args.prefixo}.")
    else:
        print(f"Nenhuma chave encontrada com o prefixo {args.prefixo}.")


def _assinar(args):
    criada, desativadas = assinar_chave(args.prefixo, args.plano_id, args.mercado, anual=args.anual)
    print(f"Assinatura criada para {args.prefixo}.")
    print(f"plano ........ {criada.get('plano_id')} ({criada.get('mercado')}, {criada.get('moeda')})")
    print(f"ciclo ........ {criada.get('ciclo_cobranca')}")
    print(f"creditos ..... {criada.get('creditos_incluidos')} por mes")
    excedente = criada.get("excedente")
    if criada.get("preco_excedente") is not None:
        excedente = f"{excedente} ({criada['preco_excedente']} {criada.get('moeda')} por credito)"
    print(f"excedente .... {excedente}")
    print(f"ancora ....... {criada.get('ancora_ciclo')}")
    if desativadas:
        print(f"{desativadas} assinatura(s) anterior(es) desativada(s).")
    print("tokens_total da chave zerado (a chave passa a ser medida por creditos).")


def _cancelar_assinatura(args):
    total = cancelar_assinatura(args.prefixo)
    if total:
        print(f"Assinatura da chave {args.prefixo} cancelada. A chave continua valida, sem medicao.")
    else:
        print(f"A chave {args.prefixo} nao tinha assinatura ativa.")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Chaves da AIDA API.")
    sub = parser.add_subparsers(dest="comando", required=True)

    emitir = sub.add_parser("emitir", help="Emite uma chave nova.")
    emitir.add_argument("descricao", help="Para que/para quem e a chave.")
    emitir.add_argument("--escopo", default="analyze:image")
    emitir.add_argument("--limite", type=int, default=None, help="Chamadas por janela.")
    emitir.add_argument("--dias", type=int, default=None, help="Validade em dias.")
    emitir.set_defaults(func=_emitir)

    listar = sub.add_parser("listar", help="Lista as chaves ativas.")
    listar.add_argument("--todas", action="store_true", help="Inclui as revogadas.")
    listar.set_defaults(func=_listar)

    revogar = sub.add_parser("revogar", help="Revoga uma chave pelo prefixo.")
    revogar.add_argument("prefixo")
    revogar.set_defaults(func=_revogar)

    assinar = sub.add_parser("assinar", help="Liga a chave a um plano da API (assinaturas_api).")
    assinar.add_argument("prefixo")
    assinar.add_argument("plano_id", help="Ex.: api_free, api_starter, api_pro, api_business, api_scale.")
    assinar.add_argument("mercado", choices=MERCADOS, type=str.upper)
    assinar.add_argument("--anual", action="store_true", help="Cobranca anual (10 mensalidades).")
    assinar.set_defaults(func=_assinar)

    cancelar = sub.add_parser("cancelar-assinatura", help="Desativa a assinatura ativa da chave.")
    cancelar.add_argument("prefixo")
    cancelar.set_defaults(func=_cancelar_assinatura)

    args = parser.parse_args(argv)
    try:
        args.func(args)
    except chaves_api.AutenticacaoIndisponivel as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        print(
            "Defina SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY (a service role, "
            "nao a chave anon do front-end).",
            file=sys.stderr,
        )
        return 2
    except (RuntimeError, ValueError) as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
