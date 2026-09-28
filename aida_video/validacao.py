"""AIDA Video: validacao honesta das regras de agregacao.

`avaliar_lote` escolhe a melhor combinacao da grade nos MESMOS videos em que a
mede — o numero que ele imprime e otimista por construcao. Este modulo responde
as duas perguntas que a banca vai fazer:

1. **Quanto o numero oscila?** Intervalo de confianca de 95% por bootstrap
   estratificado (reamostra videos reais e IA separadamente).
2. **A regra escolhida generaliza para um gerador que ela nunca viu?**
   Validacao cruzada deixando um gerador de fora: em cada rodada, os videos IA
   de UM gerador (mais uma fatia dos reais) ficam de fora, a grade e escolhida
   no resto, e a regra escolhida e aplicada so aos videos de fora. Juntando as
   rodadas, cada video recebe uma previsao feita por uma regra que nunca o viu.

O gerador sai do prefixo do nome do arquivo IA (`sora2_0b27b8fb.mp4` -> `sora2`),
a convencao de COMO_RODAR_AVALIACAO_VIDEOS.md. Le so os relatorios JSON gravados
por `avaliar_lote`; nao chama o Core.

Uso:
    python -m aida_video.validacao ../resultados_videos/originais
    python -m aida_video.validacao ../resultados_videos/padronizados --bootstrap 5000
"""

from __future__ import annotations

import argparse
import itertools
import json
import random
import sys
from pathlib import Path

import numpy as np

from .agregacao import IA, INCONCLUSIVO, REAL, REGRAS_PADRAO, agregar, combinar
from .avaliar_lote import GRADE_REGRAS, carregar_relatorios

GERADOR_REAL = "real"


def gerador_de(relatorio):
    if relatorio["rotulo"] == REAL:
        return GERADOR_REAL
    nome = Path(relatorio["video"]).stem
    return nome.split("_", 1)[0].lower() if "_" in nome else "desconhecido"


def prever(relatorios, regras):
    """Lista (rotulo, previsto) por video, reagregando os frames com `regras`."""
    saida = []
    for rel in relatorios:
        visual = agregar(rel["frames"], regras)
        saida.append((rel["rotulo"], combinar(visual, rel.get("audio"))["resultado"]))
    return saida


def resumir(pares):
    """Metricas de uma lista (rotulo, previsto)."""
    n = len(pares)
    reais = [p for r, p in pares if r == REAL]
    ias = [p for r, p in pares if r == IA]
    decididos = [(r, p) for r, p in pares if p != INCONCLUSIVO]
    acertos = sum(r == p for r, p in decididos)
    return {
        "videos": n,
        "acuracia_decididos": acertos / len(decididos) if decididos else None,
        "cobertura": len(decididos) / n if n else None,
        "acertos_sobre_total": acertos / n if n else None,
        "falsos_positivos": sum(p == IA for p in reais),
        "taxa_falso_positivo": sum(p == IA for p in reais) / len(reais) if reais else None,
        "recall_ia": sum(p == IA for p in ias) / len(ias) if ias else None,
        "ia_como_real": sum(p == REAL for p in ias) / len(ias) if ias else None,
    }


def _chave_ordem(m):
    # Mesmo criterio de avaliar_lote.calibrar: menos FP, mais acertos, mais cobertura.
    return (m["falsos_positivos"], -(m["acertos_sobre_total"] or 0), -(m["cobertura"] or 0))


def _grade():
    chaves = list(GRADE_REGRAS)
    for valores in itertools.product(*(GRADE_REGRAS[c] for c in chaves)):
        yield {**REGRAS_PADRAO, **dict(zip(chaves, valores))}


def escolher_regras(relatorios):
    return min(_grade(), key=lambda regras: _chave_ordem(resumir(prever(relatorios, regras))))


def bootstrap(pares, n=2000, semente=0, nivel=0.95):
    """IC por percentil, reamostrando reais e IA separadamente (proporcao fixa)."""
    rng = random.Random(semente)
    por_rotulo = {REAL: [x for x in pares if x[0] == REAL], IA: [x for x in pares if x[0] == IA]}
    amostras = {}
    for _ in range(n):
        amostra = [rng.choice(grupo) for grupo in por_rotulo.values() for _ in grupo]
        for k, v in resumir(amostra).items():
            if v is not None and k != "videos":
                amostras.setdefault(k, []).append(v)
    alfa = (1 - nivel) / 2
    return {
        k: [round(float(np.quantile(v, alfa)), 4), round(float(np.quantile(v, 1 - alfa)), 4)]
        for k, v in amostras.items()
    }


def validacao_cruzada_por_gerador(relatorios, semente=0):
    """Deixa um gerador de fora por vez; os reais sao divididos no mesmo numero de fatias."""
    geradores = sorted({gerador_de(r) for r in relatorios} - {GERADOR_REAL})
    if len(geradores) < 2:
        raise ValueError("A validação por gerador precisa de pelo menos 2 geradores IA "
                         "(prefixo do nome do arquivo, ex.: sora2_xxx.mp4).")
    reais = [r for r in relatorios if r["rotulo"] == REAL]
    random.Random(semente).shuffle(reais)
    fatia_real = {id(r): i % len(geradores) for i, r in enumerate(reais)}

    rodadas, pares_fora = [], []
    for i, gerador in enumerate(geradores):
        fora = [r for r in relatorios
                if gerador_de(r) == gerador or (r["rotulo"] == REAL and fatia_real[id(r)] == i)]
        ids_fora = {id(r) for r in fora}
        treino = [r for r in relatorios if id(r) not in ids_fora]
        regras = escolher_regras(treino)
        previstos = prever(fora, regras)
        pares_fora += previstos
        so_ia = [x for x in previstos if x[0] == IA]
        rodadas.append({
            "gerador_fora": gerador,
            "regras_escolhidas": {k: regras[k] for k in GRADE_REGRAS},
            "videos_ia": len(so_ia),
            "recall_ia": resumir(so_ia)["recall_ia"],
            "ia_como_real": resumir(so_ia)["ia_como_real"],
            "falsos_positivos_reais_fora": sum(p == IA for r, p in previstos if r == REAL),
        })
    return {"rodadas": rodadas, "fora_da_amostra": resumir(pares_fora), "pares": pares_fora}


def por_gerador(relatorios, regras):
    grupos = {}
    for rel, (rotulo, previsto) in zip(relatorios, prever(relatorios, regras)):
        grupos.setdefault(gerador_de(rel), []).append((rotulo, previsto))
    return {g: resumir(p) for g, p in sorted(grupos.items())}


def validar(pasta, n_bootstrap=2000, semente=0):
    relatorios = [r for r in carregar_relatorios(pasta) if "erro" not in r]
    if not relatorios:
        raise FileNotFoundError(f"Nenhum relatório válido em {Path(pasta) / 'relatorios'}.")

    atuais = prever(relatorios, REGRAS_PADRAO)
    melhor_na_grade = escolher_regras(relatorios)
    na_grade = prever(relatorios, melhor_na_grade)
    cv = validacao_cruzada_por_gerador(relatorios, semente)

    def bloco(pares):
        return {"pontual": _arredondar(resumir(pares)), "ic95": bootstrap(pares, n_bootstrap, semente)}

    return {
        "videos": len(relatorios),
        "regras_atuais": {"regras": {k: REGRAS_PADRAO[k] for k in GRADE_REGRAS}, **bloco(atuais),
                          "por_gerador": _arredondar(por_gerador(relatorios, REGRAS_PADRAO))},
        "melhor_da_grade_otimista": {"regras": {k: melhor_na_grade[k] for k in GRADE_REGRAS}, **bloco(na_grade),
                                     "aviso": "escolhida e medida nos mesmos vídeos: número otimista"},
        "grade_por_gerador_fora": {**bloco(cv["pares"]), "rodadas": _arredondar(cv["rodadas"])},
    }


def _arredondar(obj):
    if isinstance(obj, float):
        return round(obj, 4)
    if isinstance(obj, dict):
        return {k: _arredondar(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_arredondar(v) for v in obj]
    return obj


def _fmt(valor, ic):
    if valor is None:
        return "—"
    return f"{valor:.1%} [{ic[0]:.1%} – {ic[1]:.1%}]" if ic else f"{valor:.1%}"


def imprimir(res):
    print(f"{res['videos']} vídeos. Valores: ponto [IC 95% bootstrap]\n")
    for titulo, chave in (("Regras atuais", "regras_atuais"),
                          ("Melhor da grade, medida nos mesmos vídeos (otimista)", "melhor_da_grade_otimista"),
                          ("Grade escolhida sem ver o gerador (honesto)", "grade_por_gerador_fora")):
        b = res[chave]
        p, ic = b["pontual"], b["ic95"]
        print(f"== {titulo} ==")
        if "regras" in b:
            print(f"   regras: {b['regras']}")
        for k, nome in (("acuracia_decididos", "acurácia nos decididos"), ("cobertura", "cobertura"),
                        ("taxa_falso_positivo", "taxa de falso positivo"), ("recall_ia", "IA detectada"),
                        ("ia_como_real", "IA tomada por REAL")):
            print(f"   {nome:<24}{_fmt(p[k], ic.get(k))}")
        print(f"   falsos positivos        {p['falsos_positivos']}\n")
    print("== Por gerador fora (regra escolhida sem ele) ==")
    for r in res["grade_por_gerador_fora"]["rodadas"]:
        print(f"   {r['gerador_fora']:<14} IA detectada {r['recall_ia']:.0%}  tomada por REAL {r['ia_como_real']:.0%}"
              f"  FP reais {r['falsos_positivos_reais_fora']}  regras {r['regras_escolhidas']}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="IC por bootstrap e validação por gerador das regras de vídeo.")
    parser.add_argument("saida", type=Path, help="pasta de saída do avaliar_lote (com relatorios/)")
    parser.add_argument("--bootstrap", type=int, default=2000)
    parser.add_argument("--semente", type=int, default=0)
    args = parser.parse_args(argv)
    try:
        res = validar(args.saida, args.bootstrap, args.semente)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 2
    (args.saida / "validacao.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    imprimir(res)
    print(f"\nArquivo: {args.saida / 'validacao.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
