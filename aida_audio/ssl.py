"""AIDA Audio v2: embeddings de fala auto-supervisionados (XLS-R) + regressao logistica.

Por que (experimento de 11/10/2026, ``aida_audio/experimento_ssl.py``): com as
caracteristicas classicas o AUC em TTS comercial nunca visto (ElevenLabs, Hume,
Speechify...) era 0,60; com o XLS-R-300m, 0,97-0,99. As camadas intermediarias do
modelo carregam detalhe acustico fino que o sintetizador nao imita.

Inferencia: ate ``MAX_JANELAS`` janelas de ``SEGUNDOS`` espalhadas pelo audio; cada
janela vira [media, desvio] das camadas 5-12 (2048 numeros), o classificador da
uma probabilidade por janela e a resposta e a media. O backbone (~1,2 GB) e
carregado uma vez por processo.
"""

from __future__ import annotations

import threading

import numpy as np

REPO = "facebook/wav2vec2-xls-r-300m"
CAMADAS = tuple(range(5, 13))
SEGUNDOS = 6.0
MAX_JANELAS = 4
TAXA = 16000

_trava = threading.Lock()
_backbone = None


def _carregar():
    global _backbone
    with _trava:
        if _backbone is None:
            import torch
            from transformers import AutoFeatureExtractor, AutoModel
            ext = AutoFeatureExtractor.from_pretrained(REPO)
            modelo = AutoModel.from_pretrained(REPO).eval()
            _backbone = (torch, ext, modelo)
    return _backbone


def janelas(sinal, taxa=TAXA, segundos=SEGUNDOS, maximo=MAX_JANELAS):
    """Ate `maximo` trechos de `segundos`, espalhados (o meio do audio primeiro)."""
    n = int(segundos * taxa)
    if sinal.size <= n:
        return [sinal]
    inicios = np.linspace(0, sinal.size - n, num=min(maximo, max(1, sinal.size // n))).astype(int)
    return [sinal[i:i + n] for i in inicios]


def embedding(trecho, camadas=CAMADAS):
    torch, ext, modelo = _carregar()
    with torch.inference_mode():
        x = ext(trecho, sampling_rate=TAXA, return_tensors="pt")
        saida = modelo(**x, output_hidden_states=True)
        hs = torch.stack([saida.hidden_states[i] for i in camadas])
        media = hs.mean(dim=(0, 2)).squeeze(0)
        desvio = hs.std(dim=2).mean(dim=0).squeeze(0)
        return torch.cat([media, desvio]).numpy().astype(np.float32)


def probabilidade_ia(amostras, taxa, pacote):
    """Media das probabilidades por janela. `pacote` vem de treinar_ssl.py."""
    if taxa != TAXA:
        raise ValueError(f"O AIDA Audio v2 espera {TAXA} Hz (recebeu {taxa}).")
    sinal = np.asarray(amostras, dtype=np.float32).reshape(-1)
    X = np.vstack([embedding(j, tuple(pacote.get("camadas", CAMADAS))) for j in janelas(sinal)])
    return float(pacote["modelo"].predict_proba(X)[:, 1].mean()), len(X)
