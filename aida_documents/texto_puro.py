"""Arquivo de texto (.txt) e caracteres invisiveis em qualquer texto.

Um .txt nao guarda como foi feito: sem programa, datas ou revisoes. Sobram o texto
(identificadores e Benford, como no PDF) e o que esta escondido nele:

- caracteres de largura zero (U+200B..U+200D, U+2060, U+FEFF no meio do texto) e
  caracteres de tag (U+E0000..U+E007F): servem para marca d'agua ou texto oculto;
- seletores de variacao (U+FE00..U+FE0F e U+E0100..U+E01EF) em sequencia longa: cada um
  carrega um byte, e e assim que um manifesto C2PA pode viajar dentro de texto puro.
  Se os bytes decodificados forem um manifesto, ele e lido como no PDF.

Esta camada e experimental: ainda nao vimos um .txt real com C2PA.
"""

from __future__ import annotations

import re

from .proveniencia import eh_manifesto, resumir_manifesto

_LARGURA_ZERO = re.compile("[\u200b\u200c\u200d\u2060\ufeff\U000e0000-\U000e007f]")
_SELETORES = re.compile("[\ufe00-\ufe0f\U000e0100-\U000e01ef]{16,}")
MIN_INVISIVEIS = 3


def decodificar(dados: bytes):
    """Texto de um .txt: BOM UTF-8/UTF-16, senao UTF-8, senao Latin-1 (nunca falha)."""
    if dados.startswith((b"\xff\xfe", b"\xfe\xff")):
        return dados.decode("utf-16", "replace")
    try:
        return dados.decode("utf-8-sig")
    except UnicodeDecodeError:
        return dados.decode("latin-1")


def _byte(car):
    cp = ord(car)
    return cp - 0xFE00 if cp <= 0xFE0F else cp - 0xE0100 + 16


def ocultos(texto: str):
    """Caracteres invisiveis e, se houver, o manifesto C2PA codificado em seletores de variacao."""
    c2pa = {"presente": False}
    for trecho in _SELETORES.findall(texto):
        dados = bytes(_byte(c) for c in trecho)
        if eh_manifesto(dados):
            c2pa = resumir_manifesto(dados)
            break
    seletores = sum(len(t) for t in _SELETORES.findall(texto))
    invisiveis = len(_LARGURA_ZERO.findall(texto.lstrip("\ufeff"))) + seletores  # BOM inicial nao conta
    return {"caracteres_invisiveis": invisiveis, "c2pa": c2pa}


def inspecionar_txt(dados: bytes):
    texto = decodificar(dados)
    return {"formato": "txt", "texto": texto, "caracteres": len(texto), **ocultos(texto)}
