"""Quem analisa cada frame.

O AIDA Video nao reimplementa deteccao: cada frame e uma imagem e vai para o
AIDA Core, o mesmo servico que atende o AIDA Image. Trocar onde o Core roda
(Space, maquina local) e so mudar AIDA_CORE_URL.

Um analisador e qualquer objeto com `analisar(caminho_png) -> dict` que
devolva, no minimo, `resultado` e `probabilidade_ia` no contrato do Core.
Os testes usam um duble; nada aqui depende de rede para ser testado.
"""

from __future__ import annotations

import io
import os
import threading
import time
from pathlib import Path

from PIL import Image, UnidentifiedImageError

CORE_URL_PADRAO = "https://aidaon-aida-api.hf.space"
# O Core leva toda imagem ao "dominio de treino" antes de medir: thumbnail para
# lado maximo 1024 por LANCZOS (aida-space: normalizar_para_dominio_de_treino).
# Fazer exatamente essa reducao aqui da o MESMO resultado que mandar o frame
# inteiro (medido: 0.0664 nos dois casos, foto de 4080 px) e corta o envio de
# um frame 4K de ~18 s para ~3,5 s. Reduzir para outro tamanho (a versao antiga
# usava 2048 com INTER_AREA) mudava a probabilidade, porque somava duas reducoes.
# Se o Core mudar lado_maximo_canonico, mude AIDA_CORE_LADO junto.
LADO_CORE = int(os.environ.get("AIDA_CORE_LADO", "1024"))


class CoreIndisponivel(RuntimeError):
    """Rede, DNS, timeout ou Space hibernando. Vale a pena tentar de novo."""


class CoreRecusou(RuntimeError):
    """O Core respondeu 4xx: tentar de novo nao adianta."""


def _bytes_para_envio(caminho, lado=None):
    lado = LADO_CORE if lado is None else lado
    try:
        with Image.open(caminho) as imagem:
            imagem = imagem.convert("RGB")
    except (OSError, UnidentifiedImageError) as exc:
        raise ValueError(f"Frame ilegível: {Path(caminho).name}") from exc
    if lado and max(imagem.size) > lado:
        imagem.thumbnail((lado, lado), Image.Resampling.LANCZOS)
    saida = io.BytesIO()
    imagem.save(saida, "PNG")  # sem perda: o JPEG canonico e o Core quem aplica
    return saida.getvalue()


class AnalisadorCore:
    """Envia cada frame para POST /analisar do AIDA Core."""

    def __init__(self, url=None, timeout_s=180.0, tentativas=3, espera_s=2.0, sessao=None):
        import requests

        self.url = (url or os.environ.get("AIDA_CORE_URL") or CORE_URL_PADRAO).rstrip("/")
        self.timeout_s = timeout_s
        self.tentativas = max(1, int(tentativas))
        self.espera_s = espera_s
        self._requests = requests
        self._sessao_fixa = sessao
        # requests.Session nao e segura entre threads: uma por thread quando
        # os frames vao em paralelo (analisar_video(paralelo=N)).
        self._local = threading.local()

    @property
    def sessao(self):
        if self._sessao_fixa is not None:
            return self._sessao_fixa
        if not hasattr(self._local, "sessao"):
            self._local.sessao = self._requests.Session()
        return self._local.sessao

    def analisar(self, caminho_png):
        conteudo = _bytes_para_envio(caminho_png)
        ultimo_erro = None
        for tentativa in range(self.tentativas):
            if tentativa:
                time.sleep(self.espera_s * tentativa)
            try:
                resposta = self.sessao.post(
                    f"{self.url}/analisar",
                    files={"imagem": (Path(caminho_png).name, conteudo, "image/png")},
                    # Sem mapas de evidencia (poupa tempo) e sem historico no Core:
                    # quem guarda o resultado do video e este pipeline.
                    data={"evidencias": "false", "historico_habilitado": "false"},
                    timeout=self.timeout_s,
                )
            except self._requests.RequestException as exc:
                ultimo_erro = CoreIndisponivel(f"Core inacessivel em {self.url}: {exc}")
                continue

            if resposta.status_code >= 500:
                ultimo_erro = CoreIndisponivel(f"Core respondeu {resposta.status_code}")
                continue
            try:
                corpo = resposta.json()
            except ValueError:
                corpo = None
            if resposta.status_code >= 400:
                mensagem = corpo.get("erro") if isinstance(corpo, dict) else None
                raise CoreRecusou(f"Core recusou o frame ({resposta.status_code}): {mensagem or resposta.text[:200]}")
            if not isinstance(corpo, dict) or "resultado" not in corpo:
                ultimo_erro = CoreIndisponivel("Core devolveu uma resposta fora do contrato")
                continue
            return corpo
        raise ultimo_erro


class AnalisadorFixo:
    """Duble deterministico: devolve respostas prontas, em ordem ou por nome de arquivo.

    Serve para testes e para rodar o pipeline inteiro sem o Core no ar.
    """

    def __init__(self, respostas):
        self.respostas = respostas
        self.chamadas = []

    def analisar(self, caminho_png):
        self.chamadas.append(Path(caminho_png).name)
        if callable(self.respostas):
            resposta = self.respostas(len(self.chamadas) - 1, Path(caminho_png).name)
        else:
            resposta = self.respostas[(len(self.chamadas) - 1) % len(self.respostas)]
        if isinstance(resposta, Exception):
            raise resposta
        return dict(resposta)
