"""Testes do servidor HTTP do AIDA Video (usado pela pagina index-video.html)."""

from __future__ import annotations

import io
import time

import pytest

from aida_video.analisadores import AnalisadorFixo
from aida_video.servidor import TTL_TAREFA_S, criar_app

FRAME_REAL = {"resultado": "REAL", "probabilidade_ia": 0.1, "fora_de_dominio": False}


@pytest.fixture
def cliente():
    # Sem thread: a analise termina dentro do POST e os testes nao precisam esperar.
    app = criar_app(lambda: AnalisadorFixo([FRAME_REAL]), executar_em_thread=False)
    app.config["TESTING"] = True
    return app.test_client()


def _enviar(cliente, caminho, nome=None, **campos):
    dados = {"video": (io.BytesIO(caminho.read_bytes()), nome or caminho.name), **campos}
    return cliente.post("/video/analisar", data=dados, content_type="multipart/form-data")


def test_saude(cliente):
    r = cliente.get("/video/saude")
    assert r.status_code == 200
    corpo = r.get_json()
    assert corpo["status"] == "online"
    assert ".mp4" in corpo["extensoes"]
    assert "modelo_audio_disponivel" in corpo


def test_fluxo_completo(cliente, video_tres_cenas):
    r = _enviar(cliente, video_tres_cenas, intervalo_s="1", max_frames="10")
    assert r.status_code == 202
    id_ = r.get_json()["tarefa"]

    tarefa = cliente.get(f"/video/tarefa/{id_}").get_json()
    assert tarefa["estado"] == "concluida", tarefa["erro"]
    assert "pasta" not in tarefa  # caminho interno do servidor nao vaza
    relatorio = tarefa["relatorio"]
    assert relatorio["resultado"] == "REAL"
    assert tarefa["progresso"]["feitos"] == tarefa["progresso"]["total"] == len(relatorio["frames"])

    arquivo = relatorio["frames"][0]["arquivo"]
    mini = cliente.get(f"/video/tarefa/{id_}/frame/{arquivo}")
    assert mini.status_code == 200
    assert mini.mimetype == "image/jpeg"
    assert mini.data[:2] == b"\xff\xd8"
    png = cliente.get(f"/video/tarefa/{id_}/frame/{arquivo}?tamanho=original")
    assert png.mimetype == "image/png"
    assert png.data[:8] == b"\x89PNG\r\n\x1a\n"


def test_nome_com_acento_e_caminho(cliente, video_tres_cenas):
    r = _enviar(cliente, video_tres_cenas, nome="../../vídeo final.MP4")
    assert r.status_code == 202
    tarefa = cliente.get(f"/video/tarefa/{r.get_json()['tarefa']}").get_json()
    assert tarefa["estado"] == "concluida", tarefa["erro"]


def test_limites_de_parametros(cliente, video_tres_cenas):
    r = _enviar(cliente, video_tres_cenas, intervalo_s="abc", max_frames="99999")
    tarefa = cliente.get(f"/video/tarefa/{r.get_json()['tarefa']}").get_json()
    parametros = tarefa["relatorio"]["parametros_extracao"]
    assert parametros["intervalo_s"] == 1.0
    assert parametros["max_frames"] == 120


def test_sem_arquivo(cliente):
    r = cliente.post("/video/analisar", data={}, content_type="multipart/form-data")
    assert r.status_code == 400
    assert "video" in r.get_json()["erro"]


def test_extensao_invalida(cliente, tmp_path):
    arquivo = tmp_path / "foto.jpg"
    arquivo.write_bytes(b"x" * 10)
    r = _enviar(cliente, arquivo)
    assert r.status_code == 400
    assert "não suportado" in r.get_json()["erro"]


def test_video_corrompido_vira_tarefa_com_erro(cliente, tmp_path):
    arquivo = tmp_path / "lixo.mp4"
    arquivo.write_bytes(b"\x00" * 2048)
    r = _enviar(cliente, arquivo)
    assert r.status_code == 202
    tarefa = cliente.get(f"/video/tarefa/{r.get_json()['tarefa']}").get_json()
    assert tarefa["estado"] == "erro"
    assert "lixo.mp4" in tarefa["erro"]
    # A mensagem do FFmpeg traz o caminho completo; a pasta interna nao pode vazar.
    assert "aida_video_srv" not in tarefa["erro"] and "\\" not in tarefa["erro"]


def test_tarefa_inexistente(cliente):
    assert cliente.get("/video/tarefa/nao_existe").status_code == 404


def test_frame_so_aceita_nomes_do_extrator(cliente, video_tres_cenas):
    id_ = _enviar(cliente, video_tres_cenas).get_json()["tarefa"]
    for nome in ("manifesto.json", "relatorio.json", "..%2Frelatorio.json", "frame_0000.png"):
        assert cliente.get(f"/video/tarefa/{id_}/frame/{nome}").status_code == 404


def test_rota_desconhecida_e_metodo_errado_devolvem_json(cliente):
    r = cliente.get("/nao/existe")
    assert r.status_code == 404 and "erro" in r.get_json()
    r = cliente.get("/video/analisar")
    assert r.status_code == 405 and "erro" in r.get_json()


def test_limite_de_tarefas_simultaneas(video_tres_cenas):
    app = criar_app(lambda: AnalisadorFixo([FRAME_REAL]), executar_em_thread=False)
    tarefas = app.config["TAREFAS"]
    for _ in range(2):
        tarefas.criar("x", "v.mp4")  # ficam em "extraindo"
    r = _enviar(app.test_client(), video_tres_cenas)
    assert r.status_code == 429


def test_tarefas_antigas_sao_apagadas(tmp_path):
    app = criar_app(executar_em_thread=False)
    tarefas = app.config["TAREFAS"]
    pasta = tmp_path / "trabalho"
    pasta.mkdir()
    id_ = tarefas.criar(pasta, "v.mp4")
    tarefas.atualizar(id_, estado="concluida")
    assert tarefas.limpar_antigas(agora=time.time() + TTL_TAREFA_S + 1) == 1
    assert tarefas.ler(id_) is None
    assert not pasta.exists()


def test_video_original_nao_fica_no_servidor(cliente, video_tres_cenas):
    id_ = _enviar(cliente, video_tres_cenas).get_json()["tarefa"]
    pasta = cliente.application.config["TAREFAS"]._dados[id_]["pasta"]
    assert not any(pasta.glob("_entrada/*.mp4"))


def test_limite_de_tamanho_devolve_413_em_json(tmp_path):
    app = criar_app(lambda: AnalisadorFixo([FRAME_REAL]), executar_em_thread=False, tamanho_max_mb=1)
    arquivo = tmp_path / "grande.mp4"
    arquivo.write_bytes(b"\x00" * (2 * 1024 * 1024))
    r = _enviar(app.test_client(), arquivo)
    assert r.status_code == 413
    assert "1 MB" in r.get_json()["erro"]
    assert app.test_client().get("/video/saude").get_json()["tamanho_max_mb"] == 1


def test_limite_padrao_comporta_video_de_celular():
    from aida_video.extrair_frames import TAMANHO_MAX_MB

    assert TAMANHO_MAX_MB >= 2048


def test_miniatura_de_frame_4k_e_pequena(tmp_path):
    import cv2
    import numpy as np

    app = criar_app(executar_em_thread=False)
    tarefas = app.config["TAREFAS"]
    id_ = tarefas.criar(tmp_path, "v.mp4")
    ruido = np.random.default_rng(0).integers(0, 256, (2160, 3840, 3), dtype=np.uint8)
    (tmp_path / "frame_0000_00000.000s.png").write_bytes(cv2.imencode(".png", ruido)[1].tobytes())
    r = app.test_client().get(f"/video/tarefa/{id_}/frame/frame_0000_00000.000s.png")
    assert r.status_code == 200
    miniatura = cv2.imdecode(np.frombuffer(r.data, np.uint8), cv2.IMREAD_COLOR)
    assert max(miniatura.shape[:2]) == 480
    assert len(r.data) < 400_000
