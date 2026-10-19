"""Nenhuma credencial privada pode entrar no repositório.

O site é estático e tudo em `scripts/` vai para o navegador. A chave `anon`
do Supabase é pública por desenho (quem protege os dados é o RLS); a
`service_role` ignora o RLS e, se vazar, dá acesso total ao banco.
"""

from __future__ import annotations

import base64
import json
import re
import subprocess
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
JWT = re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.(eyJ[A-Za-z0-9_-]{10,})\.[A-Za-z0-9_-]{10,}")
OUTROS = re.compile(
    r"(hf_[A-Za-z0-9]{30,}|sk-[A-Za-z0-9_-]{30,}|AKIA[0-9A-Z]{16}|"
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----|sbp_[a-f0-9]{40})"
)


def _arquivos_versionados():
    try:
        saida = subprocess.run(["git", "ls-files"], cwd=RAIZ, capture_output=True,
                               text=True, check=True).stdout
        caminhos = [RAIZ / l for l in saida.splitlines()]
    except (OSError, subprocess.CalledProcessError):
        caminhos = list(RAIZ.rglob("*"))
    textos = {".js", ".html", ".py", ".json", ".md", ".sql", ".example", ".txt", ".yml", ".yaml"}
    return [p for p in caminhos if p.is_file() and (p.suffix in textos or p.name.startswith(".env"))]


def _payload(segmento: str) -> dict:
    return json.loads(base64.urlsafe_b64decode(segmento + "=" * (-len(segmento) % 4)))


def test_todo_jwt_versionado_e_a_chave_anon():
    proibidos = []
    for caminho in _arquivos_versionados():
        texto = caminho.read_text(encoding="utf-8", errors="ignore")
        for achado in JWT.finditer(texto):
            try:
                papel = _payload(achado.group(1)).get("role")
            except ValueError:
                continue
            if papel != "anon":
                proibidos.append(f"{caminho.relative_to(RAIZ)}: role={papel}")

    assert not proibidos, f"JWT com papel privilegiado no repositório: {proibidos}"


def test_sem_tokens_de_servicos_externos():
    achados = []
    for caminho in _arquivos_versionados():
        texto = caminho.read_text(encoding="utf-8", errors="ignore")
        for m in OUTROS.finditer(texto):
            achados.append(f"{caminho.relative_to(RAIZ)}: {m.group(0)[:8]}…")

    assert not achados, f"possíveis credenciais versionadas: {achados}"
