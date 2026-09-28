"""Testes da avaliacao em lote (aida_video/avaliar_lote.py)."""

from __future__ import annotations

import json

import pytest

from aida_video.agregacao import IA, INCONCLUSIVO, REAL
from aida_video.analisadores import AnalisadorFixo
from aida_video.avaliar_lote import (
    _auc, analisar_lote, calibrar, carregar_relatorios, gravar_csvs, listar_videos, main, metricas,
)
from conftest import gerar_video

FRAME_REAL = {"resultado": REAL, "probabilidade_ia": 0.1, "fora_de_dominio": False}
FRAME_IA = {"resultado": IA, "probabilidade_ia": 0.9, "fora_de_dominio": False}


@pytest.fixture
def lote(tmp_path):
    raiz = tmp_path / "videos"
    (raiz / "reais").mkdir(parents=True)
    (raiz / "ia").mkdir()
    gerar_video(raiz / "reais" / "real_1.mp4", com_audio=False)
    gerar_video(raiz / "reais" / "real_2.mov", com_audio=False)
    gerar_video(raiz / "ia" / "gerado_1.mp4", com_audio=False)
    (raiz / "ia" / "quebrado.mp4").write_bytes(b"\x00" * 100)
    (raiz / "ia" / "notas.txt").write_text("ignorado")
    return raiz


def test_listar_videos_usa_pasta_como_rotulo(lote):
    itens = listar_videos(lote)
    nomes = {(v.name, r) for v, r, _ in itens}
    assert nomes == {("real_1.mp4", REAL), ("real_2.mov", REAL), ("gerado_1.mp4", IA), ("quebrado.mp4", IA)}


def test_listar_videos_sem_subpastas(tmp_path):
    with pytest.raises(FileNotFoundError, match="reais"):
        listar_videos(tmp_path)


def test_lote_completo_retoma_e_mede(lote, tmp_path, monkeypatch):
    import aida_video.avaliar_lote as mod

    saida = tmp_path / "saida"
    chamadas = []
    original = mod.analisar_video

    def analisar_com_rotulo(video, analisador=None, **kw):
        chamadas.append(video.name)
        pasta = video.parent.name
        return original(video, analisador=AnalisadorFixo([FRAME_IA if pasta == "ia" else FRAME_REAL]), **kw)

    monkeypatch.setattr(mod, "analisar_video", analisar_com_rotulo)
    avisos = []
    analisar_lote(lote, saida, analisador=object(), avisar=avisos.append)
    assert sorted(chamadas) == ["gerado_1.mp4", "quebrado.mp4", "real_1.mp4", "real_2.mov"]
    assert len(list((saida / "relatorios").glob("*.json"))) == 4
    assert not list(saida.rglob("*.png"))  # frames 4K nao sao guardados

    # Segunda rodada: tudo pulado.
    chamadas.clear()
    analisar_lote(lote, saida, analisador=object(), avisar=avisos.append)
    assert chamadas == []

    relatorios = carregar_relatorios(saida)
    m = metricas(relatorios)
    assert m["videos"] == 3  # o quebrado fica fora das metricas
    assert m["matriz"][REAL][REAL] == 2 and m["matriz"][IA][IA] == 1
    assert m["acuracia_decididos"] == 1.0 and m["falsos_positivos"] == 0
    assert m["auc_frames"] == 1.0

    gravar_csvs(relatorios, saida)
    resumo = (saida / "resumo_videos.csv").read_text(encoding="utf-8-sig").splitlines()
    assert len(resumo) == 5
    assert any("quebrado.mp4" in linha and "Não foi possível" in linha for linha in resumo)
    assert (saida / "frames.csv").is_file()


def _relatorio(rotulo, resultados):
    frames = [
        {"tempo_s": float(i), "resultado": r, "probabilidade_ia": 0.9 if r == IA else 0.1, "fora_de_dominio": False}
        for i, r in enumerate(resultados)
    ]
    from aida_video.agregacao import agregar

    return {"video": "v", "rotulo": rotulo, "frames": frames, "visual": agregar(frames), "audio": None}


def test_calibracao_prefere_menos_falsos_positivos():
    relatorios = [
        _relatorio(REAL, [REAL] * 6 + [IA] * 3 + [REAL]),  # real com trecho IA falso
        _relatorio(IA, [IA] * 4 + [REAL] * 6),
        _relatorio(REAL, [REAL] * 10),
    ]
    padrao = metricas(relatorios)
    assert padrao["falsos_positivos"] == 1
    melhor = calibrar(relatorios)[0]
    assert melhor["falsos_positivos"] == 0
    assert melhor["matriz"][IA][IA] == 1


def test_auc():
    assert _auc([0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9]) == 1.0
    assert _auc([0, 1], [0.5, 0.5]) == 0.5
    assert _auc([1, 1], [0.2, 0.3]) is None


def test_cli_so_calibrar_sem_relatorios(tmp_path, capsys):
    assert main([str(tmp_path), "--saida", str(tmp_path / "s"), "--so-calibrar"]) == 2


def test_cli_so_calibrar(tmp_path, capsys):
    saida = tmp_path / "s"
    (saida / "relatorios").mkdir(parents=True)
    for i, rel in enumerate([_relatorio(REAL, [REAL] * 5), _relatorio(IA, [IA] * 5)]):
        rel["metadados"] = {"largura_exibida": 1, "altura_exibida": 1}
        rel["resultado"] = rel["visual"]["resultado"]
        (saida / "relatorios" / f"{i}.json").write_text(json.dumps(rel), encoding="utf-8")
    assert main([str(tmp_path), "--saida", str(saida), "--so-calibrar"]) == 0
    saida_texto = capsys.readouterr().out
    assert "acurácia nos decididos: 1.0" in saida_texto
    assert (saida / "calibracao.json").is_file()
