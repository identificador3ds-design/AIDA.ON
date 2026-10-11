"""Vale trocar as caracteristicas classicas por embeddings de fala pre-treinados?

Experimento controlado (11/10/2026). Mesmos clipes, mesma cabeca (regressao
logistica), tres representacoes:

* ``classicas``  — ``extrair_caracteristicas`` (o que o AIDA Audio usa hoje);
* ``wavlm``      — microsoft/wavlm-base-plus (95 M), media das camadas 3-9;
* ``xlsr``       — facebook/wav2vec2-xls-r-300m (300 M, 128 linguas), camadas 5-12.

Embeddings auto-supervisionados (SSL) sao a base dos detectores que mais
generalizam no ASVspoof 5 e no In-the-Wild: as camadas intermediarias carregam
detalhe acustico fino (fase, ruido de fundo, transicoes) que o TTS nao imita.

Protocolos (nada do teste aparece no treino):

1. **PT, sistemas e locutores novos** — treino em parte dos 16 sistemas TTS do
   MLAAD-pt e dos locutores do MLS-pt; teste nos sistemas/locutores restantes.
2. **Externo, TTS comercial em ingles** — treina em todo o PT e testa no
   garystafford/deepfake-audio-detection v4 (ElevenLabs, Hume, Speechify, Polly,
   Kokoro, Luvvoice x YouTube). Lingua, canal e sistemas nunca vistos.
3. **Falso positivo em celular** — o mesmo modelo nos 167 videos reais da equipe.

    python -m aida_audio.experimento_ssl <pasta_dados> <saida.json> [--por-sistema 80]

<pasta_dados>: mlaad_pt/**/<sistema>/*.wav, mls_pt/<locutor>/*, gary/data/*.parquet;
videos reais em G:/Meu Drive/TCC/videos_teste/reais.
"""

from __future__ import annotations

import argparse
import io
import json
import random
import sys
import time
from pathlib import Path

import numpy as np

from .caracteristicas import extrair_caracteristicas
from .carregar import AudioAusente, carregar_audio

SEGUNDOS = 6.0
TAXA = 16000
EXT = {".wav", ".mp3", ".flac", ".m4a", ".ogg", ".opus", ".mp4", ".mov"}
BACKBONES = {
    "wavlm": ("microsoft/wavlm-base-plus", range(3, 10)),
    "xlsr": ("facebook/wav2vec2-xls-r-300m", range(5, 13)),
}
VIDEOS_REAIS = Path("G:/Meu Drive/TCC/videos_teste/reais")


def _recorte(sinal):
    n = int(SEGUNDOS * TAXA)
    if sinal.size <= n:
        return sinal
    i = (sinal.size - n) // 2                    # meio do clipe: evita silencio de borda
    return sinal[i:i + n]


def listar(pasta: Path, por_sistema: int, semente=7):
    rnd = random.Random(semente)
    itens = []
    sistemas = {}
    for f in (pasta / "mlaad_pt").rglob("*"):
        if f.suffix.lower() in EXT:
            sistemas.setdefault(f.parent.name, []).append(f)
    for sist, fs in sorted(sistemas.items()):
        rnd.shuffle(fs)
        itens += [dict(fonte="pt", origem=f, rotulo=1, grupo=f"tts:{sist}") for f in fs[:por_sistema]]
    reais = [f for f in (pasta / "mls_pt").rglob("*") if f.suffix.lower() in EXT]
    rnd.shuffle(reais)
    n_ia = sum(1 for i in itens if i["rotulo"] == 1)
    itens += [dict(fonte="pt", origem=f, rotulo=0, grupo=f"mls:{f.parent.name}") for f in reais[:n_ia]]

    import pandas as pd
    for pq in sorted((pasta / "gary").rglob("*.parquet")):
        df = pd.read_parquet(pq)
        for _, r in df.iterrows():
            nome = Path(r["audio"].get("path") or "x").name
            gerador = "youtube" if int(r["label"]) == 0 else nome.split("_")[0]
            itens.append(dict(fonte="gary", origem=r["audio"]["bytes"], rotulo=int(r["label"]),
                              grupo=f"gary:{gerador}", nome=nome))
    for f in sorted(VIDEOS_REAIS.glob("*")):
        if f.suffix.lower() in EXT:
            itens.append(dict(fonte="celular", origem=f, rotulo=0, grupo="celular"))
    return itens


def carregar(item):
    origem = item["origem"]
    if isinstance(origem, (bytes, bytearray)):
        import soundfile as sf
        sinal, taxa = sf.read(io.BytesIO(origem), dtype="float32", always_2d=True)
        sinal = sinal.mean(axis=1)
        if taxa != TAXA:
            from math import gcd

            from scipy.signal import resample_poly
            d = gcd(int(taxa), TAXA)
            sinal = resample_poly(sinal, TAXA // d, int(taxa) // d)
        return _recorte(sinal.astype(np.float32))
    sinal, _ = carregar_audio(origem, TAXA, max_segundos=60)
    return _recorte(sinal)


class Embedder:
    def __init__(self, nome):
        import torch
        from transformers import AutoFeatureExtractor, AutoModel
        repo, self.camadas = BACKBONES[nome]
        self.torch = torch
        self.ext = AutoFeatureExtractor.from_pretrained(repo)
        self.modelo = AutoModel.from_pretrained(repo).eval()
        torch.set_num_threads(max(1, (torch.get_num_threads() or 4)))

    def __call__(self, sinal):
        t = self.torch
        with t.inference_mode():
            x = self.ext(sinal, sampling_rate=TAXA, return_tensors="pt")
            saida = self.modelo(**x, output_hidden_states=True)
            hs = t.stack([saida.hidden_states[i] for i in self.camadas])   # camadas x 1 x T x D
            media = hs.mean(dim=(0, 2)).squeeze(0)
            desvio = hs.std(dim=2).mean(dim=0).squeeze(0)
            return t.cat([media, desvio]).numpy().astype(np.float32)


def extrair(itens, representacoes):
    embs = {r: Embedder(r) for r in representacoes if r in BACKBONES}
    X = {r: [] for r in representacoes}
    ok = []
    t0 = time.time()
    for k, it in enumerate(itens):
        try:
            sinal = carregar(it)
            if sinal.size < TAXA:                # < 1 s de audio
                continue
            linha = {}
            for r in representacoes:
                if r == "classicas":
                    c, _ = extrair_caracteristicas(sinal, TAXA)
                    linha[r] = np.array([c[k2] for k2 in sorted(c)], np.float32)
                else:
                    linha[r] = embs[r](sinal)
        except (AudioAusente, ValueError, RuntimeError) as exc:
            print(f"  pulado {it.get('nome') or it['origem']}: {type(exc).__name__}", flush=True)
            continue
        for r in representacoes:
            X[r].append(linha[r])
        ok.append(it)
        if (k + 1) % 100 == 0:
            print(f"[ssl] {k + 1}/{len(itens)} ({time.time() - t0:.0f}s)", flush=True)
    return {r: np.vstack(v) for r, v in X.items()}, ok


def _metricas(y, s, limiar):
    from sklearn.metrics import roc_auc_score
    from .modelo import calcular_eer
    out = {"n": int(len(y))}
    if len(set(y)) == 2:
        out["auc"] = round(float(roc_auc_score(y, s)), 4)
        out["eer"] = round(calcular_eer(y, s)[0], 4)
    y = np.asarray(y)
    if (y == 0).any():
        out["falso_positivo"] = round(float(np.mean(s[y == 0] >= limiar)), 4)
    if (y == 1).any():
        out["ia_detectada"] = round(float(np.mean(s[y == 1] >= limiar)), 4)
    return out


def avaliar(X, itens):
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    fonte = np.array([i["fonte"] for i in itens])
    y = np.array([i["rotulo"] for i in itens])
    grupo = np.array([i["grupo"] for i in itens])
    pt = fonte == "pt"
    grupos_pt = sorted(set(grupo[pt]))
    rnd = random.Random(11)
    teste_g = set(rnd.sample([g for g in grupos_pt if g.startswith("tts:")], 5)
                  + rnd.sample([g for g in grupos_pt if g.startswith("mls:")], 12))
    te = pt & np.isin(grupo, list(teste_g))
    tr = pt & ~te
    resultado = {"grupos_teste_pt": sorted(teste_g)}
    for nome, M in X.items():
        def modelo():
            return make_pipeline(StandardScaler(), LogisticRegression(C=0.5, max_iter=4000, class_weight="balanced"))

        # Limiar: FPR 5% nas reais do proprio treino (validacao interna simples).
        m1 = modelo().fit(M[tr], y[tr])
        s_tr = m1.predict_proba(M[tr])[:, 1]
        lim1 = float(np.quantile(s_tr[y[tr] == 0], 0.95))
        r = {"pt_sistemas_novos": _metricas(y[te], m1.predict_proba(M[te])[:, 1], lim1)}

        m2 = modelo().fit(M[pt], y[pt])
        s_pt = m2.predict_proba(M[pt])[:, 1]
        lim2 = float(np.quantile(s_pt[y[pt] == 0], 0.95))
        g = fonte == "gary"
        if g.any():
            s_g = m2.predict_proba(M[g])[:, 1]
            r["externo_tts_comercial"] = _metricas(y[g], s_g, lim2)
            r["externo_por_gerador"] = {
                ger.split(":")[1]: round(float(np.mean(s_g[grupo[g] == ger] >= lim2)), 3)
                for ger in sorted(set(grupo[g]))}
        c = fonte == "celular"
        if c.any():
            r["celular_reais"] = _metricas(y[c], m2.predict_proba(M[c])[:, 1], lim2)
        resultado[nome] = r
        print(nome, json.dumps(r, ensure_ascii=False), flush=True)
    return resultado


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("pasta", type=Path)
    ap.add_argument("saida", type=Path)
    ap.add_argument("--por-sistema", type=int, default=80)
    ap.add_argument("--representacoes", default="classicas,wavlm,xlsr")
    a = ap.parse_args(argv)
    itens = listar(a.pasta, a.por_sistema)
    print(f"[ssl] {len(itens)} clipes", flush=True)
    reps = a.representacoes.split(",")
    cache = a.saida.with_suffix(".npz")
    X, ok = extrair(itens, reps)
    np.savez(cache, **X, rotulo=[i["rotulo"] for i in ok], fonte=[i["fonte"] for i in ok],
             grupo=[i["grupo"] for i in ok])
    res = avaliar(X, ok)
    res["n_clipes"] = len(ok)
    a.saida.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
