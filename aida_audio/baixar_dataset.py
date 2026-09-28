"""Monta dataset_audio/ em portugues a partir de duas fontes publicas.

- **reais/**: Multilingual LibriSpeech, portugues, particoes dev+test+9_hours
  (`facebook/multilingual_librispeech`, CC BY 4.0, sem restricao). Audiolivros
  lidos por pessoas; uma subpasta por locutor (`mls_<id>`), que vira o GRUPO do
  `aida_audio.modelo` — o mesmo locutor nunca cai em treino e teste.
- **ia/**: MLAAD, portugues (`mueller91/MLAAD`, CC BY-NC 4.0). 16 sistemas TTS
  (XTTS, Bark, VITS, Qwen3-TTS, Fish, OpenAI TTS-1 HD...); uma subpasta por
  sistema, que vira o grupo — o teste mede sistemas que o treino nao viu.

As duas fontes leem texto de livros, o que evita que o modelo separe as
classes pelo ASSUNTO da fala.

O MLAAD e restrito: a conta precisa aceitar os termos em
https://huggingface.co/datasets/mueller91/MLAAD (aprovacao automatica) e o token
dela precisa estar em HF_TOKEN ou no `hf auth login`. Sem acesso, o script baixa
so os reais e avisa.

Uso (na pasta AIDA.ON):
    python -m aida_audio.baixar_dataset ../dataset_audio --por-sistema 150 --max-reais 2400
"""

from __future__ import annotations

import argparse
import io
import random
import sys
from pathlib import Path

REPO_MLS = "facebook/multilingual_librispeech"
ARQUIVOS_MLS = [
    "portuguese/dev-00000-of-00001.parquet",
    "portuguese/test-00000-of-00001.parquet",
    "portuguese/9_hours-00000-of-00001.parquet",
]
REPO_MLAAD = "mueller91/MLAAD"
PASTA_MLAAD_PT = "fake/pt"


def baixar_reais(destino, max_arquivos, semente=0, avisar=print):
    import pyarrow.parquet as pq
    from huggingface_hub import hf_hub_download

    pasta = Path(destino) / "reais"
    linhas = []
    for nome in ARQUIVOS_MLS:
        caminho = hf_hub_download(REPO_MLS, nome, repo_type="dataset")
        tabela = pq.read_table(caminho, columns=["audio", "speaker_id", "id"]).to_pylist()
        linhas += tabela
        avisar(f"MLS {nome}: {len(tabela)} falas")
    random.Random(semente).shuffle(linhas)
    gravados = 0
    for linha in linhas[:max_arquivos]:
        audio = linha["audio"]
        extensao = Path(audio.get("path") or "x.flac").suffix or ".flac"
        saida = pasta / f"mls_{linha['speaker_id']}" / f"{linha['id']}{extensao}"
        if not saida.is_file():
            saida.parent.mkdir(parents=True, exist_ok=True)
            saida.write_bytes(audio["bytes"])
        gravados += 1
    locutores = len({l["speaker_id"] for l in linhas[:max_arquivos]})
    avisar(f"reais: {gravados} arquivos de {locutores} locutores em {pasta}")
    return gravados


def baixar_ia(destino, por_sistema, semente=0, avisar=print):
    from huggingface_hub import HfApi, hf_hub_download
    from huggingface_hub.errors import GatedRepoError, HfHubHTTPError

    api = HfApi()
    pasta = Path(destino) / "ia"
    try:
        arquivos = [a for a in api.list_repo_files(REPO_MLAAD, repo_type="dataset")
                    if a.startswith(PASTA_MLAAD_PT + "/") and a.lower().endswith((".wav", ".mp3", ".flac"))]
    except (GatedRepoError, HfHubHTTPError) as exc:
        avisar(f"MLAAD inacessível ({type(exc).__name__}). Aceite os termos em "
               f"https://huggingface.co/datasets/{REPO_MLAAD} com a conta do token e rode de novo.")
        return 0
    por = {}
    for a in arquivos:
        por.setdefault(a.split("/")[2], []).append(a)
    rng = random.Random(semente)
    total = 0
    for sistema, lista in sorted(por.items()):
        rng.shuffle(lista)
        grupo = "".join(c if c.isalnum() or c in "-_." else "_" for c in sistema)
        for remoto in lista[:por_sistema]:
            saida = pasta / grupo / Path(remoto).name
            if not saida.is_file():
                try:
                    local = hf_hub_download(REPO_MLAAD, remoto, repo_type="dataset")
                except (GatedRepoError, HfHubHTTPError) as exc:
                    # A listagem de arquivos passa mesmo sem acesso; o download e que e barrado.
                    avisar(f"MLAAD inacessível ({type(exc).__name__}). Aceite os termos em "
                           f"https://huggingface.co/datasets/{REPO_MLAAD} com a conta do token e rode de novo.")
                    return total
                saida.parent.mkdir(parents=True, exist_ok=True)
                saida.write_bytes(Path(local).read_bytes())
            total += 1
        avisar(f"ia/{grupo}: {min(len(lista), por_sistema)} arquivos")
    return total


def main(argv=None):
    parser = argparse.ArgumentParser(description="Baixa reais (MLS pt) e IA (MLAAD pt) para dataset_audio/.")
    parser.add_argument("destino", type=Path)
    parser.add_argument("--por-sistema", type=int, default=150, help="arquivos por sistema TTS do MLAAD")
    parser.add_argument("--max-reais", type=int, default=2400)
    parser.add_argument("--so-reais", action="store_true")
    args = parser.parse_args(argv)
    reais = baixar_reais(args.destino, args.max_reais)
    ia = 0 if args.so_reais else baixar_ia(args.destino, args.por_sistema)
    print(f"\nPronto: {reais} reais, {ia} IA. Treine com: python -m aida_audio.modelo {args.destino}")
    return 0 if reais and (ia or args.so_reais) else 1


if __name__ == "__main__":
    sys.exit(main())
