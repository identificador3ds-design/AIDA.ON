"""Roda o AIDA Documents numa pasta rotulada e gera um CSV para calibrar os pesos.

Estrutura esperada (as mesmas pastas de videos_teste):
    <pasta>/reais/*.pdf
    <pasta>/ia/*.pdf        (ou manipulados/)

Uso:
    python -m aida_documents.avaliar_lote "G:/Meu Drive/TCC/documentos_teste" --saida resultado.csv
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from .analisar import analisar_documento

ROTULOS = {"reais": "REAL", "ia": "IA/MANIPULADA", "manipulados": "IA/MANIPULADA"}
COLUNAS = [
    "arquivo", "rotulo", "resultado", "acertou", "suspeita", "indicios", "revisoes", "assinaturas",
    "bytes_apos_assinatura", "paginas_sem_texto", "produtor", "benford_n", "benford_mad", "benford_mse", "erro",
]


def _auc(pares):
    """AUC pela estatistica de Mann-Whitney: P(suspeita de um manipulado > de um real)."""
    pos = [s for s, r in pares if r != "REAL"]
    neg = [s for s, r in pares if r == "REAL"]
    if not pos or not neg:
        return None
    ganhos = sum(1.0 if p > n else 0.5 if p == n else 0.0 for p in pos for n in neg)
    return ganhos / (len(pos) * len(neg))


def avaliar(pasta):
    linhas = []
    for sub, rotulo in ROTULOS.items():
        for arq in sorted((Path(pasta) / sub).glob("*.pdf")):
            linha = {"arquivo": arq.name, "rotulo": rotulo}
            try:
                r = analisar_documento(arq)
                e, b = r["estrutura"], r["benford"]
                linha.update(
                    resultado=r["resultado"], acertou=r["resultado"] == rotulo, suspeita=r["suspeita"],
                    indicios="; ".join(i["indicio"] for i in r["indicios"]), revisoes=e["revisoes"],
                    assinaturas=e["assinaturas"], bytes_apos_assinatura=e["bytes_apos_assinatura"],
                    paginas_sem_texto=e["paginas_sem_texto"], produtor=e["produtor"],
                    benford_n=b["n"], benford_mad=round(b["mad"], 5), benford_mse=round(b["mse"], 6),
                )
            except Exception as exc:  # um PDF quebrado nao para o lote
                linha["erro"] = f"{type(exc).__name__}: {exc}"
            linhas.append(linha)
    return linhas


def resumo(linhas):
    validas = [l for l in linhas if not l.get("erro")]
    decididas = [l for l in validas if l["resultado"] != "INCONCLUSIVO"]
    return {
        "total": len(linhas),
        "erros": len(linhas) - len(validas),
        "cobertura": len(decididas) / len(validas) if validas else None,
        "acuracia_decididos": sum(l["acertou"] for l in decididas) / len(decididas) if decididas else None,
        "auc_suspeita": _auc([(l["suspeita"], l["rotulo"]) for l in validas]),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pasta")
    parser.add_argument("--saida", default="resultado_documentos.csv")
    args = parser.parse_args(argv)
    linhas = avaliar(args.pasta)
    with open(args.saida, "w", newline="", encoding="utf-8-sig") as f:
        escritor = csv.DictWriter(f, fieldnames=COLUNAS, delimiter=";")
        escritor.writeheader()
        escritor.writerows(linhas)
    for chave, valor in resumo(linhas).items():
        print(f"{chave}: {valor if not isinstance(valor, float) else f'{valor:.3f}'}")
    print(f"CSV: {args.saida}")


if __name__ == "__main__":
    main()
