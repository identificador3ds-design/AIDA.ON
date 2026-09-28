"""Testes da padronizacao de videos (rodada de controle da avaliacao em lote)."""

from __future__ import annotations

import av
import pytest

from aida_video.padronizar import _dimensoes, padronizar_pasta, padronizar_video
from conftest import gerar_video


def _formato(caminho):
    with av.open(str(caminho)) as c:
        v = c.streams.video[0]
        return {
            "largura": v.codec_context.width,
            "altura": v.codec_context.height,
            "codec": v.codec_context.name,
            "duracao": c.duration / 1_000_000,
            "fps": float(v.average_rate),
            "audio": bool(c.streams.audio),
        }


def test_reduz_corta_e_mantem_audio(tmp_path):
    origem = gerar_video(tmp_path / "grande.mp4", tamanho=(1280, 720), segundos_por_cena=4.0)  # 12 s
    saida = padronizar_video(origem, tmp_path / "p.mp4", lado=640, max_s=5)
    f = _formato(saida)
    assert (f["largura"], f["altura"]) == (640, 360)
    assert f["codec"] == "h264"
    assert f["duracao"] == pytest.approx(5.0, abs=0.3)
    assert f["audio"]


def test_nao_amplia_video_pequeno(tmp_path):
    origem = gerar_video(tmp_path / "pequeno.mp4", tamanho=(320, 240), com_audio=False)
    f = _formato(padronizar_video(origem, tmp_path / "p.mp4", lado=854))
    assert (f["largura"], f["altura"]) == (320, 240)
    assert not f["audio"]


def test_limita_fps(tmp_path):
    origem = gerar_video(tmp_path / "rapido.mp4", fps=50, com_audio=False, cenas=((0, 0, 255),))
    f = _formato(padronizar_video(origem, tmp_path / "p.mp4", fps_max=25))
    assert f["fps"] == pytest.approx(25, abs=0.5)
    assert f["duracao"] == pytest.approx(2.0, abs=0.2)


@pytest.mark.parametrize(
    "largura, altura, esperado",
    [(3840, 2160, (854, 480)), (2160, 3840, (480, 854)), (101, 51, (100, 50)), (640, 360, (640, 360))],
)
def test_dimensoes_pares_e_proporcionais(largura, altura, esperado):
    assert _dimensoes(largura, altura, 854) == esperado


def test_pasta_espelha_rotulos_e_pula_feitos(tmp_path):
    origem = tmp_path / "videos"
    gerar_video((origem / "reais").mkdir(parents=True) or origem / "reais" / "a.mov", com_audio=False)
    gerar_video((origem / "ia").mkdir() or origem / "ia" / "b.mp4", com_audio=False)
    (origem / "ia" / "quebrado.mp4").write_bytes(b"\x00" * 64)
    avisos = []
    falhas = padronizar_pasta(origem, tmp_path / "saida", avisar=avisos.append)
    assert (tmp_path / "saida" / "reais" / "a.mp4").is_file()
    assert (tmp_path / "saida" / "ia" / "b.mp4").is_file()
    assert [v.name for v, _ in falhas] == ["quebrado.mp4"]
    assert not (tmp_path / "saida" / "ia" / "quebrado.mp4").exists()

    avisos.clear()
    padronizar_pasta(origem, tmp_path / "saida", avisar=avisos.append)
    assert len(avisos) == 1  # so o quebrado e tentado de novo
