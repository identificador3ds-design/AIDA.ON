"""Testes da validacao honesta (aida_video/validacao.py) e da trajetoria (aida_video/trajetoria.py)."""

from __future__ import annotations

import json

import numpy as np
import pytest

from aida_video.agregacao import IA, REAL
from aida_video.avaliar_lote import _auc
from aida_video.trajetoria import (
    NOMES_CARACTERISTICAS, amostrar_janelas, caracteristicas_trajetoria, passo_de_frames,
)
from aida_video.validacao import (
    GERADOR_REAL, bootstrap, gerador_de, main, resumir, validacao_cruzada_por_gerador,
)
from conftest import gerar_video


def _frame(rotulo, t):
    return {"tempo_s": t, "resultado": rotulo, "probabilidade_ia": 0.9 if rotulo == IA else 0.1,
            "fora_de_dominio": False}


def _rel(nome, rotulo, votos):
    return {"video": nome, "rotulo": rotulo, "pasta": "ia" if rotulo == IA else "reais",
            "frames": [_frame(v, i * 0.5) for i, v in enumerate(votos)], "audio": None}


def _lote():
    rels = []
    for g in ("sora2", "veo31", "kling26"):
        for k in range(4):
            rels.append(_rel(f"{g}_{k:04x}.mp4", IA, [IA] * 4 + [REAL] * (k % 3)))
    for k in range(12):
        rels.append(_rel(f"IMG_{k}.MOV", REAL, [REAL] * 6))
    return rels


def test_auc_por_postos_igual_par_a_par():
    rng = np.random.default_rng(0)
    rot = list(rng.integers(0, 2, 200))
    sc = list(np.round(rng.random(200), 1))  # muitos empates de proposito
    pos = [s for r, s in zip(rot, sc) if r == 1]
    neg = [s for r, s in zip(rot, sc) if r == 0]
    esperado = sum((p > q) + 0.5 * (p == q) for p in pos for q in neg) / (len(pos) * len(neg))
    assert _auc(rot, sc) == pytest.approx(esperado)
    assert _auc([1, 1], [0.2, 0.3]) is None


def test_gerador_pelo_prefixo():
    assert gerador_de({"video": "sora2_0b27b8fb.mp4", "rotulo": IA}) == "sora2"
    assert gerador_de({"video": "semprefixo.mp4", "rotulo": IA}) == "desconhecido"
    assert gerador_de({"video": "IMG_1.MOV", "rotulo": REAL}) == GERADOR_REAL


def test_resumir_conta_fp_e_recall():
    pares = [(REAL, REAL), (REAL, IA), (IA, IA), (IA, "INCONCLUSIVO")]
    m = resumir(pares)
    assert m["falsos_positivos"] == 1
    assert m["taxa_falso_positivo"] == 0.5
    assert m["recall_ia"] == 0.5
    assert m["cobertura"] == 0.75


def test_bootstrap_ic_contem_o_ponto():
    pares = [(REAL, REAL)] * 30 + [(REAL, IA)] * 3 + [(IA, IA)] * 20 + [(IA, REAL)] * 10
    ic = bootstrap(pares, n=300)
    ponto = resumir(pares)
    for chave in ("acuracia_decididos", "recall_ia", "taxa_falso_positivo"):
        assert ic[chave][0] <= ponto[chave] <= ic[chave][1]


def test_cv_por_gerador_cobre_todos_os_videos_uma_vez():
    rels = _lote()
    cv = validacao_cruzada_por_gerador(rels)
    assert len(cv["pares"]) == len(rels)
    assert [r["gerador_fora"] for r in cv["rodadas"]] == ["kling26", "sora2", "veo31"]
    assert all(r["videos_ia"] == 4 for r in cv["rodadas"])


def test_cv_exige_dois_geradores():
    rels = [_rel("sora2_1.mp4", IA, [IA] * 4), _rel("IMG_1.MOV", REAL, [REAL] * 4)]
    with pytest.raises(ValueError, match="2 geradores"):
        validacao_cruzada_por_gerador(rels)


def test_main_grava_json(tmp_path, capsys):
    (tmp_path / "relatorios").mkdir()
    for i, rel in enumerate(_lote()):
        (tmp_path / "relatorios" / f"{i}.json").write_text(json.dumps(rel), encoding="utf-8")
    assert main([str(tmp_path), "--bootstrap", "50"]) == 0
    res = json.loads((tmp_path / "validacao.json").read_text(encoding="utf-8"))
    assert {"regras_atuais", "melhor_da_grade_otimista", "grade_por_gerador_fora"} <= set(res)
    assert "honesto" in capsys.readouterr().out


def test_main_sem_relatorios(tmp_path):
    assert main([str(tmp_path)]) == 2


# ----------------------------------------------------------------- trajetoria


def test_passo_inteiro_sem_frame_repetido():
    assert [passo_de_frames(f) for f in (60, 30, 24, 16, 10, 8)] == [8, 4, 3, 2, 1, 1]
    assert passo_de_frames(None) == 4


def test_trajetoria_reta_tem_curvatura_zero():
    z = np.outer(np.arange(10), np.ones(5))  # pontos numa reta, passo constante
    f = caracteristicas_trajetoria(z)
    assert len(f) == len(NOMES_CARACTERISTICAS) == 21
    curv = f[7:13]
    assert np.allclose(curv, 0, atol=1e-5)
    assert np.allclose(f[:7], np.sqrt(5))


def test_trajetoria_zigue_zague_curva_mais():
    reta = caracteristicas_trajetoria(np.outer(np.arange(8), [1.0, 0.0]))
    zigue = caracteristicas_trajetoria(np.array([[i, i % 2] for i in range(8)], dtype=float))
    idx = NOMES_CARACTERISTICAS.index("curv_media")
    assert zigue[idx] > reta[idx] + 45


def test_trajetoria_curta_demais():
    with pytest.raises(ValueError):
        caracteristicas_trajetoria(np.zeros((2, 4)))


def test_amostrar_janelas_em_video_sintetico(tmp_path):
    video = gerar_video(tmp_path / "v.mp4", segundos_por_cena=4.0, fps=24, com_audio=False)
    janelas, info = amostrar_janelas(video, max_janelas=1)
    assert info["passo_frames"] == 3 and info["fps_efetivo"] == 8.0
    assert len(janelas) == 1 and janelas[0].shape == (24, 224, 224, 3)
    tres, _ = amostrar_janelas(video, max_janelas=3)  # 12 s a 8 fps = 96 amostras
    assert len(tres) == 3


def test_amostrar_janelas_video_curto_demais(tmp_path):
    video = gerar_video(tmp_path / "v.mp4", cenas=((0, 0, 255),), segundos_por_cena=0.5, fps=24, com_audio=False)
    janelas, info = amostrar_janelas(video)
    assert janelas == [] and info["amostras"] < 8


def test_avaliar_trajetoria_separa_e_mede_atalho():
    from aida_video.treinar_trajetoria import avaliar, treinar_final

    rng = np.random.default_rng(1)
    registros = []
    for g in ("sora2", "veo31", "wan26"):
        for k in range(8):
            registros.append({"video": f"{g}_{k}.mp4", "rotulo": IA, "pasta": "ia", "info": {"fps": 30.0},
                              "janelas": [list(rng.normal(1.0, 0.3, 21))]})
    for k in range(24):
        registros.append({"video": f"IMG_{k}.MOV", "rotulo": REAL, "pasta": "reais", "info": {"fps": 30.0},
                          "janelas": [list(rng.normal(-1.0, 0.3, 21))]})
    core = [{"video": r["video"], "pasta": r["pasta"], "rotulo": r["rotulo"],
             "frames": [{"probabilidade_ia": 0.5, "fora_de_dominio": False}]} for r in registros]
    res, p = avaliar(registros, core)
    assert res["trajetoria"]["auc"] > 0.95
    assert res["atalho_auc_so_fps"] == 0.5  # mesmo fps nas duas classes: sem atalho
    assert set(res["trajetoria_ia_detectada_por_gerador_fora"]) == {"sora2", "veo31", "wan26"}
    assert "fusao_trajetoria_mais_core" in res["comparacao_mesmos_videos"]
    assert not np.isnan(p).any()


def test_treinar_final_grava_modelo(tmp_path):
    import joblib

    from aida_video.treinar_trajetoria import treinar_final

    registros = [{"rotulo": IA if k % 2 else REAL, "janelas": [[float(k % 2)] * 21]} for k in range(10)]
    destino = treinar_final(registros, tmp_path / "m.joblib")
    pacote = joblib.load(destino)
    assert pacote["videos_treino"] == 10 and len(pacote["caracteristicas"]) == 21
