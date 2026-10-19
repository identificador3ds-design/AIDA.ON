"""Baixa documentos REAIS de bancos publicos para calibrar o AIDA Documents.

Fontes (testadas em 19/10/2026):
- NapierOne (Edinburgh Napier University, licenca aberta com atribuicao): 100 (tiny)
  ou ~1.000 (small) arquivos reais por formato, coletados ate 2021-2022, em ingles.
  Bucket publico S3 "napierone.com" (eu-north-1). So os subconjuntos normais: os
  NOMAGIC (cabecalho apagado) e PASSWORD (com senha) nao servem para o AIDA.
- Essay-BR estendido (UFPI, MIT): 6.577 redacoes ENEM de dez/2015 a ago/2021, em
  portugues, gravadas como .txt. ATENCAO: o texto traz as correcoes do avaliador
  misturadas ("ex presidente ex-presidente"); nao e o texto puro do aluno.

Os arquivos sao gravados como vieram (nada e regravado, para nao criar marcas de
edicao), cada um com uma linha em <saida>/origem.csv (fonte, licenca, formato).

Uso (na pasta AIDA.ON):
    python -m aida_documents.baixar_amostras napierone --formatos PDF DOCX DOC TXT --tamanho tiny --saida ../reais_publicos
    python -m aida_documents.baixar_amostras essaybr --quantidade 200 --saida ../reais_publicos
"""

from __future__ import annotations

import argparse
import ast
import csv
import io
import re
import urllib.request
import zipfile
from pathlib import Path

NAPIERONE = "https://s3.eu-north-1.amazonaws.com/napierone.com/NapierOne/Data/{fmt}/{fmt}-{tamanho}.zip"
ESSAYBR = "https://raw.githubusercontent.com/lplnufpi/essay-br/master/extended-corpus/extended_essay-br.csv"
LICENCA_NAPIERONE = "Edinburgh Napier University License (livre, com atribuição)"
LICENCA_ESSAYBR = "MIT (LPLN-UFPI)"
_DADO_NAPIERONE = re.compile(r"^\d{4}-[a-z0-9]+\.[a-z0-9]+$")  # 0001-doc.doc; ignora a ficha DOC.pdf


def _baixar(url):
    with urllib.request.urlopen(url, timeout=600) as resposta:
        return resposta.read()


def _registrar(saida, linhas):
    arquivo = Path(saida) / "origem.csv"
    novo = not arquivo.exists()
    with open(arquivo, "a", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=["arquivo", "rotulo", "formato", "fonte", "licenca", "detalhe"], delimiter=";")
        if novo:
            escritor.writeheader()
        escritor.writerows(linhas)


def napierone(formatos, tamanho, saida, avisar=print):
    destino = Path(saida) / "reais"
    destino.mkdir(parents=True, exist_ok=True)
    for fmt in formatos:
        pacote = f"{fmt}-{tamanho}.zip"
        avisar(f"baixando {pacote}...")
        z = zipfile.ZipFile(io.BytesIO(_baixar(NAPIERONE.format(fmt=fmt, tamanho=tamanho))))
        linhas = []
        for info in z.infolist():
            nome = Path(info.filename).name  # descarta pastas do zip: nada sai de <saida>/reais
            if info.is_dir() or not _DADO_NAPIERONE.match(nome):
                continue
            final = f"napierone-{nome}"
            (destino / final).write_bytes(z.read(info))
            linhas.append({"arquivo": final, "rotulo": "REAL", "formato": fmt.lower(),
                           "fonte": f"NapierOne {pacote}", "licenca": LICENCA_NAPIERONE, "detalhe": ""})
        _registrar(saida, linhas)
        avisar(f"  {len(linhas)} arquivos em {destino}")


def essaybr(quantidade, saida, avisar=print):
    destino = Path(saida) / "reais"
    destino.mkdir(parents=True, exist_ok=True)
    avisar("baixando Essay-BR...")
    csv.field_size_limit(10**8)
    redacoes = list(csv.DictReader(io.StringIO(_baixar(ESSAYBR).decode("utf-8"))))
    linhas = []
    for i, r in enumerate(redacoes[:quantidade], 1):
        try:  # o campo vem como lista Python de paragrafos
            paragrafos = ast.literal_eval(r["essay"])
        except (ValueError, SyntaxError):
            paragrafos = [r["essay"]]
        texto = "\n\n".join(p.strip() for p in paragrafos if p.strip())
        if r.get("title"):
            texto = r["title"].strip() + "\n\n" + texto
        final = f"essaybr-{i:04d}.txt"
        (destino / final).write_text(texto + "\n", encoding="utf-8")
        linhas.append({"arquivo": final, "rotulo": "REAL", "formato": "txt", "fonte": "Essay-BR estendido",
                       "licenca": LICENCA_ESSAYBR, "detalhe": f"tema {r.get('prompt')}, nota {r.get('score')}"})
    _registrar(saida, linhas)
    avisar(f"  {len(linhas)} redações em {destino}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="fonte", required=True)
    n1 = sub.add_parser("napierone")
    n1.add_argument("--formatos", nargs="+", default=["PDF", "DOCX", "DOC", "TXT"], choices=["PDF", "DOCX", "DOC", "TXT"])
    n1.add_argument("--tamanho", default="tiny", choices=["tiny", "small"], help="tiny ~100, small ~1.000 por formato")
    n1.add_argument("--saida", default="reais_publicos")
    eb = sub.add_parser("essaybr")
    eb.add_argument("--quantidade", type=int, default=200)
    eb.add_argument("--saida", default="reais_publicos")
    args = parser.parse_args(argv)
    if args.fonte == "napierone":
        napierone(args.formatos, args.tamanho, args.saida)
    else:
        essaybr(args.quantidade, args.saida)


if __name__ == "__main__":
    main()
