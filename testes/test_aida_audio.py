"""Testes do AIDA Audio: leitura, caracteristicas, EER, treino e analise."""

from __future__ import annotations

import numpy as np
import pytest

from aida_audio import analisar_amostras, analisar_audio, carregar_audio, extrair_caracteristicas, salvar_wav
from aida_audio.carregar import AudioAusente
from aida_audio.modelo import calcular_eer, carregar_modelo, gerar_tabela, listar_dataset, treinar

TAXA = 16000


def tom(freq=440.0, segundos=2.0, taxa=TAXA, amplitude=0.3):
    t = np.arange(int(segundos * taxa)) / taxa
    return (amplitude * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def ruido(segundos=2.0, taxa=TAXA, semente=0, amplitude=0.2):
    return (amplitude * np.random.default_rng(semente).standard_normal(int(segundos * taxa))).astype(np.float32)


# ---------------------------------------------------------------- leitura


def test_wav_ida_e_volta(tmp_path):
    original = tom()
    caminho = salvar_wav(tmp_path / "t.wav", original)
    lido, taxa = carregar_audio(caminho)
    assert taxa == TAXA
    assert lido.dtype == np.float32
    assert abs(lido.size - original.size) <= 32
    n = min(lido.size, original.size)
    assert np.max(np.abs(lido[:n] - original[:n])) < 1e-3


def test_reamostra_para_16k_mono(tmp_path):
    caminho = salvar_wav(tmp_path / "44k.wav", tom(taxa=44100), taxa=44100)
    amostras, taxa = carregar_audio(caminho)
    assert taxa == 16000
    assert amostras.ndim == 1
    assert amostras.size == pytest.approx(2 * 16000, abs=200)


def test_le_trilha_de_video(video_tres_cenas):
    amostras, taxa = carregar_audio(video_tres_cenas)
    assert amostras.size / taxa == pytest.approx(6.0, abs=0.2)
    assert np.abs(amostras).max() == pytest.approx(0.3, abs=0.05)


def test_limite_de_duracao(tmp_path):
    caminho = salvar_wav(tmp_path / "longo.wav", tom(segundos=5))
    amostras, _ = carregar_audio(caminho, max_segundos=1.5)
    assert amostras.size == int(1.5 * TAXA)


def test_video_sem_audio(video_sem_audio):
    with pytest.raises(AudioAusente):
        carregar_audio(video_sem_audio)


def test_audio_inexistente_vazio_e_corrompido(tmp_path):
    with pytest.raises(FileNotFoundError):
        carregar_audio(tmp_path / "nada.wav")
    (tmp_path / "vazio.wav").touch()
    with pytest.raises(ValueError):
        carregar_audio(tmp_path / "vazio.wav")
    (tmp_path / "lixo.mp3").write_bytes(b"\x00\x01" * 500)
    with pytest.raises(ValueError):
        carregar_audio(tmp_path / "lixo.mp3")


# ---------------------------------------------------------------- caracteristicas


@pytest.mark.parametrize(
    "sinal",
    [tom(), ruido(), np.zeros(TAXA, np.float32), np.zeros(10, np.float32), np.zeros(0, np.float32), np.ones(TAXA, np.float32)],
    ids=["tom", "ruido", "silencio", "10_amostras", "vazio", "saturado"],
)
def test_caracteristicas_sempre_mesmas_chaves_e_finitas(sinal):
    referencia, _ = extrair_caracteristicas(tom(), TAXA)
    caracteristicas, qualidade = extrair_caracteristicas(sinal, TAXA)
    assert caracteristicas.keys() == referencia.keys()
    assert all(np.isfinite(v) for v in caracteristicas.values())
    assert set(qualidade) >= {"duracao_s", "fracao_silencio", "suficiente"}


def test_quantidade_de_caracteristicas():
    caracteristicas, _ = extrair_caracteristicas(tom(), TAXA)
    # 4 grupos cepstrais x 20 coeficientes x (media, desvio) + 8 espectrais x 4 + 2
    assert len(caracteristicas) == 4 * 20 * 2 + 8 * 4 + 2


def test_centroide_segue_a_frequencia():
    grave, _ = extrair_caracteristicas(tom(300), TAXA)
    agudo, _ = extrair_caracteristicas(tom(3000), TAXA)
    assert agudo["centroide_hz_media"] > grave["centroide_hz_media"] + 1000


def test_planura_distingue_tom_de_ruido():
    t, _ = extrair_caracteristicas(tom(), TAXA)
    r, _ = extrair_caracteristicas(ruido(), TAXA)
    assert r["planura_media"] > 5 * t["planura_media"]


def test_silencio_e_detectado():
    sinal = np.concatenate([tom(segundos=0.5), np.zeros(2 * TAXA, np.float32)])
    _, qualidade = extrair_caracteristicas(sinal, TAXA)
    assert qualidade["fracao_silencio"] == pytest.approx(0.8, abs=0.05)
    _, qualidade = extrair_caracteristicas(np.zeros(TAXA, np.float32), TAXA)
    assert qualidade["suficiente"] is False


def test_saturacao_e_detectada():
    _, qualidade = extrair_caracteristicas(np.clip(tom(amplitude=3.0), -1, 1), TAXA)
    assert qualidade["fracao_saturada"] > 0.3


# ---------------------------------------------------------------- EER


def test_eer_separacao_perfeita_e_aleatoria():
    assert calcular_eer([0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9])[0] == 0.0
    rng = np.random.default_rng(0)
    rotulos = rng.integers(0, 2, 4000)
    eer, _ = calcular_eer(rotulos, rng.random(4000))
    assert eer == pytest.approx(0.5, abs=0.05)


def test_eer_exige_duas_classes():
    with pytest.raises(ValueError):
        calcular_eer([1, 1], [0.2, 0.3])


# ---------------------------------------------------------------- dataset, treino, analise


@pytest.fixture
def dataset(tmp_path):
    """'reais' = tons com harmonicos; 'ia' = ruido filtrado. Separaveis de proposito:
    o teste verifica a TUBULACAO do treino, nao a qualidade do detector."""
    raiz = tmp_path / "dataset_audio"
    rng = np.random.default_rng(3)
    for locutor in range(3):
        for i in range(4):
            f0 = 120 + 40 * locutor + 5 * i
            sinal = sum(tom(f0 * h, amplitude=0.2 / h) for h in range(1, 6))
            salvar_wav(raiz / "reais" / f"locutor{locutor}" / f"{i}.wav", sinal)
            salvar_wav(raiz / "ia" / f"gerador{locutor}" / f"{i}.wav", ruido(semente=int(rng.integers(1e6))))
    (raiz / "ia" / "leiame.txt").write_text("ignorado")
    salvar_wav(raiz / "ia" / "silencio.wav", np.zeros(TAXA, np.float32))
    return raiz


def test_listar_dataset_agrupa_por_subpasta(dataset):
    itens = listar_dataset(dataset)
    assert len(itens) == 25  # .txt fica de fora
    grupos = {g for _, _, g in itens}
    assert "reais/locutor0" in grupos and "ia/gerador2" in grupos and "ia/silencio" in grupos


def test_listar_dataset_sem_pasta_obrigatoria(tmp_path):
    (tmp_path / "reais").mkdir()
    with pytest.raises(FileNotFoundError, match="ia"):
        listar_dataset(tmp_path)


def test_treino_e_analise_ponta_a_ponta(dataset, tmp_path):
    avisos = []
    linhas, falhas = gerar_tabela(dataset, tmp_path / "tabela.csv", avisar=avisos.append)
    assert len(linhas) == 24
    assert len(falhas) == 1 and "silencio" in falhas[0]["arquivo"]
    assert (tmp_path / "tabela.csv").is_file()

    destino = tmp_path / "modelo.joblib"
    pacote = treinar(linhas, destino)
    assert destino.is_file()
    assert pacote["nome"] in pacote["desempenho_teste"]
    assert pacote["desempenho_teste"][pacote["nome"]]["eer"] <= 0.25

    carregado = carregar_modelo(destino)
    voz = sum(tom(150 * h, amplitude=0.2 / h) for h in range(1, 6))
    r_real = analisar_amostras(voz, TAXA, pacote_modelo=carregado)
    r_ia = analisar_amostras(ruido(semente=999), TAXA, pacote_modelo=carregado)
    assert r_real["modelo_disponivel"] and r_real["resultado"] in ("REAL", "INCONCLUSIVO")
    assert r_ia["resultado"] in ("IA/MANIPULADA", "INCONCLUSIVO")
    assert r_real["probabilidade_ia"] < r_ia["probabilidade_ia"]


def test_treino_recusa_dados_insuficientes(dataset):
    linhas, _ = gerar_tabela(dataset, avisar=lambda _: None)
    # Todos os reais do mesmo locutor: impossivel separar treino/teste sem vazamento.
    so_um_grupo = [l for l in linhas if l["rotulo"] == 1 or l["grupo"] == "reais/locutor0"]
    with pytest.raises(ValueError, match="reais"):
        treinar(so_um_grupo, "nao_salva.joblib")
    with pytest.raises(ValueError):
        treinar([], "nao_salva.joblib")


def test_sem_modelo_e_inconclusivo_com_caracteristicas(tmp_path):
    r = analisar_amostras(tom(), TAXA, caminho_modelo=tmp_path / "nao_existe.joblib")
    assert r["resultado"] == "INCONCLUSIVO"
    assert r["modelo_disponivel"] is False
    assert r["probabilidade_ia"] is None
    assert r["caracteristicas"]
    assert "nenhum modelo" in r["motivos"][-1]


def test_audio_curto_ou_silencioso_e_inconclusivo_mesmo_com_modelo():
    class ModeloQueNaoPodeSerChamado:
        def predict_proba(self, x):
            raise AssertionError("nao deveria classificar audio sem conteudo")

    pacote = {"modelo": ModeloQueNaoPodeSerChamado(), "nome": "x", "colunas": [], "limiar": 0.5}
    assert analisar_amostras(tom(segundos=0.3), TAXA, pacote_modelo=pacote)["resultado"] == "INCONCLUSIVO"
    assert analisar_amostras(np.zeros(3 * TAXA, np.float32), TAXA, pacote_modelo=pacote)["resultado"] == "INCONCLUSIVO"


def test_modelo_incompativel_da_erro_claro():
    pacote = {"modelo": None, "nome": "x", "colunas": ["coluna_que_nao_existe"], "limiar": 0.5}
    with pytest.raises(ValueError, match="Treine o modelo de novo"):
        analisar_amostras(tom(), TAXA, pacote_modelo=pacote)


def test_modelo_invalido_no_disco(tmp_path):
    import joblib

    joblib.dump({"qualquer": 1}, tmp_path / "ruim.joblib")
    with pytest.raises(ValueError, match="invalido"):
        carregar_modelo(tmp_path / "ruim.joblib")


def test_analisar_audio_de_arquivo(tmp_path):
    caminho = salvar_wav(tmp_path / "a.wav", tom())
    r = analisar_audio(caminho, caminho_modelo=tmp_path / "sem.joblib")
    assert r["arquivo"] == "a.wav"
    assert r["qualidade"]["duracao_s"] == pytest.approx(2.0, abs=0.01)
