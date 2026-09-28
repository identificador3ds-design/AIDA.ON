# Resultado da avaliação em escala (339 vídeos) e o que pode ser melhorado

> Setembro/2026. Continuação de `pesquisa-aida-video-audio.md` depois da primeira rodada real:
> 169 vídeos reais (celular, WhatsApp/apps, gravação de tela) + 170 vídeos de IA (10 geradores,
> [`aslhlf/Gen_videos`](https://huggingface.co/datasets/aslhlf/Gen_videos)), avaliados originais e
> padronizados (`COMO_RODAR_AVALIACAO_VIDEOS.md`).

---

## 1. Resultado

| Métrica | Originais (339) | Padronizados (337) |
|---|---|---|
| Acurácia nos decididos | 83,98% | 75,89% |
| Cobertura (não inconclusivo) | 68,14% | 66,47% |
| **Falsos positivos** | **6** | **1** |
| AUC por frame | 0,8555 | 0,8724 |
| Tempo total de processamento | 2,50 h | 1,24 h |

**Matriz — originais:**

| | previsto REAL | previsto IA | inconclusivo |
|---|---|---|---|
| REAL (169) | 132 | 6 | 31 |
| IA (170) | 31 | 62 | 77 |

**Matriz — padronizados:**

| | previsto REAL | previsto IA | inconclusivo |
|---|---|---|---|
| REAL (167*) | 151 | 1 | 15 |
| IA (170) | 53 | 19 | 98 |

\* 169 fontes − 2 colisões de nome (`.mov`/`.mp4` mesmo stem) na padronização.

Grade de calibração (81 combinações, `calibracao.json`): a melhor combinação nos padronizados
(`fracao_ia=0.4, fracao_real=0.6, sequencia_minima=4, fracao_trecho=0.1`) chega a **0 falsos
positivos com 70,6% de cobertura** — mas foi escolhida nos mesmos 337 vídeos que mede; precisa
confirmar num conjunto separado antes de virar padrão.

### Geradores mais difíceis (confirmado nas duas rodadas, consistente com o piloto de 20)

| Gerador | Classificado como REAL (originais) | Classificado como REAL (padronizados) |
|---|---|---|
| HunyuanVideo-1.5 | 9/17 | 10/17 |
| LTX-2 | 7/17 | 9/17 |
| Veo 3.1 | 1/17 | 7/17 |
| Wan 2.6 | 5/17 | 7/17 |
| Sora 2 | 5/17 | 6/17 |

Kling 2.6, FastWan e LongCat continuam os mais fáceis de pegar.

---

## 2. Diagnóstico: por que a acurácia é essa

### 2.1 O "resultado" hoje é 100% visual — o áudio nunca decide

`aida_audio/modelo.py` treina um classificador (LFCC/MFCC + espectrais + Random Forest ou
Regressão Logística, com EER) — mas **nenhum modelo foi treinado ainda** (não existe
`aida_audio/modelos/modelo_audio.joblib`). Sem pacote carregado, `analisar_amostras()`
(`aida_audio/analisar.py:68`) sempre devolve `INCONCLUSIVO`. Conferido nos dois CSVs: a coluna
`audio` é **252 INCONCLUSIVO + 87 vazio (sem trilha), 0 REAL, 0 IA** em 339 vídeos.

Como `combinar(visual, audio)` (`aida_video/agregacao.py:140`) só deixa o áudio virar o resultado
quando ele é `REAL` ou `IA/MANIPULADA`, isso significa que **a análise de áudio existe em código,
mas contribuiu zero para qualquer decisão até agora**. É o maior ganho "de graça" disponível: o
pipeline já está pronto, falta só dataset + treino (seção 3.2).

### 2.2 Sem modelagem temporal — cada frame é uma foto isolada

O Core (`analisadores.py`) recebe cada frame como imagem estática e aplica o mesmo modelo do AIDA
Image — AIDA-2.0: cabeça sobre embeddings CLIP (B3), classificador de características forenses
espectrais/textura/ruído/Benford (B2) e RIGID, a estabilidade do embedding CLIP sob ruído (B5),
fundidos por média calibrada com faixa de abstenção (`b4_politica.json`). Tudo treinado em
**fotos**, não em frames de vídeo. (O FFT+Benford + Random Forest é o modelo v1 de `aida_modelo/`,
que não roda mais em produção.) A agregação (`agregacao.py`) só olha `fração de frames IA`,
`fração REAL` e `sequência mínima consecutiva` — estatística sobre os votos, não o vídeo como
sinal contínuo. Nenhuma característica de movimento, fluxo óptico ou consistência entre frames
entra na decisão. Isso limita o teto: o AUC por frame (0,85–0,87) já é bom, mas a cobertura fica
baixa (66–68%) porque a agregação joga tudo que não é maioria clara para inconclusivo.

### 2.3 Formato/compressão ainda pesa nos originais

Os 6 falsos positivos dos originais **não são aleatórios**: 4 são `.mp4` com nome UUID (tipo
`DE6ED0A8-...`) em **1080x1920 HEVC** — mesmo pipeline de exportação, provavelmente de um app de
mensagens — e 2 são `.MOV` 4K nativos do iPhone. Um desses UUID (`DE6ED0A8-88EE-4058-8786-
018B9FF1EF88.mp4`) **continua borderline até depois de padronizar** (prob. mediana 0,74 → 0,51,
único falso positivo dos padronizados) — não é só artefato de contêiner, vale abrir esse vídeo
especificamente no dossiê forense do Core.

### 2.4 Padronizar troca falso positivo por cobertura

Confirma o piloto de 20 em escala: padronizar quase elimina falso positivo (6→1) mas derruba
cobertura de IA (62 decididos como IA → só 19), porque os limiares foram calibrados para fotos e
para os originais, não para clipes de 10s/480p. O AUC por frame não piora (0,855→0,872) — **o
sinal de IA continua lá**, só que a regra de decisão joga a maioria pra inconclusivo. Confirma a
hipótese do guia: uma regra própria para vídeo padronizado (limiar mais baixo / calibração
separada) provavelmente recupera cobertura sem voltar a ter falso positivo — é o que a melhor
combinação da grade já sugere (seção 1).

---

## 3. Pesquisa: o que a literatura de 2026 recomenda

### 3.1 Detecção de vídeo gerado por IA (não é a mesma tarefa que deepfake de rosto)

O AIDA detecta **vídeo inteiro gerado por T2V** (Sora, Veo, Kling…), não troca de rosto — a
literatura relevante é a de *AI-generated video detection*, não *face-swap deepfake*:

- **Métodos nativos de vídeo** (em vez de foto-a-foto): consistência entre frames (frame
  consistency), fluxo óptico/resíduo de movimento (GC-ConsFlow, dual-branch RGB+optical-flow),
  trajetória/velocidade de geração (**TRACE**) — capturam o "fervilhar" de textura e a física
  implausível que um classificador de foto isolada não vê. [GC-ConsFlow](https://arxiv.org/pdf/2501.13435),
  [Video Forgery Detection com fluxo óptico](https://arxiv.org/pdf/2508.00397),
  [TRACE](https://arxiv.org/html/2609.25775).
- **Consistência semântica vídeo↔prompt (CMTA)**: vídeo de IA mantém uma trajetória semântica
  "estável demais" com relação ao prompt (via embeddings CLIP/BLIP); vídeo real tem flutuação
  natural. Generaliza melhor entre geradores porque não depende de artefato específico de um
  modelo. [CMTA](https://arxiv.org/pdf/2605.00630).
- **Robustez a baixa resolução/recompressão — é justamente o nosso caso do "padronizado"**: a
  literatura confirma que resolução baixa e recompressão mascaram o rastro forense; abordagens
  recentes preservam artefato "em escala nativa" (ViT sem downsampling) ou usam representações de
  **trajetória/velocidade** (menos sensíveis a perda espacial que artefato de aparência).
  [Preserving Forgery Artifacts at Native Scale](https://arxiv.org/pdf/2604.04634),
  [Seeing What Matters](https://arxiv.org/html/2506.16802).
- **Falso positivo por compressão é um problema conhecido, não peculiaridade do AIDA**: "vídeos
  autênticos fortemente comprimidos retêm artefato de bloco que certos detectores tratam como
  evidência de geração" — bate exatamente com os 4 UUID HEVC da seção 2.3.
- Survey 2026 cobrindo imagem+vídeo+áudio com avaliação empírica de generalização:
  [Artificial Intelligence Review (Springer)](https://link.springer.com/article/10.1007/s10462-026-11608-4).

### 3.2 Áudio (reforça o que já estava em `pesquisa-aida-video-audio.md`, sem mudança de rumo)

Nada mudou na recomendação: **Abordagem A** (LFCC/MFCC + espectrais + Random Forest, já
implementada em `aida_audio/`) como linha de base, **Abordagem B** (WavLM/XLS-R congelado +
Regressão Logística) se sobrar tempo. O gargalo não é técnica, é **dataset rotulado** — nenhum
áudio real/IA em PT-BR foi montado ainda (seção 2.5 do doc anterior: In-the-Wild, MLAAD-pt,
Common Voice pt, TTS aberto pra gerar falso com consentimento da equipe).

### 3.3 Fusão áudio+vídeo — como outros projetos combinam os dois sinais

O `combinar()` atual é a fusão mais simples possível (OR: qualquer lado dizendo IA decide). A
literatura de 2026 vai além:

- **Cross-attention com gating adaptativo**: rede separada por modalidade (áudio: Res2Net;
  vídeo: 3D-CNN+atenção temporal) + atenção cruzada bidirecional que pondera cada modalidade pela
  confiança dela no clipe — 96,7% de acurácia, AUC 0,988, EER 3,3% no benchmark deles. Mais
  sofisticado do que o AIDA precisa agora, mas mostra o teto do que dá pra chegar combinando bem.
  [Cross-Attention Fusion](https://pmc.ncbi.nlm.nih.gov/articles/PMC13306650/).
- **Sincronia lábio↔áudio**: sinal forte em *face-swap*/reencenação (voz não bate com o
  movimento da boca) — **pouco aplicável ao AIDA hoje**, porque vídeo T2V gerado (Sora, Veo,
  Kling) muitas vezes não tem áudio, ou tem áudio gerado separadamente sem relação labial
  determinística. Vale revisitar se o AIDA passar a analisar vídeos com pessoa falando de fontes
  tipo deepfake de apresentador/entrevista.
- **PIVOT (verificação físico-causal áudio+vídeo)**: estima grandezas físicas a partir de áudio e
  vídeo juntos e verifica se batem com leis físicas plausíveis. Interessante pela explicabilidade,
  mas o resultado reportado (70–72% de acurácia) é **pior** do que a acurácia visual que o AIDA já
  tem (84–93% nos decididos) — não é prioridade agora.
  [PIVOT](https://arxiv.org/pdf/2609.15562).

**Conclusão da pesquisa de fusão**: o formato certo pro AIDA no curto prazo não é uma rede de
fusão nova — é treinar o áudio que já existe e, quando os dois tiverem sinal, trocar o OR de
`combinar()` por uma soma ponderada das probabilidades (ex.: `prob_final = w_video·prob_video +
w_audio·prob_audio`, pesos calibrados com os dados reais), simples e já dá a maior parte do ganho
que redes de atenção cruzada buscam.

---

## 4. Recomendações, em ordem de custo/benefício

| # | Ação | Por quê | Esforço |
|---|---|---|---|
| 1 | **Treinar `aida_audio`** com um mini-dataset (In-the-Wild/ASVspoof + MLAAD-pt + Common Voice pt + TTS próprio) | Código pronto, zero contribuição hoje; é o maior ganho por esforço mínimo | Médio (montar dataset) |
| 2 | **Calibração separada para vídeo padronizado** — usar a combinação da grade (`fracao_ia=0.4, sequencia_minima=3–4, fracao_trecho=0.1`) como regra default quando o vídeo é padronizado, e confirmar num conjunto separado antes de fixar | AUC não caiu (0,872), só a regra de decisão está jogando cobertura fora | Baixo (já tem os dados, é ajustar `REGRAS_PADRAO`) |
| 3 | **Investigar os 4 vídeos UUID 1080x1920 HEVC** (falso positivo nas duas rodadas, um deles resistente à padronização) | Pode ser um pipeline de exportação específico (app de mensagem) que precisa de tratamento à parte, não é ruído aleatório | Baixo (abrir no dossiê forense do Core) |
| 4 | **Adicionar 1–2 características temporais simples na agregação** (variância entre frames consecutivos, ou fluxo óptico resumido) antes de partir para redes de vídeo completas | Ganho incremental sem trocar a arquitetura; literatura confirma que "fervilhar" de textura é o sinal mais citado em vídeo de IA | Médio |
| 5 | **Combinação ponderada em vez de OR** em `combinar()`, assim que o áudio tiver modelo treinado | Aproxima o AIDA da abordagem de fusão da literatura sem precisar de rede de atenção cruzada | Baixo, depende do #1 |
| 6 | (Pesquisa futura, não implementar ainda) Explorar consistência semântica vídeo↔prompt (estilo CMTA) ou representações de trajetória (estilo TRACE) como um segundo classificador "nativo de vídeo", complementar ao Core de foto | Maior salto de acurácia potencial, mas exige modelo novo e dataset de treino — não é ajuste de calibração | Alto |

---

## Referências novas desta rodada

- [GC-ConsFlow — fluxo óptico + contexto global](https://arxiv.org/pdf/2501.13435)
- [Video Forgery Detection com resíduo de fluxo óptico](https://arxiv.org/pdf/2508.00397)
- [TRACE — trajetória/velocidade para detecção de vídeo de IA](https://arxiv.org/html/2609.25775)
- [CMTA — consistência semântica vídeo↔prompt (CLIP/BLIP)](https://arxiv.org/pdf/2605.00630)
- [Preserving Forgery Artifacts at Native Scale](https://arxiv.org/pdf/2604.04634)
- [Seeing What Matters — augmentação forense generalizável](https://arxiv.org/html/2506.16802)
- [Survey 2026 imagem+vídeo+áudio (Artificial Intelligence Review)](https://link.springer.com/article/10.1007/s10462-026-11608-4)
- [Cross-Attention Fusion áudio-vídeo com gating adaptativo](https://pmc.ncbi.nlm.nih.gov/articles/PMC13306650/)
- [PIVOT — verificação físico-causal áudio+vídeo](https://arxiv.org/pdf/2609.15562)
