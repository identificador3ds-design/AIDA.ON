"""AIDA Video - Etapa 04: agregacao temporal.

Transforma o resultado de cada frame numa conclusao sobre o video.

Regras (heuristicas iniciais, a calibrar com o dataset de videos do passo 1
da pesquisa — por isso ficam todas em REGRAS_PADRAO, nao espalhadas no codigo):

- frames com erro ou `fora_de_dominio` (tela preta, texto, cartela) nao votam;
- com menos de `min_frames_validos` validos, o video e INCONCLUSIVO;
- IA/MANIPULADA se a fracao de frames IA passa `fracao_ia`, ou se ha uma
  sequencia de pelo menos `sequencia_minima` frames IA seguidos cobrindo
  `fracao_trecho` do video (deepfake localizado: so um trecho foi trocado);
- REAL se a fracao de frames REAL passa `fracao_real` e nao ha trecho suspeito;
- qualquer outra combinacao e INCONCLUSIVO, com o motivo.

A decisao usa o `resultado` que o Core deu a cada frame (ele ja aplica o limiar
calibrado e a faixa inconclusiva). As probabilidades agregadas vao junto para
analise, mas nao decidem sozinhas.
"""

from __future__ import annotations

import numpy as np

IA = "IA/MANIPULADA"
REAL = "REAL"
INCONCLUSIVO = "INCONCLUSIVO"

REGRAS_PADRAO = {
    "min_frames_validos": 3,
    "fracao_ia": 0.5,
    "fracao_real": 0.7,
    "sequencia_minima": 3,
    "fracao_trecho": 0.15,
    # Movimento (trajetoria DINOv2, fundida com a mediana do Core): entre os dois
    # limites o video fica INCONCLUSIVO. Medido fora da amostra (gerador deixado
    # de fora, 336 videos): 14% inconclusivos; nos decididos 86% da IA detectada
    # e 6,9% de falso positivo (so os frames: 11% e 0,6%).
    "trajetoria_faixa_inconclusiva": (0.35, 0.65),
    # Audio: acima disso, sozinho marca IA mesmo com a imagem REAL. Nenhum video
    # real de celular com imagem REAL passou de 0,80 (validacao fora da amostra).
    "audio_ia_forte": 0.90,
}


def _trechos(frames, rotulo):
    """Sequencias consecutivas (na ordem do tempo) de frames com `rotulo`."""
    trechos, atual = [], []
    for frame in frames:
        if frame.get("resultado") == rotulo:
            atual.append(frame)
        elif atual:
            trechos.append(atual)
            atual = []
    if atual:
        trechos.append(atual)
    return [
        {
            "inicio_s": t[0]["tempo_s"],
            "fim_s": t[-1]["tempo_s"],
            "frames": len(t),
            "probabilidade_ia_media": round(
                float(np.mean([f["probabilidade_ia"] for f in t if f.get("probabilidade_ia") is not None] or [0.0])), 4
            ),
        }
        for t in trechos
    ]


def agregar(frames, regras=None):
    """`frames`: lista na ordem do tempo com tempo_s, resultado, probabilidade_ia,
    fora_de_dominio e, quando falhou, `erro`."""
    regras = {**REGRAS_PADRAO, **(regras or {})}
    com_erro = [f for f in frames if f.get("erro")]
    fora = [f for f in frames if not f.get("erro") and f.get("fora_de_dominio")]
    validos = [f for f in frames if not f.get("erro") and not f.get("fora_de_dominio")]

    contagem = {IA: 0, REAL: 0, INCONCLUSIVO: 0}
    for f in validos:
        contagem[f.get("resultado") if f.get("resultado") in contagem else INCONCLUSIVO] += 1

    probs = np.array(
        [f["probabilidade_ia"] for f in validos if isinstance(f.get("probabilidade_ia"), (int, float))],
        dtype=np.float64,
    )
    estatisticas = (
        {
            "media": round(float(probs.mean()), 4),
            "mediana": round(float(np.median(probs)), 4),
            "maxima": round(float(probs.max()), 4),
            "p90": round(float(np.percentile(probs, 90)), 4),
            "desvio": round(float(probs.std()), 4),
        }
        if probs.size
        else None
    )

    n = len(validos)
    fracoes = {k: (round(v / n, 4) if n else 0.0) for k, v in contagem.items()}
    trechos_ia = _trechos(validos, IA)
    maior_trecho = max((t["frames"] for t in trechos_ia), default=0)
    trecho_relevante = maior_trecho >= regras["sequencia_minima"] and (
        n and maior_trecho / n >= regras["fracao_trecho"]
    )

    motivos = []
    if n < regras["min_frames_validos"]:
        resultado = INCONCLUSIVO
        motivos.append(
            f"só {n} frame(s) analisável(is); o mínimo é {regras['min_frames_validos']}"
            + (f" ({len(com_erro)} com erro)" if com_erro else "")
            + (f" ({len(fora)} fora de domínio)" if fora else "")
        )
    elif fracoes[IA] >= regras["fracao_ia"]:
        resultado = IA
        motivos.append(f"{fracoes[IA]:.0%} dos frames com indício de IA")
    elif trecho_relevante:
        resultado = IA
        t = max(trechos_ia, key=lambda t: t["frames"])
        motivos.append(f"trecho contínuo com indício de IA entre {t['inicio_s']:.1f}s e {t['fim_s']:.1f}s")
    elif fracoes[REAL] >= regras["fracao_real"]:
        resultado = REAL
        if contagem[IA]:
            motivos.append(f"{contagem[IA]} frame(s) isolado(s) com indício de IA, sem formar trecho")
    else:
        resultado = INCONCLUSIVO
        motivos.append(
            f"frames divididos: {fracoes[REAL]:.0%} real, {fracoes[IA]:.0%} IA, "
            f"{fracoes[INCONCLUSIVO]:.0%} inconclusivo"
        )

    return {
        "resultado": resultado,
        "inconclusivo": resultado == INCONCLUSIVO,
        "motivos": motivos,
        "frames_total": len(frames),
        "frames_validos": n,
        "frames_com_erro": len(com_erro),
        "frames_fora_de_dominio": len(fora),
        "contagem": contagem,
        "fracoes": fracoes,
        "probabilidade_ia": estatisticas,
        "trechos_ia": trechos_ia,
        "regras": regras,
    }


def combinar_visual(visual, trajetoria, regras=None):
    """Junta o voto dos frames com a analise de movimento (aida_video.trajetoria).

    IA pelos frames continua valendo sozinho (quase nunca erra em video real).
    Fora isso decide a trajetoria: acima da faixa IA, abaixo REAL, dentro dela
    INCONCLUSIVO. Sem trajetoria disponivel o voto dos frames fica como esta."""
    if not trajetoria or not trajetoria.get("disponivel"):
        return visual
    regras = {**REGRAS_PADRAO, **(regras or {})}
    baixo, alto = regras["trajetoria_faixa_inconclusiva"]
    prob = trajetoria["probabilidade_ia"]
    base = "movimento entre frames" + (" + probabilidade do Core" if trajetoria.get("usa_core") else "")
    motivo = f"{base}: {prob:.0%} de probabilidade de IA"
    saida = {**visual, "resultado_frames": visual["resultado"], "motivos": list(visual["motivos"])}
    if visual["resultado"] == IA:
        saida["motivos"].append(motivo)
        return saida
    if prob >= alto:
        resultado = IA
        motivo += " (movimento típico de vídeo gerado)"
    elif prob <= baixo:
        resultado = REAL
        motivo += " (movimento típico de câmera real)"
    else:
        resultado = INCONCLUSIVO
        motivo += f" (faixa de dúvida {baixo:.0%}-{alto:.0%})"
    saida["resultado"] = resultado
    saida["inconclusivo"] = resultado == INCONCLUSIVO
    saida["motivos"] = [motivo] + saida["motivos"]
    return saida


def combinar(visual, audio, regras=None):
    """Conclusao do video a partir da parte visual e (se houver) do audio.

    O audio (aida_audio treinado com as trilhas dos videos) tem FP baixo mas
    detecta so metade da IA; a imagem (frames + movimento) detecta mais, com
    ~6% de FP. Por isso o audio ajuda sem poder derrubar um video real sozinho:

    - imagem IA -> IA;
    - imagem INCONCLUSIVA -> o audio decide, se for conclusivo;
    - imagem REAL e audio IA com prob >= `audio_ia_forte` -> IA (voz sintetica
      sobre imagem real, ex.: voz clonada);
    - imagem REAL e audio IA mais fraco -> INCONCLUSIVO (os dois discordam).

    Medido fora da amostra (336 videos, gerador de fora): FP igual ao da imagem
    sozinha (6,0%), IA detectada de 73% para 78%, inconclusivos de 14% para 6%.
    """
    regras = {**REGRAS_PADRAO, **(regras or {})}
    motivos = []
    resultado_audio = audio.get("resultado") if audio else None
    prob_audio = audio.get("probabilidade_ia") if audio else None
    audio_forte = resultado_audio == IA and (prob_audio is None or prob_audio >= regras["audio_ia_forte"])
    movimento = [m for m in visual["motivos"] if m.startswith("movimento")]

    if visual["resultado"] == IA:
        resultado = IA
        motivos.append("indício de IA na imagem")
        motivos.extend(movimento)
        if resultado_audio == IA:
            motivos.append("indício de IA no áudio")
    elif visual["resultado"] == REAL:
        if audio_forte:
            resultado = IA
            motivos.append("indício forte de IA no áudio (voz sintética sobre imagem sem indício)")
        elif resultado_audio == IA:
            resultado = INCONCLUSIVO
            motivos.append("imagem sem indício de IA, mas o áudio tem indício de IA: os dois discordam")
            motivos.extend(movimento)
        else:
            resultado = REAL
            motivos.extend(movimento)
            if resultado_audio in (None, INCONCLUSIVO):
                motivos.append("conclusão baseada só na imagem; o áudio não foi avaliado de forma conclusiva")
            else:
                motivos.append("imagem e áudio sem indício de IA")
    else:
        if resultado_audio in (IA, REAL):
            resultado = resultado_audio
            motivos.append(
                "imagem inconclusiva; decidido pelo áudio ("
                + ("indício de IA na voz/som" if resultado_audio == IA else "áudio sem indício de IA")
                + ")"
            )
        else:
            resultado = INCONCLUSIVO
        motivos.extend(visual["motivos"])
    return {"resultado": resultado, "inconclusivo": resultado == INCONCLUSIVO, "motivos": motivos}
