"""Envio unificado (index-enviar.html): o tipo do arquivo escolhe o detector.

`tipoDe` vive em scripts/aida-encaminhar.js e é exercitado pelo Node. Cada
detector mantém a própria página (quem quer ver como funciona abre direto).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
MODULO = RAIZ / "scripts" / "aida-encaminhar.js"
PAGINAS = RAIZ / "pages"


def _tipo(nome, mime=""):
    codigo = (
        "global.window={location:{search:''}};"
        f"require({json.dumps(str(MODULO))});"
        f"process.stdout.write(String(window.AIDAEncaminhar.tipoDe({{name:{json.dumps(nome)},type:{json.dumps(mime)}}})))"
    )
    return subprocess.run(["node", "-e", codigo], capture_output=True, text=True, check=True).stdout


@pytest.mark.skipif(shutil.which("node") is None, reason="node ausente")
@pytest.mark.parametrize("nome,mime,esperado", [
    ("foto.jpg", "image/jpeg", "imagem"),
    ("IMG_0001.HEIC", "", "imagem"),                 # Windows não dá MIME a HEIC
    ("clipe.mp4", "video/mp4", "video"),
    ("gravacao.mov", "", "video"),
    ("PTT-20261011.opus", "", "audio"),              # áudio do WhatsApp
    ("voz.ogg", "audio/ogg", "audio"),
    ("musica.mp3", "audio/mpeg", "audio"),
    ("nota.pdf", "application/pdf", "documento"),
    ("planilha.xlsx", "", "null"),
])
def test_tipo_do_arquivo_escolhe_o_detector(nome, mime, esperado):
    assert _tipo(nome, mime) == esperado


def test_cada_detector_tem_pagina_e_recebe_o_arquivo_encaminhado():
    destinos = {
        "index-seleciona.html": ("script-ferramenta.js", '"imagem"'),
        "index-video.html": ("script-video.js", '"video"'),
        "index-audio.html": ("script-audio.js", '"audio"'),
        "index-documentos.html": ("script-documentos.js", '"documento"'),
    }
    for pagina, (script, tipo) in destinos.items():
        html = (PAGINAS / pagina).read_text(encoding="utf-8")
        assert "aida-encaminhar.js" in html and html.index("aida-encaminhar.js") < html.index(script), pagina
        codigo = (RAIZ / "scripts" / script).read_text(encoding="utf-8")
        assert f"entregarEm(" in codigo and tipo in codigo, script


def test_pagina_de_envio_aponta_para_os_quatro_detectores():
    html = (PAGINAS / "index-enviar.html").read_text(encoding="utf-8")
    for destino in ("index-seleciona.html", "index-video.html", "index-audio.html", "index-documentos.html"):
        assert f'href="./{destino}"' in html
    inicio = (PAGINAS / "index-apresentacao.html").read_text(encoding="utf-8")
    assert 'href="./index-enviar.html"' in inicio
