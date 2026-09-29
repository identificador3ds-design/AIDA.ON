# AIDA Video — estado em 29/09/2026 e o que falta

> Continuação de `resultados-e-melhorias-video-2026-09.md`, que é de antes do treino do áudio e do
> modelo de movimento. Partes daquele documento estão superadas: o áudio já tem modelo
> (`random_forest base+videos_rf`) e o movimento (trajetória DINOv2 + mediana do Core) já decide.

## 1. O que está publicado hoje

Space `aidaon/aida-video` (commit `c981d07`):
- quadros → Core (`aidaon-aida-api`, versão R6fp6);
- movimento: `trajetoria.joblib` **antigo** (treinado com a escala do Core de agosto);
- áudio: `modelo_audio.joblib` (limiar 0,63, faixa inconclusiva 0,48–0,63);
- decisão pelas **regras fixas** de `agregacao.combinar`, sem a fusão ponderada.

Resultado nos 14 vídeos reais de teste (teste1–teste14, `VÍDEOS GATO`): **13 REAL, 1
INCONCLUSIVO (teste11), 0 falsos positivos.**

Nos 336 vídeos padronizados (166 reais, 170 IA de 10 geradores; validação deixando um gerador
de fora), com o Core R6fp6:

| | Regras (publicado) | Fusão ponderada (pendrive) |
|---|---|---|
| Reais acusados de IA | 12–13% | **4,2%** |
| IA detectada | 80–82% | 77,1% |
| Inconclusivos | 6–7% | 15,8% |
| Acerto nos decididos | 87,5% | 91,5% |
| AUC | – | 0,943 |

A fusão acusa um terço dos reais que as regras acusam, em troca de mais inconclusivos. No total
de acertos as regras ganham (McNemar p = 0,03), porque inconclusivo conta como não-acerto.

## 2. Correção do áudio na fusão (feita em 29/09)

**Sintoma.** A fusão classificava o teste11 (real) como IA, com 66%.

**Causa.** No modelo com áudio, o áudio tem o maior peso (coeficiente 1,97 por desvio-padrão,
contra 1,70 do movimento). No teste11 o áudio deu 0,640, **a 0,01 do limiar** (confiança
"baixa" no próprio `aida_audio`), e somou +1,63 ao logit, mais que imagem e movimento juntos
(que diziam real).

A hipótese anterior, de vazamento (o áudio treinado nos mesmos vídeos da fusão), estava errada: a
fusão já usa `resultados_audio/com_videos/previsoes.csv`, que são notas fora da amostra.

**Correção** (`aida_video/fusao.py`):
- `audio_utilizavel()`: áudio a menos de `MARGEM_AUDIO_INCERTO = 0,15` do limiar do modelo de
  áudio (0,48–0,78) fica de fora, tanto no treino quanto no uso; o vídeo vai para o modelo só de
  imagem e movimento, e o relatório explica o motivo;
- a margem é a mesma que o `aida_audio` já chama de confiança "baixa" (não foi ajustada nos
  dados). Nos 336 vídeos, 43 dos 240 com áudio caem nessa zona;
- modelo retreinado: `aida_video/modelos/fusao.joblib`, faixa inconclusiva 0,29–0,60;
- backup do anterior: `C:\aida_retreino_local\fusao_joblib_backup_2026-09-29.joblib`;
- testes novos em `testes/test_aida_video_fusao.py` (196 testes de vídeo/áudio passam).

Efeito: FP 4,8% → 4,2%, IA detectada 80,0% → 77,1%, e **teste11 passa a REAL**. Nos 14 reais:
13 REAL, 1 INCONCLUSIVO (teste10), 0 falsos positivos.

## 3. O que falta no vídeo

| # | Item | Estado | Depende de |
|---|---|---|---|
| 1 | **Publicar** fusão + `trajetoria.joblib` novo + ajuste de `agregacao.py` + integração em `analisar_video.py` no Space | Pronto no pendrive, passou no critério (0 FP nos 14; FP nos 336 menor que o publicado) | Decisão do grupo: menos falsos positivos vs. mais inconclusivos |
| 2 | Números da página `/video` | A página mostra ~78% / 6% FP / 6% inconclusivos; não batem com nenhuma das duas colunas acima | Item 1 (usar os números do que estiver publicado) |
| 3 | Vídeo → Forensics (link para o dossiê do quadro mais suspeito) | Não feito | — |
| 4 | Sora 2 | 41–53% detectado no vídeo, 12% no áudio | Vídeos Sora 2 **com áudio** para treino |
| 5 | Teste de vídeos reais fixo | Os 14 reais ainda não estão num teste automático | — |
| 6 | Conjunto externo novo | Os 336 foram usados para escolher regras e limiares; os números estão um pouco otimistas | Vídeos novos, nunca usados |
| 7 | Tempo de processamento | 1 a 30 min por vídeo no Space (CPU básica, fila) | Hardware do Space ou menos quadros |

## 4. Como reproduzir

```
cd AIDA.ON
python -m aida_video.fusao ../resultados_videos/padronizados_r6fp6 \
    --trajetoria C:/aida_retreino_local/trajetoria_padronizados \
    --audio "G:/Meu Drive/TCC/resultados_audio/com_videos/previsoes.csv" \
    --saida C:/aida_retreino_local/fusao_video_audiofix --salvar-modelo
```
