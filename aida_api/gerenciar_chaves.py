"""CLI de chaves de API.

De proposito NAO e um endpoint HTTP. Uma rota publica que emite chaves precisa
da sua propria autenticacao — e essa autenticacao (login de desenvolvedor,
painel, verificacao de identidade) nao existe no projeto. Emitir por linha de
comando, com a service role em maos, e o que corresponde a realidade de hoje.

    python -m aida_api.gerenciar_chaves emitir "app de teste"
    python -m aida_api.gerenciar_chaves listar
    python -m aida_api.gerenciar_chaves revogar aida_ab12cd
"""

from __future__ import annotations

import argparse
import sys

from . import chaves_api


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
    except RuntimeError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
