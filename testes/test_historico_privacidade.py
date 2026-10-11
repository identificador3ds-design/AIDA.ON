"""Privacidade do histórico: imagens dos usuários não podem ficar públicas.

Em 08/10/2026 a chave anon do site lia `historico_analises` inteira (168
linhas, 11 usuários) e cada `imagem_original` era URL de bucket público que
abria sem login. A correção tem três partes, e cada uma tem teste aqui:

* o upload grava o CAMINHO no bucket, não uma URL pública permanente;
* o histórico exibe por URL ASSINADA e apaga pelo caminho certo, inclusive
  em linhas antigas que guardam a URL pública com nome codificado;
* a migração SQL liga RLS por dono e torna o bucket privado.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
ANALISE = (RAIZ / "scripts" / "script-analise.js").read_text(encoding="utf-8")
HISTORICO = (RAIZ / "scripts" / "script-historico.js").read_text(encoding="utf-8")
MIGRACAO = (RAIZ / "docs" / "migracao-rls-historico-evidencias.sql").read_text(encoding="utf-8")


def test_upload_nao_gera_url_publica():
    assert "getPublicUrl" not in ANALISE
    assert "const imagem_original = filePath;" in ANALISE


def test_upload_saneia_o_nome_do_arquivo():
    assert "nomeSeguro" in ANALISE
    assert "${Date.now()}_${arquivo.name}" not in ANALISE


def test_historico_exibe_por_url_assinada():
    assert "createSignedUrls" in HISTORICO
    assert 'src="${escaparHtml(item.imagem_original)}"' not in HISTORICO
    assert "item.resultado_img || item.imagem_original" not in HISTORICO


def test_historico_nao_poe_dado_cru_em_atributo():
    assert 'data-url="${item.imagem_original}"' not in HISTORICO
    assert 'data-id="${item.id}"' not in HISTORICO


def _extrair_funcao(fonte: str, nome: str) -> str:
    inicio = fonte.index(f"function {nome}(")
    profundidade, i = 0, fonte.index("{", inicio)
    while True:
        if fonte[i] == "{":
            profundidade += 1
        elif fonte[i] == "}":
            profundidade -= 1
            if profundidade == 0:
                return fonte[inicio : i + 1]
        i += 1


CASOS_CAMINHO = [
    # linha nova: já é o caminho
    ("uid-1/1700_foto.jpg", "uid-1/1700_foto.jpg"),
    # linha antiga: URL pública, nome com espaço e acento codificados
    ("https://x.supabase.co/storage/v1/object/public/evidencias/uid-1/17_f%C3%A9rias%20praia.jpg",
     "uid-1/17_férias praia.jpg"),
    # URL assinada colada por engano: descarta a query
    ("https://x.supabase.co/storage/v1/object/sign/evidencias/uid-1/a.png?token=abc", "uid-1/a.png"),
    # URL de outro lugar não vira caminho no bucket
    ("https://outro.site/imagem.jpg", ""),
    ("", ""),
    (None, ""),
]


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js não instalado")
def test_caminho_evidencia_em_node():
    funcao = _extrair_funcao(HISTORICO, "caminhoEvidencia")
    entradas = [c[0] for c in CASOS_CAMINHO]
    script = f"{funcao}\nconsole.log(JSON.stringify({json.dumps(entradas)}.map(caminhoEvidencia)));"
    saida = subprocess.run(["node", "-e", script], capture_output=True, text=True,
                           encoding="utf-8", check=True).stdout

    assert json.loads(saida) == [c[1] for c in CASOS_CAMINHO]


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js não instalado")
def test_nome_saneado_em_node():
    trecho = re.search(r"const nomeSeguro = (String\(arquivo\.name[\s\S]*?);", ANALISE).group(1)
    nomes = ["férias na praia #1.JPG", "../../etc/passwd", "a" * 200 + ".png", ""]
    script = (f"const r = {json.dumps(nomes)}.map(n => {{ const arquivo = {{name: n}}; "
              f"return {trecho}; }}); console.log(JSON.stringify(r));")
    saida = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True,
                                      encoding="utf-8", check=True).stdout)

    assert saida[0] == "ferias_na_praia_1.JPG"
    assert "/" not in saida[1]
    assert len(saida[2]) == 80 and saida[2].endswith(".png")
    assert saida[3] == "imagem"


def test_migracao_liga_rls_por_dono_e_fecha_o_bucket():
    sql = MIGRACAO.lower()
    assert "alter table public.historico_analises enable row level security" in sql
    assert "user_id::text = auth.uid()::text" in sql
    assert "update storage.buckets set public = false where id = 'evidencias'" in sql
    assert "(storage.foldername(name))[1] = auth.uid()::text" in sql
    assert "revoke all on public.historico_analises from anon" in sql


def test_migracao_nao_cria_politica_aberta():
    """Nenhuma política ativa (fora dos comentários) pode ser `using (true)`."""
    ativo = "\n".join(l for l in MIGRACAO.splitlines() if not l.strip().startswith("--"))
    assert not re.search(r"using\s*\(\s*true\s*\)", ativo, re.IGNORECASE)


PERFIL = (RAIZ / "scripts" / "script-perfil.js").read_text(encoding="utf-8")


def test_excluir_conta_apaga_dossies_forenses_antes_da_conta():
    """Sem isto o dossiê ficava acessível por link direto até o cache expirar (7 dias)."""
    corpo = PERFIL[PERFIL.index("async function excluirContaEDados"):]
    assert corpo.index("removerDossiesForenses(user.id)") < corpo.index('rpc("excluir_minha_conta")')
    assert 'method: "DELETE"' in PERFIL


def test_excluir_conta_pagina_as_evidencias():
    trecho = PERFIL[PERFIL.index("async function removerEvidenciasUsuario"):PERFIL.index("async function removerDossiesForenses")]
    assert "offset" in trecho and "pagina.length < 1000" in trecho
