"""AIDA Video: combinacao ponderada de imagem, movimento e audio.

Substitui as regras fixas de `agregacao.combinar` quando o modelo treinado
existe (aida_video/modelos/fusao.joblib) e a analise de movimento rodou. Sem
isso, o video segue pelas regras, como antes.

Entradas por video (todas ja calculadas pelo pipeline):
  - probabilidade de IA da trajetoria + mediana do Core (`analisar_trajetoria`);
  - fracao de frames IA e fracao de frames REAL (voto do Core por frame);
  - maior probabilidade de IA entre os frames;
  - probabilidade de IA do audio, SE o video tiver audio avaliado.

Sao dois modelos, para a ausencia de audio nao virar atalho (nos dados de
treino quase todo video real tem audio e metade dos de IA nao tem): video sem
audio usa o modelo so de imagem; video com audio usa imagem + audio, treinado
so em videos com audio.

A saida tem faixa INCONCLUSIVA [baixo, alto). Os limiares sao escolhidos em
previsoes fora da amostra (gerador deixado de fora), com alvo de falso
positivo `fp_alvo` e de IA passando como REAL `ia_como_real_alvo`.

Uso (na pasta AIDA.ON):
    python -m aida_video.fusao ../resultados_videos/padronizados_r6fp6 \\
        --trajetoria ../resultados_videos/trajetoria_padronizados \\
        --audio ../resultados_audio/com_videos/previsoes.csv --saida ../resultados_videos/fusao
    (acrescente --salvar-modelo para gravar aida_video/modelos/fusao.joblib)
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np

from .agregacao import IA, INCONCLUSIVO, REAL, REGRAS_PADRAO, agregar, combinar, combinar_visual

ARQUIVO_MODELO = Path(__file__).resolve().parent / "modelos" / "fusao.joblib"
NOMES_VISUAIS = ["logit_trajetoria_core", "fracao_frames_ia", "fracao_frames_real", "logit_max_frame"]
NOMES_AUDIO = ["logit_audio"]
FP_ALVO = 0.05
IA_COMO_REAL_ALVO = 0.10
# Audio a menos disto do limiar do aida_audio (a confianca "baixa" dele) nao entra na
# conta: o video segue pelo modelo so de imagem. Sem isso o audio, que tem o maior peso,
# decidia sozinho videos com imagem e movimento de camera real (ex.: teste11, audio 0,64).
MARGEM_AUDIO_INCERTO = 0.15
LIMIAR_AUDIO_PADRAO = 0.63


def _logit(p):
    p = min(max(float(p), 1e-4), 1 - 1e-4)
    return float(np.log(p / (1 - p)))


def _frames_validos(frames):
    return [f for f in frames if not f.get("erro") and f.get("resultado")]


def audio_utilizavel(prob_audio, limiar_audio=LIMIAR_AUDIO_PADRAO, margem=MARGEM_AUDIO_INCERTO):
    """prob_audio, ou None se ausente ou perto demais do limiar do modelo de audio."""
    if not isinstance(prob_audio, (int, float)):
        return None
    limiar_audio = LIMIAR_AUDIO_PADRAO if limiar_audio is None else float(limiar_audio)
    return None if abs(float(prob_audio) - limiar_audio) < margem else float(prob_audio)


def caracteristicas(frames, prob_trajetoria, prob_audio=None):
    """Linha de caracteristicas de um video. prob_audio=None (sem audio avaliado) poe 0 na
    coluna do audio, que so o modelo com audio le."""
    validos = _frames_validos(frames)
    probs = [f["probabilidade_ia"] for f in validos
             if not f.get("fora_de_dominio") and isinstance(f.get("probabilidade_ia"), (int, float))]
    n = len(validos)
    linha = [
        _logit(prob_trajetoria),
        sum(f["resultado"] == IA for f in validos) / n if n else 0.0,
        sum(f["resultado"] == REAL for f in validos) / n if n else 0.0,
        _logit(max(probs)) if probs else 0.0,
        _logit(prob_audio) if prob_audio is not None else 0.0,
    ]
    return linha


def novo_modelo():
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    return make_pipeline(StandardScaler(), LogisticRegression(C=0.5, max_iter=2000, class_weight="balanced"))


class Fusao:
    """Modelo so de imagem + modelo de imagem e audio (ver docstring do modulo)."""

    def fit(self, X, y, tem_audio):
        n = len(NOMES_VISUAIS)
        self.visual = novo_modelo().fit(X[:, :n], y)
        # Sem as duas classes entre os videos com audio nao ha o que aprender: fica so a imagem.
        self.com_audio = None
        if len(set(y[tem_audio].tolist())) == 2:
            self.com_audio = novo_modelo().fit(X[tem_audio], y[tem_audio])
        return self

    def prob(self, X, tem_audio):
        n = len(NOMES_VISUAIS)
        p = self.visual.predict_proba(X[:, :n])[:, 1]
        if self.com_audio is not None and tem_audio.any():
            p[tem_audio] = self.com_audio.predict_proba(X[tem_audio])[:, 1]
        return p


def _matriz(videos):
    X = np.array([caracteristicas(v["frames"], v["p_trajetoria"], v["p_audio"]) for v in videos])
    y = np.array([int(v["rotulo"] == IA) for v in videos])
    a = np.array([v["p_audio"] is not None for v in videos])
    return X, y, a


def escolher_limiares(y, p, fp_alvo=FP_ALVO, ia_como_real_alvo=IA_COMO_REAL_ALVO):
    """alto: menor limiar com FP <= alvo nos reais; baixo: maior limiar com IA abaixo dele <= alvo."""
    reais, ias = np.sort(p[y == 0]), np.sort(p[y == 1])
    k = int(np.floor(fp_alvo * len(reais)))
    alto = float(reais[len(reais) - k - 1]) + 1e-9 if k < len(reais) else 0.0
    j = int(np.floor(ia_como_real_alvo * len(ias)))
    baixo = float(ias[j]) - 1e-9 if j < len(ias) else 1.0
    return min(baixo, alto), alto


def decidir(prob, baixo, alto):
    return IA if prob >= alto else (REAL if prob < baixo else INCONCLUSIVO)


# --------------------------------------------------------------------------- uso no pipeline

_PACOTE = None


def carregar_modelo(caminho=None):
    global _PACOTE
    caminho = Path(caminho or ARQUIVO_MODELO)
    if caminho == ARQUIVO_MODELO and _PACOTE is not None:
        return _PACOTE
    if not caminho.is_file():
        return None
    import joblib

    pacote = joblib.load(caminho)
    if caminho == ARQUIVO_MODELO:
        _PACOTE = pacote
    return pacote


def combinar_ponderado(frames, trajetoria, audio, pacote):
    """Conclusao pela combinacao ponderada, ou None se faltar entrada (usa as regras)."""
    if not pacote or not trajetoria or not trajetoria.get("disponivel") or not _frames_validos(frames):
        return None
    audio = audio or {}
    bruto = audio.get("probabilidade_ia")
    p_audio = audio_utilizavel(bruto, audio.get("limiar", pacote.get("limiar_audio")),
                               pacote.get("margem_audio_incerto", MARGEM_AUDIO_INCERTO))
    X = np.array([caracteristicas(frames, trajetoria["probabilidade_ia"], p_audio)])
    prob = float(pacote["modelo"].prob(X, np.array([p_audio is not None]))[0])
    baixo, alto = pacote["faixa_inconclusiva"]
    resultado = decidir(prob, baixo, alto)
    fontes = "imagem, movimento e áudio" if p_audio is not None else "imagem e movimento"
    motivos = [f"combinação ponderada de {fontes}: {prob:.0%} de probabilidade de IA "
               f"(inconclusivo entre {baixo:.0%} e {alto:.0%})"]
    if p_audio is None and isinstance(bruto, (int, float)):
        motivos.append(f"áudio com {bruto:.0%} de probabilidade de IA, perto demais do limiar "
                       "(confiança baixa): não entrou na conta; decidido pela imagem e movimento")
    elif p_audio is None and audio.get("presente"):
        motivos.append("áudio sem avaliação conclusiva; decidido só pela imagem")
    return {
        "resultado": resultado,
        "inconclusivo": resultado == INCONCLUSIVO,
        "motivos": motivos,
        "combinacao": {"metodo": "ponderada", "probabilidade_ia": round(prob, 4),
                       "faixa_inconclusiva": [round(baixo, 4), round(alto, 4)], "usa_audio": p_audio is not None},
    }


# --------------------------------------------------------------------------- treino e avaliacao

def limiar_audio_publicado():
    try:
        import joblib

        from aida_audio.modelo import ARQUIVO_MODELO as MODELO_AUDIO

        return float(joblib.load(MODELO_AUDIO)["limiar"])
    except Exception:
        return LIMIAR_AUDIO_PADRAO


def carregar_videos(pasta_core, pasta_trajetoria, csv_audio, avisar=print, margem_audio=MARGEM_AUDIO_INCERTO):
    """Junta relatorios do Core, cache da trajetoria e previsoes de audio fora da amostra.

    A probabilidade da trajetoria tambem sai fora da amostra (gerador deixado de fora),
    com a mediana do Core destes relatorios, como em producao."""
    from .avaliar_lote import carregar_relatorios
    from .treinar_trajetoria import _prob_core, carregar_cache, fora_da_amostra
    from .validacao import gerador_de

    core = {(r["pasta"], r["video"]): r for r in carregar_relatorios(pasta_core) if "erro" not in r}
    mediana = _prob_core(core.values())
    registros = [r for r in carregar_cache(pasta_trajetoria) if (r["pasta"], r["video"]) in mediana]
    extra = {i: [mediana[(r["pasta"], r["video"])]] for i, r in enumerate(registros)}
    p_traj = fora_da_amostra(registros, extra=extra)

    audio, limiar_audio = {}, limiar_audio_publicado()
    if csv_audio:
        with open(csv_audio, encoding="utf-8") as f:
            audio = {linha["arquivo"]: float(linha["probabilidade_ia"]) for linha in csv.DictReader(f)}

    videos = [{
        "video": r["video"], "pasta": r["pasta"], "rotulo": r["rotulo"], "gerador": gerador_de(r),
        "frames": core[(r["pasta"], r["video"])]["frames"], "p_trajetoria": float(p_traj[i]),
        "p_audio": audio_utilizavel(audio.get(r["video"]), limiar_audio, margem_audio),
        "p_audio_bruto": audio.get(r["video"]),
    } for i, r in enumerate(registros)]
    avisar(f"{len(videos)} videos ({sum(v['rotulo'] == REAL for v in videos)} reais), "
           f"{sum(v['p_audio'] is not None for v in videos)} com audio usado "
           f"({sum(v['p_audio_bruto'] is not None for v in videos)} com audio avaliado)")
    return registros, videos


def regra_atual(v, faixa_audio):
    """O que o site fazia antes: regras de agregacao + combinar_visual + combinar."""
    visual = agregar(v["frames"], REGRAS_PADRAO)
    visual = combinar_visual(visual, {"disponivel": True, "probabilidade_ia": v["p_trajetoria"], "usa_core": True})
    audio = None
    p_audio = v.get("p_audio_bruto", v["p_audio"])
    if p_audio is not None:
        baixo, alto = faixa_audio
        audio = {"resultado": decidir(p_audio, baixo, alto), "probabilidade_ia": p_audio}
    return combinar(visual, audio)["resultado"]


def fora_da_amostra_ponderada(registros, videos, fp_alvo=FP_ALVO, ia_como_real_alvo=IA_COMO_REAL_ALVO):
    """Previsao de cada video por um modelo e limiares que nunca viram o gerador dele.

    Os limiares de cada dobra saem de previsoes fora da amostra DENTRO do treino da dobra."""
    from .treinar_trajetoria import dobras_por_gerador

    X, y, a = _matriz(videos)
    prob = np.full(len(videos), np.nan)
    prev = [None] * len(videos)
    for _, fora in dobras_por_gerador(registros):
        fora_set = set(fora)
        tr = [i for i in range(len(videos)) if i not in fora_set]
        p_tr = np.full(len(tr), np.nan)
        for _, fora_int in dobras_por_gerador([registros[i] for i in tr]):
            fi = set(fora_int)
            tr2 = [tr[k] for k in range(len(tr)) if k not in fi]
            idx = [tr[k] for k in fora_int]
            p_tr[list(fora_int)] = Fusao().fit(X[tr2], y[tr2], a[tr2]).prob(X[idx], a[idx])
        baixo, alto = escolher_limiares(y[tr], p_tr, fp_alvo, ia_como_real_alvo)
        p = Fusao().fit(X[tr], y[tr], a[tr]).prob(X[fora], a[fora])
        prob[fora] = p
        for i, pi in zip(fora, p):
            prev[i] = decidir(pi, baixo, alto)
    return prev, prob


def resumo(videos, previstos):
    from .validacao import resumir

    m = resumir([(v["rotulo"], p) for v, p in zip(videos, previstos)])
    m["inconclusivos"] = sum(p == INCONCLUSIVO for p in previstos) / len(previstos)
    m["acerto_por_gerador"] = {}
    for g in sorted({v["gerador"] for v in videos}):
        sel = [(v, p) for v, p in zip(videos, previstos) if v["gerador"] == g]
        m["acerto_por_gerador"][g] = round(sum(p == v["rotulo"] for v, p in sel) / len(sel), 4)
    return {k: (round(x, 4) if isinstance(x, float) else x) for k, x in m.items()}


def mcnemar(videos, a, b):
    """Teste exato pareado: so a regra A acerta x so a B acerta."""
    from math import comb

    so_a = sum(p == v["rotulo"] and q != v["rotulo"] for v, p, q in zip(videos, a, b))
    so_b = sum(q == v["rotulo"] and p != v["rotulo"] for v, p, q in zip(videos, a, b))
    n = so_a + so_b
    p = min(1.0, 2 * sum(comb(n, k) for k in range(min(so_a, so_b) + 1)) / 2 ** n) if n else 1.0
    return {"so_regra_atual_acerta": so_a, "so_ponderada_acerta": so_b, "p_valor": round(p, 4)}


def treinar_final(videos, fp_alvo=FP_ALVO, ia_como_real_alvo=IA_COMO_REAL_ALVO, registros=None):
    """Modelo em todos os videos; limiares nas previsoes fora da amostra."""
    X, y, a = _matriz(videos)
    _, prob = fora_da_amostra_ponderada(registros, videos, fp_alvo, ia_como_real_alvo)
    baixo, alto = escolher_limiares(y, prob, fp_alvo, ia_como_real_alvo)
    return {
        "modelo": Fusao().fit(X, y, a),
        "faixa_inconclusiva": (baixo, alto),
        "caracteristicas": NOMES_VISUAIS + NOMES_AUDIO,
        "fp_alvo": fp_alvo,
        "ia_como_real_alvo": ia_como_real_alvo,
        "videos_treino": len(videos),
        "videos_treino_com_audio": int(a.sum()),
        "limiar_audio": limiar_audio_publicado(),
        "margem_audio_incerto": MARGEM_AUDIO_INCERTO,
        "descricao": "LogReg (imagem) + LogReg (imagem+audio); audio de confianca baixa fica de fora; "
                     "limiares fora da amostra por gerador",
    }


def _reempacotar(pacote, modulo):
    """Troca objetos de classes definidas em __main__ pelas mesmas classes do módulo importável."""
    def trocar(obj):
        cls = type(obj)
        if getattr(cls, "__module__", None) == "__main__" and hasattr(modulo, cls.__name__):
            novo = getattr(modulo, cls.__name__).__new__(getattr(modulo, cls.__name__))
            novo.__dict__.update({k: trocar(v) for k, v in obj.__dict__.items()})
            return novo
        if isinstance(obj, dict):
            return {k: trocar(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [trocar(v) for v in obj]
        return obj
    return trocar(pacote)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Treina e avalia a combinacao ponderada do AIDA Video.")
    parser.add_argument("relatorios_core", type=Path, help="saida do avaliar_lote (com relatorios/)")
    parser.add_argument("--trajetoria", type=Path, required=True, help="saida do treinar_trajetoria (cache)")
    parser.add_argument("--audio", type=Path, default=None, help="previsoes.csv do treinar_com_videos")
    parser.add_argument("--saida", type=Path, default=None)
    parser.add_argument("--fp-alvo", type=float, default=FP_ALVO)
    parser.add_argument("--ia-como-real-alvo", type=float, default=IA_COMO_REAL_ALVO)
    parser.add_argument("--salvar-modelo", action="store_true")
    args = parser.parse_args(argv)

    registros, videos = carregar_videos(args.relatorios_core, args.trajetoria, args.audio)
    faixa_audio = (0.48, 0.63)
    try:
        import joblib

        from aida_audio.modelo import ARQUIVO_MODELO as MODELO_AUDIO

        faixa_audio = tuple(joblib.load(MODELO_AUDIO)["faixa_inconclusiva"])
    except Exception:
        pass
    base = [regra_atual(v, faixa_audio) for v in videos]
    nova, prob = fora_da_amostra_ponderada(registros, videos, args.fp_alvo, args.ia_como_real_alvo)
    from .avaliar_lote import _auc

    y = [int(v["rotulo"] == IA) for v in videos]
    res = {
        "videos": len(videos),
        "regra_atual": resumo(videos, base),
        "ponderada": {**resumo(videos, nova), "auc": round(_auc(y, list(prob)), 4)},
        "auc_trajetoria_core": round(_auc(y, [v["p_trajetoria"] for v in videos]), 4),
        "comparacao_pareada": mcnemar(videos, base, nova),
    }
    print(json.dumps(res, ensure_ascii=False, indent=1))
    if args.saida:
        args.saida.mkdir(parents=True, exist_ok=True)
        (args.saida / "avaliacao_fusao.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    if args.salvar_modelo:
        import joblib

        pacote = treinar_final(videos, args.fp_alvo, args.ia_como_real_alvo, registros)
        # Rodando como "python -m aida_video.fusao", a classe nasce em __main__ e o
        # pickle guardaria "__main__.Fusao": qualquer outro programa (servidor,
        # avaliar_lote) quebraria ao carregar. Grava sempre pelo nome do módulo.
        if __name__ == "__main__":
            import importlib

            pacote = _reempacotar(pacote, importlib.import_module("aida_video.fusao"))
        ARQUIVO_MODELO.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(pacote, ARQUIVO_MODELO)
        print(f"modelo gravado em {ARQUIVO_MODELO} | faixa {pacote['faixa_inconclusiva']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
