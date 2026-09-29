# Pesquisa — AIDA Documents (29/09/2026)

Objetivo: detectar documentos (PDF e imagem de documento) adulterados ou gerados por IA,
enviados como prova em reembolso, sinistro, cancelamento ou cadastro. Mesmo contrato do resto
do AIDA: indício técnico explicável, três estados, nunca "prova".

## 1. Por que um módulo próprio

Os detectores de imagem não servem bem para documentos:

- **Fu et al. (2026)** mostram que detectores de imagem gerada por IA perdem mais de 7 pontos
  de AUC média em imagens de documento. O motivo: o artefato fica concentrado em poucas regiões
  (o fundo branco não carrega pista) e as regiões com muito texto são as mais informativas.
  Selecionar recortes guiados pela densidade de texto melhorou 9,6 pontos.
- **AIForge-Doc (2026)**: 4.061 recibos e formulários com trechos refeitos por inpainting
  (Gemini 2.5 Flash Image, Ideogram). O trecho alterado ocupa em mediana 0,92 % dos pixels.
  TruFor chega a AUC 0,751, o detector específico de documentos (DocTamper/DTD) a 0,563, e o
  GPT-4o a 0,509, ou seja, acaso.
- **Wu et al. (2026)**, com 3.066 recibos forjados pelo GPT-Image-2: inspetores humanos
  acertam 50,1 %, TruFor fica em 59,9 % de AUC e DocTamper em 58,5 %. Nas adulterações
  tradicionais os mesmos detectores voltam a 96,2 % e 85,2 %. A conclusão dos autores é que o
  inpainting por IA apaga as descontinuidades locais que esses detectores aprenderam a procurar.

Consequência para o AIDA: a análise de pixel sozinha não resolve documento. A primeira versão
aposta no que a IA de imagem **não** controla: a estrutura do arquivo e a coerência dos dados.

## 2. Camadas implementadas na v0 (`aida_documents/`)

### 2.1 Coerência de identificadores

Sistemas emissores nunca erram dígito verificador. Um CNPJ, CPF ou chave de acesso de 44
dígitos com DV errado é o indício mais barato e forte que existe. Na chave também conferimos
UF (tabela IBGE), mês, modelo (55, 65, 57...) e se o CNPJ do emitente embutido nela aparece
no documento. O CNPJ alfanumérico, em vigor desde julho de 2026, já é aceito.

Fundamento: **Artaud et al. (2018)**, no concurso *Find it!* (ICPR), com recibos franceses,
e o trabalho *Detecting Forged Receipts with Domain-Specific Ontology-Based Entities & Relations*
(ICDAR 2023), com entidades e relações de uma ontologia do domínio,
mostram que a checagem semântica do conteúdo (totais, datas, identificadores) complementa a
análise visual.

### 2.2 Estrutura do PDF

- **Revisões incrementais**: cada gravação "por cima" acrescenta xref e `%%EOF`, e o
  original continua no arquivo (Forensic Analysis of Residual Information in Adobe PDF Files,
  arXiv:2003.10546).
- **Assinatura digital**: bytes depois do `/ByteRange` significam alteração após a
  assinatura. **Mainka, Mladenov e Rohlmann (NDSS 2021)** mostram 16 de 29 visualizadores
  vulneráveis a *shadow attacks*, que trocam conteúdo sem invalidar a assinatura. Por isso a
  camada só aponta; a validade criptográfica fica com o Verificador ITI.
- **Produtor**: **Adhatarao e Lauradoux (IFIP SEC 2022)** identificam o software produtor
  pelo "estilo de código" do PDF (192 regras, 11 produtores, até 100 % de acerto em alguns).
  Na v0 usamos só os metadados Producer/Creator. O estilo de código é o próximo passo, porque
  metadado se apaga fácil.
- **Sem camada de texto**: um PDF de nota que é só imagem é print, foto ou montagem, não
  saída direta do emissor.
- **Subconjuntos de fonte duplicados**: um editor que acrescenta texto embute um segundo
  subconjunto da mesma fonte.

### 2.3 Lei de Benford nos valores

Primeiro dígito dos valores monetários comparado com `log10(1 + 1/d)`, com MSE, MAD e
qui-quadrado.

- **Nigrini**: faixas de MAD para o 1º dígito são 0,006, 0,012 e 0,015.
- **Goodman (2016, Significance)** e **Cerqueti e Lupi (2022)** alertam que os requisitos
  estatísticos quase nunca são cumpridos por quem quer um "detector automático de fraude", e
  que N pequeno e N muito grande quebram os testes clássicos.
- **Nosso teste confirmou isso.** Com N = 120 valores sorteados da própria Benford, o MAD
  médio é ~0,021, acima do corte de 0,015. Uma nota fiscal tem dezenas de valores. Por isso,
  no AIDA, Benford só pesa com N ≥ 50, com MAD > 0,015 **e** p < 0,01 no qui-quadrado, e o
  relatório mostra o MAD esperado ao acaso para aquele N.
- Em texto corrido (artigo, contrato) a distribuição foge de Benford sem haver fraude
  (MAD 0,087 num artigo). A v0 conta só números no formato `1.234,56`.

Leitura para o TCC: Benford serve para triagem de **lotes** (todas as notas de um mesmo
fornecedor, extratos longos). Para um documento isolado, as camadas 2.1 e 2.2 pesam mais.

## 3. Próximos passos (ordem sugerida)

| # | Passo | Por que | Custo |
|---|---|---|---|
| 1 | Montar `documentos_teste/{reais,ia}` e rodar `avaliar_lote` | Sem isso os pesos são chute. Reais: notas/recibos do grupo (anonimizar). IA: pedir o mesmo documento ao GPT-Image/Gemini e editar reais no iLovePDF/Word | 3–4 h |
| 2 | Coerência aritmética | soma dos itens = total, quantidade × unitário = valor, tributos. Uma IA erra conta com frequência | 3 h |
| 3 | OCR (Tesseract `por`) para PDF-imagem e foto | tira do INCONCLUSIVO os documentos fotografados; permite rodar 2.1 e 2.3 neles | 3 h + instalar Tesseract |
| 4 | Recortes guiados por texto → AIDA Image | recomendação direta de Fu et al.: mandar ao Core as regiões com mais texto, não o documento inteiro | 4 h |
| 5 | Estilo de código do PDF | ordem de objetos, espaços, formato do xref/ID: identifica o produtor mesmo sem metadado | 6 h |
| 6 | Consulta da chave na SEFAZ / QR Code NFC-e | confirma que a nota existe e bate valor e data. É a prova mais forte, mas depende de serviço externo | 4 h |
| 7 | Detector aprendido (DocTamper/DTD ou TruFor) | só depois de 1–4. Os benchmarks mostram que ele cai muito com inpainting por IA | máquina de casa |
| 8 | Proveniência C2PA | se o arquivo trouxer Content Credentials, mostrar a cadeia (o site já tem a página de proveniência) | 2 h |

## 4. Referências

- ARTAUD, C. et al. Find it! Fraud Detection Contest Report. In: 24th ICPR, 2018, p. 13–18.
- ADHATARAO, S.; LAURADOUX, C. Robust PDF Files Forensics Using Coding Style. IFIP SEC 2022. arXiv:2103.02702.
- CERQUETI, R.; LUPI, C. Severe testing of Benford's law. arXiv:2202.05237, 2022.
- FU, Z. et al. Beyond Natural Images: Rethinking AI-Generated Image Detection in Documents. arXiv:2609.14352, 2026.
- GOODMAN, W. The promises and pitfalls of Benford's law. Significance, v. 13, n. 3, 2016.
- MAINKA, C.; MLADENOV, V.; ROHLMANN, S. Shadow Attacks: Hiding and Replacing Content in Signed PDFs. NDSS 2021.
- NIGRINI, M. Benford's Law: Applications for Forensic Accounting, Auditing, and Fraud Detection. Wiley, 2012.
- QU, C. et al. Towards Robust Tampered Text Detection in Document Image: New Dataset and New Solution (DocTamper). CVPR 2023.
- WU, J. et al. When the Forger Is the Judge: GPT-Image-2 Cannot Recognize Its Own Faked Documents. arXiv:2604.25213, 2026.
- AIForge-Doc: A Benchmark for Detecting AI-Forged Document Tampering. arXiv:2602.20569, 2026.
- Forensic Analysis of Residual Information in Adobe PDF Files. arXiv:2003.10546.
- Detecting Forged Receipts with Domain-Specific Ontology-Based Entities & Relations. ICDAR 2023, LNCS 14188.
