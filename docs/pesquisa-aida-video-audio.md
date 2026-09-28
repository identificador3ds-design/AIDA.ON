# Pesquisa inicial: AIDA Video e AIDA Audio

> Documento de partida (setembro/2026). Objetivo: levantar **como separar frames de vídeo**
> para alimentar o AIDA Core e **como detectar áudio sintético**, com uma recomendação de por onde
> começar em cada frente. Nada aqui foi validado com dados reais ainda.

---

## 0. Onde o projeto está hoje

| Vertente | O que existe | O que falta |
|---|---|---|
| **AIDA Video** | Página conceitual (`pages/index-video.html`) com o pipeline planejado: upload → extração de frames → análise por frame no Core → agregação temporal → Forensics. Frames de demonstração em `assets/demos/video/`. | Qualquer código. Protótipo da etapa 02 criado agora em `aida_video/extrair_frames.py`. |
| **AIDA Audio** | Só uma linha no roadmap do `README.md`. | Tudo: escolha de features, dataset, modelo, API. |

Ponto importante da arquitetura atual: o AIDA Image usa **features manuais** (FFT + Benford, gradientes/textura,
LSB, Laplaciano/DoG/TSR) + **Random Forest / Regressão Logística** (`aida_modelo/`). Essa mesma receita
serve de linha de base para o áudio (seção 2.3), o que deixa as duas vertentes comparáveis no TCC.

Peças já prontas fora deste repositório (ver `../aida-space/docs/arquitetura.md`, seções 5.3 e 13):

- o Core já tem um **cache indexado por conteúdo** (`sha256 -> id_analise`), criado justamente para o
  AIDA Video: frames idênticos enviados duas vezes não precisam ser reanalisados;
- o **dossiê forense** do Core já abre qualquer imagem; cada frame selecionado pode abrir nele sem código novo.

O ambiente `../aida_modelo/.venv` já tem `torch` e `torchvision` (CPU). Para a Abordagem B do áudio
(seção 2.4) faltam só `torchaudio`/`transformers` (ou `librosa` para a Abordagem A).

---

## 1. AIDA Video — como separar os frames

### 1.1 Conceitos que mudam a implementação

- **Container ≠ codec.** `.mp4`, `.mkv`, `.mov`, `.webm` são containers; dentro deles o vídeo está em
  H.264, H.265/HEVC, VP9, AV1… É o codec que precisa ser decodificado para obter os frames.
- **Tipos de frame (GOP).** *I-frames* (keyframes) são imagens completas; *P/B-frames* guardam só
  diferenças em relação a outros quadros. Não dá para "recortar" um P-frame do arquivo: ele precisa
  ser decodificado a partir do I-frame anterior. Por isso extrair um frame no meio do vídeo custa
  mais do que extrair um keyframe.
- **Taxa de quadros variável (VFR).** Vídeo de celular e de tela gravada costuma ser VFR. O tempo de um
  frame deve vir do **PTS** (presentation timestamp) do container, e não de `índice / fps` — senão o
  frame fica desalinhado com o áudio e com a linha do tempo mostrada ao usuário.
- **Rotação.** Celulares gravam o vídeo "deitado" e marcam a rotação nos metadados. Alguns leitores
  aplicam, outros não; é preciso conferir.
- **Todo frame de vídeo já é uma imagem com compressão com perdas.** Esse é o ponto mais importante
  para o AIDA: a compressão de vídeo (quantização DCT em blocos, deblocking, predição entre quadros)
  **altera justamente os sinais que o AIDA Image mede** — espectro de frequência, estatística de
  Benford nos coeficientes e ruído fino. Consequências:
  - o método **LSB praticamente perde o sentido** em frames de vídeo;
  - o modelo treinado em fotos **não deve ser reaproveitado sem reavaliação**; o ideal é treinar/calibrar
    com frames extraídos de vídeos reais e de vídeos gerados (Sora, Veo, Kling, Runway etc.);
  - os frames extraídos devem ser salvos em **PNG** (sem perda). Salvar em JPEG adiciona uma segunda
    compressão por cima da do vídeo.

### 1.2 Ferramentas

| Ferramenta | Pontos fortes | Pontos fracos | Uso sugerido no AIDA |
|---|---|---|---|
| **OpenCV** (`cv2.VideoCapture`) | Já é dependência do projeto; API simples. | Timestamps menos confiáveis em VFR; não lê áudio; pouco controle do decodificador. | Protótipo (é o que `extrair_frames.py` usa). |
| **FFmpeg / ffprobe** (CLI) | Referência da indústria; lê qualquer formato; filtros prontos (`fps`, `select`, cena, só keyframes); extrai o áudio. | É um processo externo; precisa estar instalado no servidor. | Validação/metadados (`ffprobe`) e extração do áudio para o AIDA Audio. |
| **PyAV** (`import av`) | Binding Python direto das bibliotecas do FFmpeg; PTS exato; lê vídeo **e** áudio no mesmo arquivo; permite decodificar só keyframes. | API mais baixa, um pouco mais verbosa. | **Recomendado para a versão de produção.** |
| **PySceneDetect** | Detectores de corte prontos (content, adaptive, threshold); CLI e API; backends OpenCV e PyAV. | Só resolve cortes, não a amostragem toda. | Substituir o detector de corte caseiro quando precisar de mais precisão. |
| **decord / torchcodec** | Acesso aleatório rápido a frames, pensado para treino de redes. | Instalação mais chata no Windows; decord com manutenção lenta. | Só se o treino de um modelo de vídeo exigir. |

Nenhuma dessas ferramentas está instalada no ambiente local hoje (nem `ffmpeg`, nem `av`); o OpenCV
existe em `../aida_modelo_deps`.

### 1.3 Estratégias de amostragem

Um vídeo de 1 minuto a 30 fps tem 1.800 frames, a maioria quase idêntica. Opções:

1. **Uniforme por tempo** — 1 frame a cada N segundos (`fps=1` no FFmpeg). Simples e com cobertura
   previsível; perde eventos curtos.
2. **Só keyframes (I-frames)** — rapidíssimo, porque não decodifica P/B. Mas o encoder decide onde
   eles caem (pode ser a cada 2 s ou a cada 10 s) e, em conteúdo de plataforma, o intervalo é irregular.
3. **Por corte de cena** — pega um frame por plano. Bom para vídeo editado, ruim para plano-sequência.
4. **Deduplicação** — descarta frames quase iguais ao último salvo (diferença de miniaturas ou hash
   perceptual).
5. **Híbrida (recomendada)** — uniforme + corte de cena + deduplicação. É o que o protótipo faz e é o que
   a página do AIDA Video já descreve ("amostragem por intervalo e nos cortes de cena, para não analisar
   mil quadros iguais").

Para o futuro: em deepfakes de rosto, a manipulação fica na região da face — vale detectar rostos
(ex.: MediaPipe, RetinaFace) e analisar também o **recorte da face**, não só o quadro inteiro.

### 1.4 Comandos de referência (FFmpeg)

```bash
# Metadados do arquivo (codec, fps, duração, rotação) em JSON
ffprobe -v error -show_format -show_streams -of json video.mp4

# 1 frame por segundo, em PNG
ffmpeg -i video.mp4 -vf fps=1 frames/f_%04d.png

# Só keyframes (não decodifica P/B: muito mais rápido)
ffmpeg -skip_frame nokey -i video.mp4 -fps_mode vfr frames/key_%04d.png

# Frames onde a cena muda mais de 30%
ffmpeg -i video.mp4 -vf "select='gt(scene,0.3)'" -fps_mode vfr frames/cena_%04d.png

# Extrair o áudio já no formato usado pelos modelos de áudio (mono, 16 kHz, WAV)
ffmpeg -i video.mp4 -vn -ac 1 -ar 16000 audio.wav
```

Equivalente em PyAV (esqueleto):

```python
import av

with av.open("video.mp4") as container:
    stream = container.streams.video[0]
    stream.codec_context.skip_frame = "NONKEY"   # opcional: só keyframes
    for frame in container.decode(stream):
        tempo_s = float(frame.pts * stream.time_base)
        imagem = frame.to_ndarray(format="rgb24")  # numpy HxWx3
```

### 1.5 Protótipo criado: `aida_video/extrair_frames.py`

```bash
python aida_video/extrair_frames.py video.mp4 --intervalo 1 --max-frames 120
```

- Lê com OpenCV, olha ~5 quadros por segundo (os outros só são pulados com `grab()`, sem conversão).
- Salva o frame se: é o primeiro, **ou** houve corte de cena (distância Bhattacharyya entre histogramas
  HSV ≥ 0,5), **ou** passou o intervalo **e** a miniatura 64×36 em cinza mudou (diferença média ≥ 2).
- Usa o tempo do container (`CAP_PROP_POS_MSEC`), salva PNG e gera `manifesto.json` com tempo, índice,
  motivo da seleção e as distâncias — a base para a Etapa 04 (agregação temporal).

Teste com vídeo sintético de 10 s (3 cenas: bola em movimento, cena parada, ruído): 6 frames salvos de
300 — 4 na cena com movimento, 1 na parada (duplicatas descartadas), 1 no corte da terceira cena.
Primeira versão usava dHash de 64 bits na deduplicação e **descartava** a cena com movimento (objeto
pequeno em fundo liso muda poucos bits); por isso a troca para diferença de miniaturas.

**Atualização:** a leitura migrou para PyAV (tempo pelo PTS, rotação de celular, caminhos com acento
no Windows) e o pipeline completo foi implementado — frames → AIDA Core → agregação temporal, mais a
trilha de áudio passando pelo `aida_audio` (características LFCC/MFCC, treino com EER, análise). Ver
`aida_video/README.md`. Testes: `testes/test_aida_video.py` e `testes/test_aida_audio.py`.

**Ainda falta:** testar com vídeos reais (celular, WhatsApp, YouTube, vídeos gerados), calibrar os
limiares de seleção e as regras de agregação, e treinar o modelo de áudio com um dataset real.

### 1.6 Além do frame a frame (pesquisa futura)

A análise frame a frame não enxerga o **tempo**. Sinais próprios de vídeo gerado:
inconsistência temporal (texturas que "fervem", objetos que mudam de forma), fluxo óptico incoerente,
cintilação (*flicker*), física implausível e, em deepfake de rosto, **dessincronia labial** entre boca e
áudio. A agregação temporal do AIDA pode começar simples (média, mediana, máximo, % de frames acima do
limiar, desvio padrão) e depois incorporar essas medidas.

---

## 2. AIDA Audio — como detectar áudio sintético

### 2.1 Como áudio falso é produzido

- **TTS (text-to-speech):** gera fala a partir de texto; com *voice cloning* imita uma pessoa a partir de
  poucos segundos de amostra.
- **Conversão de voz (VC):** transforma a fala de uma pessoa na voz de outra.
- Tecnicamente, a maioria passa por um **vocoder neural** (HiFi-GAN e similares) ou por **codecs neurais**
  (modelos de linguagem sobre tokens de áudio). Cada família deixa assinaturas diferentes.

### 2.2 Onde ficam os indícios

- **Faixas de alta frequência:** vocoders costumam reproduzir mal acima de ~4–8 kHz (energia estranha,
  cortes, padrões periódicos no espectrograma).
- **Fase:** muitos modelos geram magnitude bem e fase mal; features só de magnitude (MFCC) perdem isso.
- **Prosódia e fisiologia:** entonação "lisa" demais, ausência ou excesso de respiração, pausas
  regulares, jitter/shimmer (micro-variações de pitch e amplitude) fora do padrão humano.
- **Ambiente:** falta de reverberação/ruído de fundo coerentes, ou ruído de fundo "limpo" demais.

⚠️ **Armadilha conhecida — o silêncio.** No ASVspoof 2019, a duração do silêncio no começo/fim dos
arquivos já separava real de falso; modelos aprenderam o silêncio, não a voz. **Remover silêncio das
bordas antes de treinar** e testar se o modelo ainda funciona.

### 2.3 Abordagem A — features manuais + ML clássico (linha de base, mesma receita do AIDA Image)

Extrair por arquivo (ou por janela de ~4 s) e reaproveitar a estrutura `gerar_csv.py` → `treinar_ml.py`:

| Grupo | Features | Biblioteca |
|---|---|---|
| Cepstrais | **LFCC** (costuma superar MFCC em anti-spoofing por dar peso igual às altas frequências), MFCC, CQCC; média, desvio e deltas | `librosa`, `torchaudio`, `spafe` |
| Espectrais | centroide, *rolloff*, *flatness*, largura de banda, contraste, energia por faixa (principalmente > 4 kHz) | `librosa` |
| Temporais | taxa de cruzamento por zero, RMS, proporção de silêncio | `librosa` |
| Voz | F0 (média/desvio), jitter, shimmer, HNR | `praat-parselmouth` |

Modelos: Random Forest, Regressão Logística, XGBoost ou GMM (o GMM com LFCC é a *baseline* oficial
histórica do ASVspoof). Vantagem: rápido, explicável, roda em CPU, conversa com o que o TCC já tem.
Desvantagem: generaliza mal para geradores novos.

### 2.4 Abordagem B — modelos de deep learning (estado da arte)

- **RawNet2** e **AASIST / AASIST-L**: redes que recebem a forma de onda crua; AASIST usa atenção em
  grafo sobre o espectro e o tempo. AASIST-L é a versão leve.
- **Modelos auto-supervisionados como extratores (SSL):** **wav2vec 2.0 / XLS-R**, **WavLM**, HuBERT.
  O modelo pré-treinado gera *embeddings* e um classificador pequeno em cima (ou AASIST) decide.
  Combinações XLS-R + AASIST ou XLS-R + classificadores leves estão no topo dos benchmarks atuais.
- **Caminho barato e forte para o TCC:** congelar o WavLM ou XLS-R, extrair a média dos embeddings de
  cada áudio e treinar uma **Regressão Logística / MLP** — dá pra fazer em CPU/Colab e costuma ser muito
  melhor que features manuais. Depois, se houver GPU, fazer *fine-tuning*.

### 2.5 Datasets

| Dataset | O que é | Observação |
|---|---|---|
| **ASVspoof 2019 LA / 2021 LA e DF** | Benchmarks clássicos de anti-spoofing (inglês). | Cuidado com o viés de silêncio. |
| **ASVspoof 5** | Edição mais recente: dados *crowdsourced*, mais ataques e ataques adversariais. | Referência atual. |
| **In-the-Wild** | Áudios reais e falsos de figuras públicas, coletados da internet. | Ótimo para medir **generalização** (modelos que vão bem no ASVspoof caem muito aqui). |
| **MLAAD** | Áudio sintético em ~40 línguas, gerado por 100+ modelos TTS; no Hugging Face. | Licença CC-BY-NC (uso acadêmico); conferir o subconjunto em português. |
| **Fala real em PT-BR** | Mozilla Common Voice (pt), CORAA, MLS Portuguese. | Para compor o lado "real" em português. |
| **Dados próprios** | Gerar falsos com TTS abertos (XTTS, Piper, F5-TTS…) a partir de vozes **da própria equipe, com consentimento**. | Resolve a falta de PT-BR e permite testar "gerador nunca visto". |

### 2.6 Pré-processamento e avaliação

- Converter tudo para **mono, 16 kHz, WAV**; normalizar volume; cortar silêncio das bordas.
- Janelas fixas (~4 s, como no AASIST) e **agregação dos scores por janela** — a mesma ideia de
  agregação temporal do AIDA Video; dá para mostrar em que trecho do áudio o indício é mais forte.
- **Métrica padrão: EER** (*Equal Error Rate*), além de F1/precisão/recall já usados no AIDA Image.
- **Divisão treino/teste por locutor e por gerador**, nunca aleatória por arquivo; testar um gerador que
  ficou fora do treino (*leave-one-generator-out*).
- **Robustez:** avaliar depois de passar por MP3, Opus (WhatsApp) e banda telefônica. *Data augmentation*
  (RawBoost, ruído, reverberação, recompressão) é o que mais ajuda aqui.

### 2.7 Limitações a declarar

Mesmo espírito do README: resultado probabilístico, geradores evoluem rápido, compressão de mensageiros
apaga indícios, e detecção de voz clonada **não** substitui verificação de identidade do locutor.

---

## 3. Próximos passos sugeridos

**Video**
1. Juntar ~20 vídeos reais (celular, WhatsApp, YouTube) e ~20 gerados; rodar `extrair_frames.py` e
   calibrar os limiares.
2. Passar os frames pelo AIDA Core atual e medir **quanto a acurácia cai** em relação às fotos — isso
   responde se é preciso retreinar com frames.
3. Implementar a agregação temporal simples (média, máximo, % acima do limiar) sobre o `manifesto.json`.
4. Migrar a leitura para PyAV e extrair o áudio no mesmo passo.

**Audio**
1. Montar um mini-dataset: In-the-Wild (ou subconjunto do ASVspoof 2019 LA) + MLAAD em português +
   Common Voice pt.
2. Baseline A: LFCC/MFCC + espectrais → CSV → Random Forest (reaproveitando `treinar_ml.py`); medir EER.
3. Baseline B: embeddings WavLM/XLS-R congelados + Regressão Logística; comparar com A.
4. Testar robustez com recompressão Opus/MP3 e com um gerador fora do treino.

---

## Referências

- Survey geral — *Audio Deepfake Detection: A Survey*: https://arxiv.org/pdf/2308.14970
- XLS-R + SLS (ACM MM 2024): https://dl.acm.org/doi/abs/10.1145/3664647.3681345
- WavLM + Multi-Fusion Attentive Classifier: https://arxiv.org/pdf/2312.08089
- Detecção frente a TTS recentes (2026): https://arxiv.org/html/2601.20510v1
- Detecção leve em navegador com SSL (2026): https://arxiv.org/pdf/2606.30780
- Fraunhofer AISEC — trabalhos relacionados: https://deepfake-demo.aisec.fraunhofer.de/related_work/
- MLAAD (artigo): https://arxiv.org/abs/2401.09512 — dataset: https://huggingface.co/datasets/mueller91/MLAAD
- AASIST (código oficial): https://github.com/clovaai/aasist
- ASVspoof: https://www.asvspoof.org/
- PySceneDetect: https://github.com/Breakthrough/PySceneDetect — docs: https://www.scenedetect.com/docs/latest/
- PyAV: https://pyav.basswood-io.com/
- Filtros do FFmpeg (`fps`, `select`, `scene`): https://ffmpeg.org/ffmpeg-filters.html
