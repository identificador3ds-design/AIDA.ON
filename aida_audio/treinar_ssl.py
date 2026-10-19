"""Treina o AIDA Audio v2 a partir dos embeddings XLS-R ja calculados.

Entradas: os .npz gravados por ``experimento_ssl.py`` (PT: MLS x MLAAD; garystafford;
videos reais da equipe) e, opcionalmente, embeddings de reais extras (ex.: FLEURS
pt_br) com a mesma representacao.

1. **Avaliacao honesta** (nada do teste no treino): treina com PT + metade dos videos
   reais (por video) + 3 TTS comerciais (Polly, Kokoro, Luvvoice) + metade do YouTube
   + metade do FLEURS; testa nos outros videos, nos TTS comerciais NUNCA vistos
   (ElevenLabs, Hume, Speechify), na outra metade do YouTube e do FLEURS.
2. **Politica**: limiar alto = FPR 3% nas reais fora da amostra (validacao cruzada);
   limiar baixo = no maximo 3% das IA ditas REAL. Entre os dois: INCONCLUSIVO.
3. **Modelo final** com todos os dados, gravado em ``modelos/modelo_audio_ssl.joblib``.

    python -m aida_audio.treinar_ssl <experimento.npz> [--extra fleurs_emb.npz] [--saida relatorio.json]
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import numpy as np

from .modelo import ARQUIVO_MODELO_SSL
from .ssl import CAMADAS, MAX_JANELAS, REPO, SEGUNDOS

REP = "xlsr"
FPR_ALVO = 0.03
FNR_ALVO = 0.03


def _modelo():
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    return make_pipeline(StandardScaler(), LogisticRegression(C=0.5, max_iter=5000, class_weight="balanced"))


def carregar(npz, extras):
    d = np.load(npz, allow_pickle=True)
    X, y = d[REP], d["rotulo"].astype(int)
    fonte = d["fonte"].astype(str)
    grupo = d["grupo"].astype(str)
    for e in extras:
        x = np.load(e, allow_pickle=True)
        n = len(x[REP])
        nome = Path(e).stem.split("_")[0]
        X = np.vstack([X, x[REP]])
        y = np.concatenate([y, np.zeros(n, int)])
        fonte = np.concatenate([fonte, np.array([nome] * n)])
        grupo = np.concatenate([grupo, np.array([f"{nome}:{i // 4}" for i in range(n)])])
    return X, y, fonte, grupo


def _politica(y, p):
    reais, ias = np.sort(p[y == 0]), np.sort(p[y == 1])
    alto = float(reais[min(len(reais) - 1, int(np.ceil((1 - FPR_ALVO) * len(reais))))])
    baixo = float(min(ias[int(np.floor(FNR_ALVO * len(ias)))], alto))
    return baixo, alto


def _taxas(y, p, baixo, alto):
    out = {"n": int(len(y))}
    if (y == 0).any():
        r = p[y == 0]
        out.update(real_ok=round(float(np.mean(r <= baixo)), 3), real_dito_ia=round(float(np.mean(r >= alto)), 3),
                   real_inconclusivo=round(float(np.mean((r > baixo) & (r < alto))), 3))
    if (y == 1).any():
        i = p[y == 1]
        out.update(ia_detectada=round(float(np.mean(i >= alto)), 3), ia_dita_real=round(float(np.mean(i <= baixo)), 3),
                   ia_inconclusiva=round(float(np.mean((i > baixo) & (i < alto))), 3))
    if len(set(y)) == 2:
        from sklearn.metrics import roc_auc_score
        out["auc"] = round(float(roc_auc_score(y, p)), 4)
    return out


def _oof(X, y, grupos, k=5):
    """Probabilidades fora da amostra, sem repetir grupo entre treino e validacao."""
    from sklearn.model_selection import StratifiedGroupKFold
    p = np.zeros(len(y))
    for tr, va in StratifiedGroupKFold(n_splits=k, shuffle=True, random_state=3).split(X, y, grupos):
        p[va] = _modelo().fit(X[tr], y[tr]).predict_proba(X[va])[:, 1]
    return p


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("npz", type=Path)
    ap.add_argument("--extra", type=Path, action="append", default=[])
    ap.add_argument("--saida", type=Path, default=None)
    ap.add_argument("--destino", type=Path, default=ARQUIVO_MODELO_SSL)
    a = ap.parse_args(argv)

    X, y, fonte, grupo = carregar(a.npz, a.extra)
    # Fora do PT o grupo e a fonte inteira ("celular", "gary:youtube"): na validacao
    # cruzada isso tiraria um CANAL inteiro do treino de cada dobra e empurraria o
    # limiar para 1,0. Cada video do celular e um item proprio; no resto, por item.
    grupo_cv = np.array([g if f == "pt" else f"{f}:{i}" for i, (g, f) in enumerate(zip(grupo, fonte))])
    ger = np.array([g.split(":")[-1] for g in grupo])
    rnd = np.random.RandomState(5)

    def metade(idx):
        idx = idx.copy()
        rnd.shuffle(idx)
        return idx[: len(idx) // 2], idx[len(idx) // 2:]

    pt = np.where(fonte == "pt")[0]
    cel_tr, cel_te = metade(np.where(fonte == "celular")[0])
    yt_tr, yt_te = metade(np.where((fonte == "gary") & (ger == "youtube"))[0])
    com_tr = np.where((fonte == "gary") & np.isin(ger, ["po", "hg", "lv"]))[0]
    com_te = np.where((fonte == "gary") & np.isin(ger, ["el", "hu", "sp"]))[0]
    ext_tr, ext_te = [], []
    for nome in sorted(set(fonte) - {"pt", "celular", "gary"}):
        t, v = metade(np.where(fonte == nome)[0])
        ext_tr.append(t)
        ext_te.append(v)
    tr = np.concatenate([pt, cel_tr, yt_tr, com_tr, *ext_tr])

    # Politica escolhida fora da amostra, so no conjunto de treino.
    p_oof = _oof(X[tr], y[tr], grupo_cv[tr])
    baixo, alto = _politica(y[tr], p_oof)
    m = _modelo().fit(X[tr], y[tr])
    testes = {"celular_reais_novos": cel_te, "tts_comercial_nunca_visto(el,hu,sp)": com_te,
              "youtube_reais_metade": yt_te}
    for nome, idx in zip(sorted(set(fonte) - {"pt", "celular", "gary"}), ext_te):
        testes[f"{nome}_reais_metade"] = idx
    relatorio = {"politica_avaliacao": {"baixo": round(baixo, 4), "alto": round(alto, 4)},
                 "validacao_oof_treino": _taxas(y[tr], p_oof, baixo, alto),
                 "testes": {k: _taxas(y[i], m.predict_proba(X[i])[:, 1], baixo, alto) for k, i in testes.items()}}
    print(json.dumps(relatorio, ensure_ascii=False, indent=2))

    # Modelo final: tudo; politica pela validacao cruzada em tudo.
    p_tudo = _oof(X, y, grupo_cv)
    baixo, alto = _politica(y, p_tudo)
    final = _modelo().fit(X, y)
    limiar = (baixo + alto) / 2
    pacote = {
        "tipo": "ssl", "nome": "xlsr300m_logreg", "modelo": final, "colunas": [],
        "backbone": REPO, "camadas": list(CAMADAS), "segundos_janela": SEGUNDOS, "max_janelas": MAX_JANELAS,
        "limiar": limiar, "faixa_inconclusiva": [baixo, alto],
        "treinado_em": datetime.now().isoformat(timespec="seconds"),
        "n_treino": {"reais": int((y == 0).sum()), "ia": int((y == 1).sum())},
        "fontes": sorted(set(fonte)),
        "validacao_oof_tudo": _taxas(y, p_tudo, baixo, alto),
    }
    import joblib
    a.destino.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pacote, a.destino)
    relatorio["modelo_final"] = {k: v for k, v in pacote.items() if k not in ("modelo",)}
    if a.saida:
        a.saida.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[treinar_ssl] modelo gravado em {a.destino} (faixa {baixo:.3f}-{alto:.3f})")


if __name__ == "__main__":
    main()
