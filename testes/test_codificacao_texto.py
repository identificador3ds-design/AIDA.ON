"""Texto exibido ao usuário não pode ter UTF-8 duplamente codificado.

`script-validador.js` e `validador_tac_aida.html` mostravam "nÃ£o", "vÃ¡lido"
e "inspeÃƒÂ§ÃƒÂ£o" (texto salvo em UTF-8, relido como Windows-1252 e salvo de
novo, até duas vezes).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
ARQUIVOS = sorted([RAIZ / "index.html", *(RAIZ / "pages").glob("*.html"),
                   *(RAIZ / "scripts").glob("*.js"), *(RAIZ / "styles").glob("*.css")])
MOJIBAKE = re.compile(r"Ã[\u0080-¿Œ-™]|Â[ -¿]|â€")


@pytest.mark.parametrize("arquivo", ARQUIVOS, ids=lambda p: p.name)
def test_sem_texto_corrompido(arquivo):
    texto = arquivo.read_text(encoding="utf-8")
    achados = [m.group(0) for m in MOJIBAKE.finditer(texto)]

    assert not achados, f"{arquivo.name}: {len(achados)} trechos corrompidos, ex.: {achados[:3]}"
