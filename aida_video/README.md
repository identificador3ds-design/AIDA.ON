# AIDA Video e AIDA Audio

```
video ─▶ extrair_frames ─▶ AIDA Core (POST /analisar, 1 frame por vez) ─▶ agregacao ─▶ relatorio
   └───▶ trilha de audio (16 kHz mono) ─▶ aida_audio ─────────────────────────┘
```

| Modulo | Papel |
|---|---|
| `aida_video/extrair_frames.py` | Etapa 02: seleciona frames (primeiro, cortes de cena, intervalo, sem duplicatas) e grava PNG + `manifesto.json` |
| `aida_video/analisadores.py` | Etapa 03: envia cada frame ao AIDA Core reduzido a 1024 px por LANCZOS (a mesma redução que o Core faz: mesmo resultado, ~5x mais rápido), com novas tentativas |
| `aida_video/agregacao.py` | Etapa 04: junta os resultados por frame (maioria, trechos continuos de IA) e combina com o audio |
| `aida_video/analisar_video.py` | Pipeline completo + linha de comando |
| `aida_video/avaliar_lote.py` | Avaliação de vídeos rotulados e calibração das regras de agregação |
| `aida_audio/carregar.py` | Le audio de qualquer arquivo (inclusive video) em mono 16 kHz |
| `aida_audio/caracteristicas.py` | MFCC, LFCC, deltas, espectrais e temporais (~200 numeros) |
| `aida_audio/modelo.py` | Gera a tabela do dataset, treina (Reg. Logistica x Random Forest) e mede EER |
| `aida_audio/analisar.py` | Analisa um audio; sem modelo treinado, devolve INCONCLUSIVO com as caracteristicas |

## Instalar e testar

```bash
pip install -r aida_video/requirements.txt
python -m pytest testes/test_aida_video.py testes/test_aida_audio.py
```

Os testes geram os videos e audios que usam; nao precisam de rede nem de arquivos no repositorio.

## Usar

```bash
# video completo contra o Core publico; guarda frames, audio.wav e relatorio.json
python -m aida_video video.mp4 --saida resultado/

# Core local
set AIDA_CORE_URL=http://localhost:7860
python -m aida_video video.mp4

# so extrair frames e audio, sem o Core
python -m aida_video video.mp4 --sem-core --saida resultado/

# audio avulso
python -m aida_audio.analisar audio.wav

# treinar o modelo de audio (pastas reais/ e ia/, subpastas por locutor ou gerador)
python -m aida_audio.modelo dataset_audio/ --processos 10

# o modelo que o site usa: MLS/MLAAD + trilhas dos videos, validado deixando um gerador de fora
python -m aida_audio.treinar_com_videos dataset_audio/caracteristicas_audio.csv ../videos_teste_padronizado     --cache-videos ../resultados_audio/caracteristicas_videos.csv --saida ../resultados_audio/com_videos
# (grava aida_audio/modelos/modelo_audio_com_videos.joblib; copie para modelo_audio.joblib se o FP servir)

# medir um modelo de audio nas trilhas dos videos
python -m aida_audio.avaliar_externo ../videos_teste_padronizado --modelo aida_audio/modelos/modelo_audio.joblib
```

## Avaliar um lote de vídeos (calibração)

```bash
python -m aida_video.avaliar_lote ../videos_teste --saida ../resultados_videos
```

`videos_teste/reais/` e `videos_teste/ia/`: o nome da pasta é o rótulo. Grava um relatório por vídeo
(e retoma de onde parou se for interrompido), `resumo_videos.csv`, `frames.csv` e `calibracao.json`.
Mostra a matriz de confusão, a acurácia nos vídeos decididos, os falsos positivos (real acusado de IA)
e a AUC por frame. `--so-calibrar` refaz as métricas e a busca de regras sem chamar o Core.

## Testar pelo site

A seção "Testar agora" de `pages/index-video.html` fala com o servidor do AIDA Video
(`aida_video/servidor.py`). São dois terminais, ambos na pasta `AIDA.ON`:

```bash
python -m aida_video.servidor          # http://127.0.0.1:7870
python -m http.server 8000             # site em http://localhost:8000/pages/index-video.html#testar
```

A análise de movimento (trajetória DINOv2, abaixo) precisa de `torch` + `timm`. O Python do sistema
não tem; use os pacotes do `.venv` do `aida_modelo` antes de subir o servidor (PowerShell):

```powershell
$env:PYTHONPATH = "D:\Escola\TCC\aida_modelo\.venv\Lib\site-packages"
python -m aida_video.servidor
```

Sem isso o servidor funciona, mas só com o voto dos frames; a página avisa
"análise de movimento desligada".

A página mostra o progresso frame a frame, a linha do tempo, os frames com o resultado de cada um,
o painel de áudio e permite baixar o relatório JSON. O endereço do servidor pode ser trocado em
"Endereço do servidor" ou por `?video_api=http://host:porta`.

No site publicado (aida-on.com.br) isso **não** funciona: a CSP do `vercel.json` só libera o Space
do Core em `connect-src`, e o navegador bloqueia chamadas para `127.0.0.1`. Para funcionar em
produção, o servidor de vídeo precisa ser publicado (ex.: junto do Core no Space) e o endereço dele
entrar na CSP.

Rotas do servidor:

| Rota | Descrição |
|---|---|
| `GET /video/saude` | status, URL do Core, se há modelo de áudio, limites |
| `POST /video/analisar` | campo `video` (multipart), `intervalo_s`, `max_frames`, `audio`; devolve `202 {"tarefa": id}` |
| `GET /video/tarefa/<id>` | estado (`extraindo`, `analisando`, `concluida`, `erro`), progresso, frames e relatório |
| `GET /video/tarefa/<id>/frame/<arquivo>` | miniatura JPEG (480 px) de um frame; `?tamanho=original` devolve o PNG cheio |

## Estados do resultado

Os mesmos tres do Core: `REAL`, `IA/MANIPULADA`, `INCONCLUSIVO`. Regra de `combinar`
(`agregacao.py`), com "imagem" = frames + movimento:

- imagem IA → IA;
- imagem INCONCLUSIVA → o áudio decide, se for conclusivo;
- imagem REAL e áudio IA com probabilidade ≥ 0,90 (`audio_ia_forte`) → IA (voz sintética sobre imagem real);
- imagem REAL e áudio IA mais fraco → INCONCLUSIVO (os dois discordam);
- imagem REAL e áudio REAL/inconclusivo → REAL.

O áudio não decide sozinho contra a imagem porque detecta só metade da IA; ele desempata.

## Modelo de áudio

`aida_audio/modelos/modelo_audio.joblib` = Random Forest sobre ~200 características, treinado com
4.800 áudios (2.400 MLS reais de 42 locutores × 2.400 MLAAD de 16 sistemas TTS) **mais** as trilhas
dos vídeos (163 reais de celular, 78 IA), com peso igual para os dois conjuntos. Limiar 0,63; faixa
inconclusiva 0,48–0,63 (`faixa_inconclusiva` no pacote).

| Áudio nas trilhas dos vídeos (fora da amostra, gerador de vídeo deixado de fora) | AUC | FP celulares | IA detectada |
|---|---|---|---|
| Só MLS/MLAAD (modelo rápido, 1.179 áudios) | 0,65 | 9,7% | 29% |
| Só MLS/MLAAD (completo, 4.800 áudios; EER 10,5% no próprio domínio) | 0,74 | **57%** | 69% |
| MLS/MLAAD + vídeos, RF (limiar validado de forma cruzada) | **0,92** | **1,2%** | 54% |

Por gerador (RF + vídeos): ltx2 70%, sora2 12%, veo31 47%, veo31fast 71%, wan26 76%.
Treinar com mais audiolivro piorou nos vídeos: o problema era domínio, não quantidade.

Efeito na conclusão do vídeo (336 vídeos padronizados, tudo fora da amostra):

| Regra | FP (reais) | IA detectada | Inconclusivos |
|---|---|---|---|
| Só imagem (frames + movimento) | 6,0% | 73% | 14% |
| Imagem + áudio (regra acima) | 6,0% | 78–79% | 6% |

## Movimento entre frames (trajetória DINOv2)

Depois dos frames, `analisar_video` roda `aida_video/trajetoria.py`: 24 frames seguidos viram
pontos no espaço do DINOv2 e a forma do caminho (distâncias e curvaturas, estilo ReStraV) vai
para uma LogReg junto com a mediana da probabilidade do Core (`aida_video/modelos/trajetoria.joblib`,
treinado com `python -m aida_video.treinar_trajetoria ... --salvar-modelo`).

Regra (`combinar_visual` em `agregacao.py`): IA pelo voto dos frames continua valendo; fora
isso, probabilidade ≥ 0,65 → IA, ≤ 0,35 → REAL, no meio → INCONCLUSIVO. Medido fora da amostra
(gerador deixado de fora, 336 vídeos padronizados em 480p): 14% inconclusivos; nos decididos,
86% da IA detectada e 6,9% de falso positivo. Só o voto dos frames: 11% e 0,6%.
Custa ~30 s por vídeo neste PC (Celeron). `--sem-trajetoria` desliga.

## Limitacoes atuais

- As regras de agregacao (`REGRAS_PADRAO`) sao heuristicas iniciais: precisam ser calibradas com
  videos reais e gerados (passo 1 da pesquisa em `docs/pesquisa-aida-video-audio.md`).
- O Core foi treinado com fotos. Frames de video sao mais comprimidos e borrados; medir quanto a
  acuracia cai e o passo 2 da pesquisa.
- O modelo de áudio viu os 250 vídeos com áudio no treino final: medir de novo nesses vídeos dá
  número otimista. Os números acima são da validação deixando um gerador de fora. Sora 2 continua
  difícil (12%). Voz clonada sobre vídeo real não está no dataset; a regra `audio_ia_forte` existe para
  esse caso, mas não foi medida.
- Frames vão ao Core 2 por vez (`--paralelo`, `AIDA_VIDEO_PARALELO`); cada um leva ~3,5 s no Space.
- O teste pelo site funciona só localmente (ver "Testar pelo site"); não há rota de vídeo na AIDA API `/v1`.
