"""Mede o modelo de audio em midia que ele NAO viu no treino (ex.: trilhas de videos).

O treino usa audiolivros (MLS) contra TTS (MLAAD). Isso nao garante nada sobre
o audio de um video de celular ou de um Sora/Veo: canal, microfone, musica e
ruido de fundo sao outros. Este script responde a pergunta que importa para o
site: nos videos, quantos reais viram IA (falso positivo) e quanta IA e pega.

Estrutura: <pasta>/reais/* e <pasta>/ia/* (audio ou video). O gerador de um
arquivo IA e o prefixo do nome antes do primeiro "_" (sora2_x.mp4 -> sora2).

Uso (na pasta AIDA.ON):
    python -m aida_audio.avaliar_externo ../videos_teste_padronizado --saida ../resultados_audio/externo_videos
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

from .analisar import MAX_SEGUNDOS_ANALISE, analisar_amostras
from .carregar import AudioAusente, carregar_audio
from .modelo import ARQUIVO_MODELO, EXTENSOES_MIDIA, carregar_modelo

IA = "IA/MANIPULADA"


def listar(pasta):
    itens = []
    for classe, rotulo in (("reais", 0), ("ia", 1)):
        for arquivo in sorted((Path(pasta) / classe).glob("*")):
            if arquivo.is_file() and arquivo.suffix.lower() in EXTENSOES_MIDIA:
                gerador = "real" if rotulo == 0 else arquivo.stem.split("_")[0]
                itens.append((arquivo, rotulo, gerador))
    return itens


def _auc(y, p):
    y, p = np.asarray(y), np.asarray(p)
    pos, neg = p[y == 1], p[y == 0]
    if not len(pos) or not len(neg):
        return None
    maiores = (pos[:, None] > neg[None, :]).sum() + 0.5 * (pos[:, None] == neg[None, :]).sum()
    return float(maiores / (len(pos) * len(neg)))


def avaliar(pasta, pacote, avisar=print):
    linhas = []
    for arquivo, rotulo, gerador in listar(pasta):
        try:
            amostras, taxa = carregar_audio(arquivo, max_segundos=MAX_SEGUNDOS_ANALISE)
            r = analisar_amostras(amostras, taxa, pacote_modelo=pacote)
        except AudioAusente:
            continue  # sem trilha de audio: nao conta
        except Exception as exc:
            avisar(f"[erro] {arquivo.name}: {exc}")
            continue
        linhas.append({"arquivo": arquivo.name, "rotulo": rotulo, "gerador": gerador,
                       "resultado": r["resultado"], "probabilidade_ia": r["probabilidade_ia"],
                       "motivos": "; ".join(r["motivos"])})
    return linhas, resumir(linhas)


def resumir(linhas):
    com_prob = [l for l in linhas if l["probabilidade_ia"] is not None]
    y = [l["rotulo"] for l in com_prob]
    p = [l["probabilidade_ia"] for l in com_prob]

    def taxa(grupo, cond):
        return round(sum(cond(l) for l in grupo) / len(grupo), 4) if grupo else None

    reais = [l for l in linhas if l["rotulo"] == 0]
    ias = [l for l in linhas if l["rotulo"] == 1]
    por_gerador = defaultdict(list)
    for l in ias:
        por_gerador[l["gerador"]].append(l)
    auc = _auc(y, p)
    return {
        "arquivos": len(linhas),
        "reais": len(reais),
        "ia": len(ias),
        "auc": round(auc, 4) if auc is not None else None,
        "falso_positivo": taxa(reais, lambda l: l["resultado"] == IA),
        "reais_inconclusivos": taxa(reais, lambda l: l["resultado"] == "INCONCLUSIVO"),
        "ia_detectada": taxa(ias, lambda l: l["resultado"] == IA),
        "ia_inconclusiva": taxa(ias, lambda l: l["resultado"] == "INCONCLUSIVO"),
        "ia_detectada_por_gerador": {g: taxa(v, lambda l: l["resultado"] == IA) for g, v in sorted(por_gerador.items())},
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Avalia o modelo de áudio em mídia fora do treino.")
    parser.add_argument("pasta", type=Path, help="pasta com reais/ e ia/")
    parser.add_argument("--modelo", type=Path, default=ARQUIVO_MODELO)
    parser.add_argument("--saida", type=Path, default=None, help="pasta para resultados.csv e resumo.json")
    args = parser.parse_args(argv)

    pacote = carregar_modelo(args.modelo)
    if pacote is None:
        print(f"Modelo não encontrado: {args.modelo}", file=sys.stderr)
        return 2
    linhas, resumo = avaliar(args.pasta, pacote)
    print(json.dumps(resumo, ensure_ascii=False, indent=2))
    if args.saida and linhas:
        args.saida.mkdir(parents=True, exist_ok=True)
        with open(args.saida / "resultados.csv", "w", newline="", encoding="utf-8") as arquivo:
            escritor = csv.DictWriter(arquivo, fieldnames=list(linhas[0]))
            escritor.writeheader()
            escritor.writerows(linhas)
        (args.saida / "resumo.json").write_text(json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
