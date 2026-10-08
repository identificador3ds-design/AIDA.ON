"""Testes do AIDA Video: extracao, cliente do Core, agregacao e pipeline.

Nenhum teste toca a rede: o Core e substituido por AnalisadorFixo ou por uma
sessao HTTP falsa. Os videos sao gerados na hora (ver conftest.py).
"""

from __future__ import annotations

import json

import numpy as np
import pytest

from aida_video import agregacao
from aida_video.agregacao import IA, INCONCLUSIVO, REAL, agregar, combinar
from aida_video.analisadores import AnalisadorCore, AnalisadorFixo, CoreIndisponivel, CoreRecusou
from aida_video.analisar_video import analisar_video, main
from aida_video.extrair_frames import aplicar_rotacao, extrair_frames, validar_video

FRAME_REAL = {"resultado": REAL, "probabilidade_ia": 0.1, "fora_de_dominio": False}
FRAME_IA = {"resultado": IA, "probabilidade_ia": 0.9, "fora_de_dominio": False}
FRAME_INC = {"resultado": INCONCLUSIVO, "probabilidade_ia": 0.5, "fora_de_dominio": False}


# ---------------------------------------------------------------- extracao


def test_extrai_primeiro_cortes_e_intervalo(video_tres_cenas, tmp_path):
    manifesto = extrair_frames(video_tres_cenas, tmp_path / "f")
    motivos = [f["motivo"] for f in manifesto["frames"]]
    tempos = [f["tempo_s"] for f in manifesto["frames"]]

    assert motivos[0] == "primeiro"
    assert motivos.count("corte_de_cena") == 2  # 3 cenas -> 2 cortes
    assert tempos == sorted(tempos)
    # Os cortes caem nas trocas de cena (2 s e 4 s), com a resolucao da varredura (0,2 s).
    cortes = [f["tempo_s"] for f in manifesto["frames"] if f["motivo"] == "corte_de_cena"]
    assert cortes == pytest.approx([2.0, 4.0], abs=0.21)
    for f in manifesto["frames"]:
        assert (tmp_path / "f" / f["arquivo"]).is_file()
    salvo = json.loads((tmp_path / "f" / "manifesto.json").read_text(encoding="utf-8"))
    assert salvo["frames"] == manifesto["frames"]


def test_metadados(video_tres_cenas, tmp_path):
    meta = extrair_frames(video_tres_cenas, tmp_path / "f")["metadados"]
    assert meta["fps"] == pytest.approx(25, abs=0.1)
    assert meta["duracao_s"] == pytest.approx(6.0, abs=0.1)
    assert (meta["largura"], meta["altura"]) == (160, 120)
    assert meta["tem_audio"] is True
    assert meta["frames_lidos"] == 150


def test_cena_parada_descarta_duplicatas(video_parado, tmp_path):
    manifesto = extrair_frames(video_parado, tmp_path / "f")
    # 6 s de quadro identico: so o primeiro frame e salvo.
    assert [f["motivo"] for f in manifesto["frames"]] == ["primeiro"]


def test_respeita_max_frames(video_tres_cenas, tmp_path):
    manifesto = extrair_frames(video_tres_cenas, tmp_path / "f", intervalo_s=0.2, max_frames=4)
    assert len(manifesto["frames"]) == 4
    assert len(list((tmp_path / "f").glob("*.png"))) == 4


def test_caminho_com_acento_e_espaco(tmp_path):
    from conftest import gerar_video

    video = gerar_video(tmp_path / "vídeo de ação.mp4", com_audio=False)
    manifesto = extrair_frames(video, tmp_path / "saída ç")
    assert manifesto["frames"]


def test_frames_png_sao_identicos_ao_decodificado(video_tres_cenas, tmp_path):
    import cv2

    manifesto = extrair_frames(video_tres_cenas, tmp_path / "f")
    dados = (tmp_path / "f" / manifesto["frames"][0]["arquivo"]).read_bytes()
    imagem = cv2.imdecode(np.frombuffer(dados, np.uint8), cv2.IMREAD_COLOR)
    assert imagem.shape == (120, 160, 3)
    # Primeira cena e azul em RGB -> canal 0 (B) alto no BGR do OpenCV.
    assert imagem[5, 150, 0] > 200 and imagem[5, 150, 2] < 50


@pytest.mark.parametrize(
    "rotacao, esperado",
    [(0, (2, 3)), (90, (3, 2)), (-90, (3, 2)), (180, (2, 3)), (None, (2, 3))],
)
def test_aplicar_rotacao_formato(rotacao, esperado):
    frame = np.arange(2 * 3 * 3, dtype=np.uint8).reshape(2, 3, 3)
    assert aplicar_rotacao(frame, rotacao).shape[:2] == esperado


def test_aplicar_rotacao_celular_em_pe_gira_no_sentido_horario():
    # Celular em pe grava -90: o canto superior esquerdo vai para o superior direito.
    frame = np.zeros((2, 3, 1), np.uint8)
    frame[0, 0] = 255
    girado = aplicar_rotacao(frame, -90)
    assert girado[0, -1, 0] == 255


def test_arquivo_inexistente(tmp_path):
    with pytest.raises(FileNotFoundError):
        validar_video(tmp_path / "nao_existe.mp4")


def test_extensao_invalida(tmp_path):
    arquivo = tmp_path / "foto.jpg"
    arquivo.write_bytes(b"x")
    with pytest.raises(ValueError, match="não suportada"):
        validar_video(arquivo)


def test_arquivo_vazio(tmp_path):
    arquivo = tmp_path / "vazio.mp4"
    arquivo.touch()
    with pytest.raises(ValueError, match="vazio"):
        validar_video(arquivo)


def test_arquivo_corrompido_da_erro_claro(tmp_path):
    arquivo = tmp_path / "lixo.mp4"
    arquivo.write_bytes(np.random.default_rng(0).integers(0, 256, 4096, dtype=np.uint8).tobytes())
    with pytest.raises(ValueError):
        extrair_frames(arquivo, tmp_path / "f")


def test_video_truncado_aproveita_o_inicio(video_tres_cenas, tmp_path):
    dados = video_tres_cenas.read_bytes()
    truncado = tmp_path / "truncado.mp4"
    truncado.write_bytes(dados[: int(len(dados) * 0.6)])
    try:
        manifesto = extrair_frames(truncado, tmp_path / "f")
    except ValueError:
        # MP4 com o indice (moov) no fim nao abre truncado: erro claro tambem e aceitavel.
        return
    assert manifesto["frames"]


def test_parametros_invalidos(video_tres_cenas, tmp_path):
    with pytest.raises(ValueError):
        extrair_frames(video_tres_cenas, tmp_path / "f", intervalo_s=0)
    with pytest.raises(ValueError):
        extrair_frames(video_tres_cenas, tmp_path / "f", max_frames=0)


# ---------------------------------------------------------------- agregacao


def _frames(*respostas):
    return [{"tempo_s": float(i), **r} for i, r in enumerate(respostas)]


def test_agrega_real():
    r = agregar(_frames(*[FRAME_REAL] * 9, FRAME_IA))
    assert r["resultado"] == REAL
    assert r["contagem"] == {REAL: 9, IA: 1, INCONCLUSIVO: 0}
    assert "isolado" in r["motivos"][0]


def test_agrega_real_editada_vota_como_real():
    # Sem esta regra, quadros REAL_EDITADA caiam na contagem de INCONCLUSIVO.
    editado = {**FRAME_REAL, "resultado": "REAL_EDITADA"}
    r = agregar(_frames(*[editado] * 9, FRAME_IA))
    assert r["resultado"] == REAL
    assert r["contagem"] == {REAL: 9, IA: 1, INCONCLUSIVO: 0}


def test_agrega_ia_por_maioria():
    r = agregar(_frames(FRAME_IA, FRAME_REAL, FRAME_IA, FRAME_IA, FRAME_REAL, FRAME_IA))
    assert r["resultado"] == IA
    assert r["probabilidade_ia"]["maxima"] == 0.9


def test_agrega_ia_por_trecho_continuo():
    # 3 de 10 frames IA seguidos (30% do video): deepfake localizado.
    r = agregar(_frames(*[FRAME_REAL] * 4, FRAME_IA, FRAME_IA, FRAME_IA, *[FRAME_REAL] * 3))
    assert r["resultado"] == IA
    assert r["trechos_ia"] == [{"inicio_s": 4.0, "fim_s": 6.0, "frames": 3, "probabilidade_ia_media": 0.9}]


def test_ia_espalhada_nao_forma_trecho():
    r = agregar(_frames(FRAME_REAL, FRAME_IA, FRAME_REAL, FRAME_IA, FRAME_REAL, FRAME_REAL, FRAME_REAL, FRAME_REAL, FRAME_REAL, FRAME_REAL))
    assert r["resultado"] == REAL


def test_agrega_dividido_e_inconclusivo():
    r = agregar(_frames(FRAME_REAL, FRAME_INC, FRAME_INC, FRAME_REAL, FRAME_IA, FRAME_INC))
    assert r["resultado"] == INCONCLUSIVO
    assert "divididos" in r["motivos"][0]


def test_poucos_frames_validos():
    r = agregar(_frames(FRAME_REAL, {"erro": "timeout"}, {**FRAME_REAL, "fora_de_dominio": True}))
    assert r["resultado"] == INCONCLUSIVO
    assert r["frames_validos"] == 1
    assert r["frames_com_erro"] == 1 and r["frames_fora_de_dominio"] == 1


def test_agrega_lista_vazia():
    r = agregar([])
    assert r["resultado"] == INCONCLUSIVO
    assert r["probabilidade_ia"] is None


def test_resultado_desconhecido_conta_como_inconclusivo():
    r = agregar(_frames(*[{"resultado": "???", "probabilidade_ia": 0.5}] * 3))
    assert r["contagem"][INCONCLUSIVO] == 3


def test_regras_sao_configuraveis():
    frames = _frames(FRAME_REAL, FRAME_REAL, FRAME_IA)
    assert agregar(frames)["resultado"] == INCONCLUSIVO
    assert agregar(frames, {"fracao_real": 0.6, "sequencia_minima": 2})["resultado"] == REAL


@pytest.mark.parametrize(
    "visual, audio, prob_audio, esperado",
    [
        (REAL, REAL, 0.1, REAL),
        (REAL, None, None, REAL),
        (REAL, INCONCLUSIVO, 0.55, REAL),
        (REAL, IA, 0.95, IA),  # voz sintetica forte sobre imagem real
        (REAL, IA, None, IA),  # audio sem probabilidade: vale o resultado
        (REAL, IA, 0.7, INCONCLUSIVO),  # audio fraco discorda da imagem
        (IA, REAL, 0.1, IA),
        (INCONCLUSIVO, REAL, 0.1, REAL),  # audio desempata
        (INCONCLUSIVO, IA, 0.7, IA),
        (INCONCLUSIVO, INCONCLUSIVO, 0.55, INCONCLUSIVO),
        (INCONCLUSIVO, None, None, INCONCLUSIVO),
    ],
)
def test_combinar(visual, audio, prob_audio, esperado):
    r = combinar({"resultado": visual, "motivos": ["m"]}, {"resultado": audio, "probabilidade_ia": prob_audio})
    assert r["resultado"] == esperado
    assert r["inconclusivo"] == (esperado == INCONCLUSIVO)
    assert r["motivos"]


def test_combinar_limiar_forte_configuravel():
    visual = {"resultado": REAL, "motivos": []}
    audio = {"resultado": IA, "probabilidade_ia": 0.7}
    assert combinar(visual, audio)["resultado"] == INCONCLUSIVO
    assert combinar(visual, audio, {"audio_ia_forte": 0.65})["resultado"] == IA


# ---------------------------------------------------------------- cliente do Core


class _Resposta:
    def __init__(self, status, corpo=None, texto=""):
        self.status_code = status
        self._corpo = corpo
        self.text = texto

    def json(self):
        if self._corpo is None:
            raise ValueError("nao e json")
        return self._corpo


class _SessaoFalsa:
    def __init__(self, respostas):
        self.respostas = list(respostas)
        self.enviados = []

    def post(self, url, files=None, data=None, timeout=None):
        self.enviados.append({"url": url, "files": files, "data": data})
        resposta = self.respostas.pop(0)
        if isinstance(resposta, Exception):
            raise resposta
        return resposta


@pytest.fixture
def png(tmp_path):
    import cv2

    caminho = tmp_path / "f.png"
    caminho.write_bytes(cv2.imencode(".png", np.zeros((8, 8, 3), np.uint8))[1].tobytes())
    return caminho


def test_core_sucesso_envia_contrato(png):
    sessao = _SessaoFalsa([_Resposta(200, FRAME_REAL)])
    r = AnalisadorCore("http://core/", sessao=sessao).analisar(png)
    assert r["resultado"] == REAL
    enviado = sessao.enviados[0]
    assert enviado["url"] == "http://core/analisar"
    assert enviado["data"]["historico_habilitado"] == "false"
    assert enviado["files"]["imagem"][0] == "f.png"


def test_core_repete_apos_falha_de_rede(png):
    import requests

    sessao = _SessaoFalsa([requests.ConnectionError("dns"), _Resposta(503), _Resposta(200, FRAME_IA)])
    r = AnalisadorCore("http://core", sessao=sessao, tentativas=3, espera_s=0).analisar(png)
    assert r["resultado"] == IA
    assert len(sessao.enviados) == 3


def test_core_indisponivel_depois_das_tentativas(png):
    import requests

    sessao = _SessaoFalsa([requests.Timeout("t")] * 2)
    with pytest.raises(CoreIndisponivel):
        AnalisadorCore("http://core", sessao=sessao, tentativas=2, espera_s=0).analisar(png)


def test_core_4xx_nao_repete(png):
    sessao = _SessaoFalsa([_Resposta(400, {"erro": "imagem invalida"}), _Resposta(200, FRAME_REAL)])
    with pytest.raises(CoreRecusou, match="imagem invalida"):
        AnalisadorCore("http://core", sessao=sessao, espera_s=0).analisar(png)
    assert len(sessao.enviados) == 1


def test_core_resposta_fora_do_contrato(png):
    sessao = _SessaoFalsa([_Resposta(200, None, "<html>"), _Resposta(200, {"x": 1})])
    with pytest.raises(CoreIndisponivel, match="contrato"):
        AnalisadorCore("http://core", sessao=sessao, tentativas=2, espera_s=0).analisar(png)


def test_frame_e_reduzido_como_o_core_reduz(tmp_path):
    """O Core faz thumbnail(1024, LANCZOS); reduzir igual aqui da o mesmo resultado
    que mandar o frame cheio, com um envio bem menor."""
    import io

    import cv2
    from PIL import Image

    ruido = np.random.default_rng(1).integers(0, 256, (2160, 3840, 3), dtype=np.uint8)
    caminho = tmp_path / "4k.png"
    caminho.write_bytes(cv2.imencode(".png", ruido)[1].tobytes())
    sessao = _SessaoFalsa([_Resposta(200, FRAME_REAL)])
    AnalisadorCore("http://core", sessao=sessao).analisar(caminho)
    enviado = sessao.enviados[0]["files"]["imagem"][1]

    esperado = Image.fromarray(np.ascontiguousarray(ruido[:, :, ::-1]))
    esperado.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
    recebido = Image.open(io.BytesIO(enviado))
    assert recebido.size == (1024, 576)
    assert np.array_equal(np.asarray(recebido.convert("RGB")), np.asarray(esperado))


def test_frame_pequeno_nao_e_ampliado(png):
    import io

    from PIL import Image

    sessao = _SessaoFalsa([_Resposta(200, FRAME_REAL)])
    AnalisadorCore("http://core", sessao=sessao).analisar(png)
    assert Image.open(io.BytesIO(sessao.enviados[0]["files"]["imagem"][1])).size == (8, 8)


def test_frame_ilegivel(tmp_path):
    caminho = tmp_path / "ruim.png"
    caminho.write_bytes(b"nao e png")
    with pytest.raises(ValueError, match="ilegível"):
        AnalisadorCore("http://core", sessao=_SessaoFalsa([])).analisar(caminho)


def test_sessao_http_e_uma_por_thread():
    import threading

    analisador = AnalisadorCore("http://core")
    sessoes = []
    threads = [threading.Thread(target=lambda: sessoes.append(analisador.sessao)) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len({id(s) for s in sessoes}) == 3
    assert analisador.sessao is analisador.sessao  # a mesma thread reaproveita


def test_url_do_core_pela_variavel_de_ambiente(monkeypatch):
    monkeypatch.setenv("AIDA_CORE_URL", "http://localhost:7860/")
    assert AnalisadorCore().url == "http://localhost:7860"


# ---------------------------------------------------------------- pipeline


def test_pipeline_completo_com_saida(video_tres_cenas, tmp_path):
    analisador = AnalisadorFixo([FRAME_REAL])
    saida = tmp_path / "resultado"
    r = analisar_video(video_tres_cenas, analisador=analisador, pasta_saida=saida)

    assert r["resultado"] == REAL
    assert r["visual"]["frames_validos"] == len(analisador.chamadas) == len(r["frames"])
    assert (saida / "relatorio.json").is_file()
    assert (saida / "audio.wav").is_file()
    assert r["audio"]["presente"] is True
    assert r["audio"]["qualidade"]["taxa_amostragem"] == 16000
    assert r["audio"]["qualidade"]["duracao_s"] == pytest.approx(6.0, abs=0.2)
    assert "caracteristicas" not in r["audio"]  # nao incha o relatorio
    json.loads((saida / "relatorio.json").read_text(encoding="utf-8"))


def test_pipeline_sem_saida_nao_deixa_lixo(video_tres_cenas, tmp_path, monkeypatch):
    import tempfile

    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "tmp"))
    (tmp_path / "tmp").mkdir()
    analisar_video(video_tres_cenas, analisador=AnalisadorFixo([FRAME_REAL]))
    assert list((tmp_path / "tmp").iterdir()) == []


def test_pipeline_detecta_trecho_ia(video_tres_cenas):
    # Frames da cena do meio (2 s a 4 s) sao IA.
    def respostas(i, nome):
        tempo = float(nome.split("_")[2].rstrip("s.png"))
        return FRAME_IA if 2.0 <= tempo < 4.0 else FRAME_REAL

    r = analisar_video(video_tres_cenas, analisador=AnalisadorFixo(respostas), parametros_extracao={"intervalo_s": 0.4})
    assert r["resultado"] == IA
    assert r["visual"]["trechos_ia"][0]["inicio_s"] == pytest.approx(2.0, abs=0.21)


def test_pipeline_video_sem_audio(video_sem_audio):
    r = analisar_video(video_sem_audio, analisador=AnalisadorFixo([FRAME_REAL]))
    assert r["audio"]["presente"] is False
    assert r["resultado"] == REAL


def test_pipeline_frame_com_erro_nao_derruba(video_tres_cenas):
    respostas = [FRAME_REAL, CoreRecusou("400"), FRAME_REAL, RuntimeError("bug"), FRAME_REAL]
    r = analisar_video(video_tres_cenas, analisador=AnalisadorFixo(respostas))
    assert r["visual"]["frames_com_erro"] >= 2
    erros = [f["erro"] for f in r["frames"] if "erro" in f]
    assert any("RuntimeError" in e for e in erros)


def test_pipeline_aborta_quando_core_cai(video_tres_cenas):
    analisador = AnalisadorFixo([CoreIndisponivel("fora do ar")])
    r = analisar_video(video_tres_cenas, analisador=analisador, parametros_extracao={"intervalo_s": 0.4})
    assert len(analisador.chamadas) == 3  # para de tentar depois de 3 falhas seguidas
    assert r["resultado"] == INCONCLUSIVO
    assert "indisponível" in r["visual"]["motivos"][0]
    assert all("erro" in f for f in r["frames"])


def test_pipeline_sem_core(video_tres_cenas):
    r = analisar_video(video_tres_cenas, analisar_frames=False)
    assert r["resultado"] == INCONCLUSIVO
    assert r["frames"] and all("resultado" not in f for f in r["frames"])


def test_pipeline_audio_ia_marca_o_video(video_tres_cenas, monkeypatch):
    import aida_audio.analisar as mod_audio

    def falso(amostras, taxa, *a, **k):
        return {"resultado": IA, "probabilidade_ia": 0.95, "motivos": [], "caracteristicas": {}}

    monkeypatch.setattr(mod_audio, "analisar_amostras", falso)
    r = analisar_video(video_tres_cenas, analisador=AnalisadorFixo([FRAME_REAL]))
    assert r["resultado"] == IA
    assert "áudio" in r["motivos"][0]


def test_cli_sem_core(video_tres_cenas, tmp_path, capsys):
    codigo = main([str(video_tres_cenas), "--sem-core", "--saida", str(tmp_path / "s")])
    assert codigo == 0
    assert "RESULTADO: INCONCLUSIVO" in capsys.readouterr().out


def test_cli_arquivo_inexistente(tmp_path, capsys):
    assert main([str(tmp_path / "x.mp4"), "--sem-core"]) == 2
    assert "Erro" in capsys.readouterr().err


def test_regras_padrao_nao_mudam_por_efeito_colateral():
    antes = dict(agregacao.REGRAS_PADRAO)
    agregar(_frames(FRAME_REAL), {"fracao_real": 0.1})
    assert agregacao.REGRAS_PADRAO == antes


def test_pipeline_em_paralelo_mantem_a_ordem_do_tempo(video_tres_cenas):
    import threading
    import time as _time

    threads = set()

    def respostas(i, nome):
        threads.add(threading.get_ident())
        _time.sleep(0.01 * (i % 3))  # respostas chegam fora de ordem
        tempo = float(nome.split("_")[2].rstrip("s.png"))
        return FRAME_IA if 2.0 <= tempo < 4.0 else FRAME_REAL

    parametros = {"intervalo_s": 0.4}
    sequencial = analisar_video(video_tres_cenas, analisador=AnalisadorFixo(respostas), parametros_extracao=parametros)
    threads.clear()
    paralelo = analisar_video(
        video_tres_cenas, analisador=AnalisadorFixo(respostas), parametros_extracao=parametros, paralelo=3
    )
    assert len(threads) > 1
    tempos = [f["tempo_s"] for f in paralelo["frames"]]
    assert tempos == sorted(tempos)
    assert [f["resultado"] for f in paralelo["frames"]] == [f["resultado"] for f in sequencial["frames"]]
    assert paralelo["resultado"] == sequencial["resultado"] == IA


def test_pipeline_em_paralelo_aborta_quando_core_cai(video_tres_cenas):
    analisador = AnalisadorFixo([CoreIndisponivel("fora do ar")])
    r = analisar_video(video_tres_cenas, analisador=analisador, parametros_extracao={"intervalo_s": 0.4}, paralelo=2)
    assert len(analisador.chamadas) == 4  # 2 lotes de 2: a 3a falha seguida esta no 2o lote
    assert r["resultado"] == INCONCLUSIVO
    assert all("erro" in f for f in r["frames"])
