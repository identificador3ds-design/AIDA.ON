"""Testes do que foi adicionado ao AIDA Audio em 26/09/2026:
leitura de tags Latin-1, avaliar_externo, faixa inconclusiva no pacote e
treinar_com_videos (validacao deixando um gerador de fora)."""

from __future__ import annotations

import struct

import numpy as np
import pytest

from aida_audio import analisar_amostras, carregar_audio, extrair_caracteristicas, salvar_wav
from aida_audio import avaliar_externo
from aida_audio import treinar_com_videos as tcv

TAXA = 16000


def tom(freq=440.0, segundos=2.0, amplitude=0.3):
    t = np.arange(int(segundos * TAXA)) / TAXA
    return (amplitude * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def ruido(segundos=2.0, semente=0, amplitude=0.2):
    return (amplitude * np.random.default_rng(semente).standard_normal(int(segundos * TAXA))).astype(np.float32)


def wav_com_titulo_latin1(caminho, amostras):
    """WAV com um chunk LIST/INFO/INAM em Latin-1 ('Capitulo' com i agudo = 0xED),
    como as tags dos audiolivros do MLS. Nao e UTF-8 valido."""
    bruto = salvar_wav(caminho, amostras).read_bytes()
    titulo = b"Cap\xedtulo um\x00"
    if len(titulo) % 2:
        titulo += b"\x00"
    info = b"INFO" + b"INAM" + struct.pack("<I", len(titulo)) + titulo
    lista = b"LIST" + struct.pack("<I", len(info)) + info
    novo = bruto[:12] + lista + bruto[12:]
    novo = novo[:4] + struct.pack("<I", len(novo) - 8) + novo[8:]
    caminho.write_bytes(novo)
    return caminho


# ---------------------------------------------------------------- Latin-1


def test_tag_latin1_reproduz_o_problema_do_pyav(tmp_path):
    import av

    caminho = wav_com_titulo_latin1(tmp_path / "mls.wav", tom())
    with pytest.raises(UnicodeDecodeError):
        av.open(str(caminho))  # padrao "strict": era isso que pulava todos os reais


def test_tag_latin1_nao_impede_a_leitura(tmp_path):
    caminho = wav_com_titulo_latin1(tmp_path / "mls.wav", tom())
    amostras, taxa = carregar_audio(caminho)
    assert taxa == TAXA
    assert amostras.size == pytest.approx(2 * TAXA, abs=64)


# ---------------------------------------------------------------- modelo de mentira


class ModeloPlanura:
    """'IA' quando a planura espectral passa do corte (ruido e plano, tom nao)."""

    def __init__(self, corte):
        self.corte = corte

    def predict_proba(self, x):
        p = np.where(x[:, 0] > self.corte, 0.9, 0.1)
        return np.column_stack([1 - p, p])


@pytest.fixture
def pacote():
    t, _ = extrair_caracteristicas(tom(), TAXA)
    r, _ = extrair_caracteristicas(ruido(), TAXA)
    corte = float(np.sqrt(t["planura_media"] * r["planura_media"]))
    return {"modelo": ModeloPlanura(corte), "nome": "planura", "colunas": ["planura_media"], "limiar": 0.5}


# ---------------------------------------------------------------- faixa inconclusiva


def test_faixa_inconclusiva_do_pacote(pacote):
    # Ruido da 0,9: com limiar 0,95 e faixa [0,8; 0,95) fica INCONCLUSIVO.
    alto = {**pacote, "limiar": 0.95, "faixa_inconclusiva": (0.8, 0.95)}
    r = analisar_amostras(ruido(), TAXA, pacote_modelo=alto)
    assert r["resultado"] == "INCONCLUSIVO"
    assert r["probabilidade_ia"] == pytest.approx(0.9)
    # Faixa abaixo de 0,9: vira IA; o tom (0,1) fica REAL.
    baixo = {**pacote, "limiar": 0.7, "faixa_inconclusiva": (0.55, 0.7)}
    assert analisar_amostras(ruido(), TAXA, pacote_modelo=baixo)["resultado"] == "IA/MANIPULADA"
    assert analisar_amostras(tom(), TAXA, pacote_modelo=baixo)["resultado"] == "REAL"


def test_sem_faixa_usa_margem_simetrica(pacote):
    assert analisar_amostras(ruido(), TAXA, pacote_modelo=pacote)["resultado"] == "IA/MANIPULADA"
    perto = {**pacote, "limiar": 0.85}  # 0,9 esta a 0,05 do limiar (< 0,10)
    assert analisar_amostras(ruido(), TAXA, pacote_modelo=perto)["resultado"] == "INCONCLUSIVO"


# ---------------------------------------------------------------- avaliar_externo


@pytest.fixture
def pasta_videos(tmp_path, video_sem_audio):
    raiz = tmp_path / "videos"
    for i in range(4):
        salvar_wav(raiz / "reais" / f"IMG_{i}.wav", tom(300 + 50 * i))
    salvar_wav(raiz / "reais" / "IMG_ruidoso.wav", ruido(semente=7))  # vira falso positivo
    for i in range(2):
        salvar_wav(raiz / "ia" / f"sora2_{i}.wav", ruido(semente=i))
        salvar_wav(raiz / "ia" / f"veo31_{i}.wav", tom(500 + i))  # IA que escapa
    (raiz / "ia" / "wan26_mudo.mp4").write_bytes(video_sem_audio.read_bytes())
    (raiz / "ia" / "leiame.txt").write_text("ignorado")
    return raiz


def test_listar_gerador_pelo_prefixo(pasta_videos):
    itens = avaliar_externo.listar(pasta_videos)
    assert sorted({g for _, _, g in itens}) == ["real", "sora2", "veo31", "wan26"]
    assert len(itens) == 10


def test_avaliar_externo_resume_fp_e_deteccao(pasta_videos, pacote):
    linhas, resumo = avaliar_externo.avaliar(pasta_videos, pacote, avisar=lambda _: None)
    assert len(linhas) == 9  # o video mudo nao conta
    assert resumo["reais"] == 5 and resumo["ia"] == 4
    assert resumo["falso_positivo"] == pytest.approx(0.2)
    assert resumo["ia_detectada"] == pytest.approx(0.5)
    assert resumo["ia_detectada_por_gerador"] == {"sora2": 1.0, "veo31": 0.0}
    assert 0.0 <= resumo["auc"] <= 1.0


def test_avaliar_externo_main_sem_modelo(tmp_path):
    assert avaliar_externo.main([str(tmp_path), "--modelo", str(tmp_path / "nao_existe.joblib")]) == 2


def test_avaliar_externo_main_grava_saida(pasta_videos, pacote, tmp_path):
    import joblib

    caminho = tmp_path / "m.joblib"
    joblib.dump(pacote, caminho)
    saida = tmp_path / "saida"
    assert avaliar_externo.main([str(pasta_videos), "--modelo", str(caminho), "--saida", str(saida)]) == 0
    assert (saida / "resultados.csv").is_file() and (saida / "resumo.json").is_file()


def test_auc():
    assert avaliar_externo._auc([0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9]) == 1.0
    assert avaliar_externo._auc([0, 1], [0.5, 0.5]) == 0.5
    assert avaliar_externo._auc([1, 1], [0.1, 0.2]) is None


# ---------------------------------------------------------------- treinar_com_videos


def test_escolher_limiar_respeita_fp_alvo():
    reais = [{"rotulo": 0, "probabilidade_ia": p} for p in np.linspace(0.0, 0.99, 100)]
    ias = [{"rotulo": 1, "probabilidade_ia": 0.99}]
    limiar = tcv.escolher_limiar(reais + ias, fp_alvo=0.02)
    assert np.mean([r["probabilidade_ia"] >= limiar for r in reais]) <= 0.02
    # Nunca abaixo de 0,5, mesmo se os reais forem todos baixos.
    assert tcv.escolher_limiar([{"rotulo": 0, "probabilidade_ia": 0.01}], 0.02) >= 0.5


def test_medir_faixa_inconclusiva():
    previsoes = [
        {"rotulo": 0, "gerador": "real", "probabilidade_ia": 0.1},
        {"rotulo": 0, "gerador": "real", "probabilidade_ia": 0.75},
        {"rotulo": 1, "gerador": "sora2", "probabilidade_ia": 0.95},
        {"rotulo": 1, "gerador": "veo31", "probabilidade_ia": 0.2},
    ]
    m = tcv.medir(previsoes, limiar=0.8, margem=0.1)
    assert m["falso_positivo"] == 0.0
    assert m["reais_inconclusivos"] == 0.5
    assert m["ia_detectada"] == 0.5
    assert m["ia_detectada_por_gerador"] == {"sora2": 1.0, "veo31": 0.0}


def _linhas_sinteticas(n_por_grupo=12, semente=0):
    """Uma coluna informativa ('x') e uma de ruido. Videos IA de 3 geradores."""
    rng = np.random.default_rng(semente)
    base, videos = [], []
    for grupo, rotulo in (("reais/a", 0), ("reais/b", 0), ("ia/tts1", 1), ("ia/tts2", 1)):
        for i in range(n_por_grupo):
            base.append({"arquivo": f"{grupo}/{i}", "rotulo": rotulo, "grupo": grupo, "gerador": grupo,
                         "origem": "base", "x": rotulo * 2 + rng.normal(), "y": rng.normal()})
    for i in range(15):
        videos.append({"arquivo": f"IMG_{i}.mp4", "rotulo": 0, "grupo": "video/real", "gerador": "real",
                       "origem": "video", "x": rng.normal(), "y": rng.normal()})
    for gerador in ("sora2", "veo31", "ltx2"):
        for i in range(5):
            videos.append({"arquivo": f"{gerador}_{i}.mp4", "rotulo": 1, "grupo": f"video/{gerador}",
                           "gerador": gerador, "origem": "video", "x": 2 + rng.normal(), "y": rng.normal()})
    return base, videos


def test_validar_por_gerador_preve_cada_video_uma_vez():
    base, videos = _linhas_sinteticas()
    previsoes = tcv.validar_por_gerador(base, videos, "regressao_logistica")
    assert sorted(p["arquivo"] for p in previsoes) == sorted(v["arquivo"] for v in videos)
    assert tcv.medir(previsoes, 0.5, 0.0)["auc"] > 0.8


def test_fatias_reais_sao_estaveis():
    _, videos = _linhas_sinteticas()
    assert tcv.fatias_reais(videos) == tcv.fatias_reais(videos)
    assert set(tcv.fatias_reais(videos).values()) == set(range(tcv.FATIAS_REAIS))


def test_pesos_equilibram_videos_e_base():
    base, videos = _linhas_sinteticas()
    linhas = base + videos
    w = tcv._pesos(linhas, 1.0)
    total_video = sum(wi for wi, l in zip(w, linhas) if l["origem"] == "video")
    assert total_video == pytest.approx(len(base))


@pytest.mark.parametrize("nome", ["regressao_logistica", "random_forest", "gradient_boosting"])
def test_modelos_aceitam_peso(nome):
    base, videos = _linhas_sinteticas()
    linhas = base + videos
    x = tcv._matriz(linhas, ["x", "y"])
    y = np.array([l["rotulo"] for l in linhas])
    modelo = tcv._ajustar(tcv.criar_modelo(nome), x, y, tcv._pesos(linhas, 1.0))
    assert modelo.predict_proba(x).shape == (len(linhas), 2)


def test_main_ponta_a_ponta(tmp_path, pasta_videos):
    import joblib

    base_linhas = []
    for grupo, rotulo in (("reais/l1", 0), ("reais/l2", 0), ("ia/t1", 1), ("ia/t2", 1)):
        for i in range(4):
            sinal = tom(300 + 20 * i) if rotulo == 0 else ruido(semente=100 + len(base_linhas))
            c, _ = extrair_caracteristicas(sinal, TAXA)
            base_linhas.append({"arquivo": f"{grupo}/{i}.wav", "rotulo": rotulo, "grupo": grupo, **c})
    csv_base = tmp_path / "base.csv"
    tcv._gravar_csv(csv_base, base_linhas)

    destino = tmp_path / "cand.joblib"
    cache = tmp_path / "cache.csv"
    saida = tmp_path / "saida"
    args = [str(csv_base), str(pasta_videos), "--cache-videos", str(cache), "--saida", str(saida),
            "--destino", str(destino)]
    assert tcv.main(args) == 0
    assert cache.is_file() and (saida / "validacao.json").is_file()
    pacote = joblib.load(destino)
    baixo, alto = pacote["faixa_inconclusiva"]
    assert baixo < alto == pacote["limiar"]
    # Segunda rodada le o cache em vez de decodificar os videos de novo.
    assert tcv.main(args) == 0
