# AIDA Documents

Triagem de documentos enviados como prova (nota fiscal, recibo, comprovante, boleto, laudo,
trabalho escolar) em **PDF, DOCX, DOC, TXT ou MD**.
Devolve os mesmos três estados do AIDA Core: `REAL`, `IA/MANIPULADA` e `INCONCLUSIVO`.
Não usa rede neural: cada indício é explicável e tem um peso. A pesquisa que embasa o
módulo e os próximos passos está em [`docs/pesquisa-aida-documents.md`](../docs/pesquisa-aida-documents.md).

```bash
python -m aida_documents.analisar nota.pdf
python -m aida_documents.avaliar_lote "G:/Meu Drive/TCC/documentos_teste" --saida resultado.csv
python -m aida_documents.treinar "G:/Meu Drive/DOCS GATO/lote" --saida estudo_documentos
python -m pytest testes/test_aida_documents.py testes/test_aida_documents_treino.py
```

Dependências: `pypdf` e `numpy` (já estão no projeto). `reportlab` só nos testes.
`treinar.py` usa `scikit-learn` e `joblib` (estão em `aida_video/requirements.txt`).

## Camadas

| Camada | Arquivo | O que procura | Peso |
|---|---|---|---|
| Formatos | `office.py`, `texto_puro.py` | ver a tabela "Outros formatos" abaixo | — |
| Credencial C2PA | `proveniencia.py` | manifesto C2PA embutido que declara origem por IA (`trainedAlgorithmicMedia`), com gerador e modelo; a assinatura não é verificada | 0,80 |
| Identificadores | `numeros.py` | DV de CNPJ (inclusive o alfanumérico), CPF e chave de acesso NF-e/NFC-e; UF, mês e modelo da chave; CNPJ do emitente da chave presente no documento. Um DV errado sozinho fica `INCONCLUSIVO`; dois ou mais somam até `IA/MANIPULADA`; poucos errados (até 10 %) entre 10 ou mais identificadores contam como digitação (0,30, uma vez) | 0,45 |
| Assinatura | `estrutura.py` | bytes acrescentados depois do trecho coberto pelo `/ByteRange` (0,50); assinatura copiada de outro PDF, cujo `/ByteRange` não termina em nenhum `%%EOF` deste arquivo (0,15) | 0,50 / 0,15 |
| Sem camada de texto | `estrutura.py` | páginas só com imagem (print, foto, montagem) | 0,35 / 0,20 |
| Revisões incrementais | `estrutura.py` | seções `%%EOF` com objetos novos (ignora o trailer vazio do Word e a linearização) | 0,30 |
| Ferramenta | `estrutura.py` | Producer/Creator de editor online ou de imagem (0,30), biblioteca de programação como ReportLab/FPDF/jsPDF (0,15), escritório ou impressora virtual (0,10) | 0,30 / 0,15 / 0,10 |
| Fontes | `estrutura.py` | a mesma fonte embutida em dois subconjuntos do mesmo tipo (`ABCDEF+Arial` e `GHIJKL+Arial`, ambas TrueType) | 0,30 |
| Benford | `benford.py` | 1º dígito dos valores monetários (`1.234,56`); MSE, MAD de Nigrini e qui-quadrado | 0,25 / 0,35 |
| Datas | `estrutura.py` | modificação mais de 1 dia depois da criação | 0,15 |

Suspeita combinada = `1 − ∏(1 − peso)`. `IA/MANIPULADA` a partir de 0,60. `REAL` só abaixo
de 0,25 **e** com prova de origem (assinatura digital intacta ou chave de acesso de NF-e
válida) e texto nativo em todas as páginas. O resto é `INCONCLUSIVO`, com o motivo.

DV certo não é prova de nada: geradores de CNPJ/CPF acertam o dígito. Só o DV errado é
indício. Um orçamento fictício gerado com ReportLab (29/09) saiu `REAL` na primeira versão
por causa disso; agora sai `INCONCLUSIVO`, com o indício fraco "biblioteca de programação".

## Outros formatos (DOCX, DOC, TXT)

O formato é reconhecido pelo conteúdo (`%PDF`, ZIP, OLE), não pela extensão. Nenhum deles
chega a `REAL`: um arquivo editável qualquer pessoa escreve, com a chave de NF-e que quiser.

| Formato | O que é lido | Indícios próprios | Peso |
|---|---|---|---|
| DOCX | core.xml, app.xml (minutos de edição, contagem de palavras), sessões `w:rsidR`, texto, macros, `META-INF/*.c2pa` | contagem de palavras zerada com texto; python-docx (autor, descrição, criação em 23/12/2013). O tempo de edição só informa (ver abaixo) | 0,15 / 0,15 |
| DOC | só metadados, com `olefile` (programa, datas, tempo de edição, macros) | — | — |
| TXT | texto (UTF-8, UTF-16 ou Latin-1) | caracteres invisíveis (largura zero, tags); manifesto C2PA em seletores de variação (experimental) | 0,15 / 0,80 |

Em DOCX, DOC e TXT o DV errado pesa 0,30 (`dv_invalido_digitado`), e não 0,60: num
arquivo digitado pode ser erro de digitação. O ML (`caracteristicas.py`, `treinar.py`)
continua só para PDF.

## Reais de bancos públicos (19/10)

`python -m aida_documents.baixar_amostras napierone --tamanho tiny` baixa ~100 arquivos
reais por formato do NapierOne (S3 público); `... essaybr --quantidade 200` grava redações
da Essay-BR como `.txt`. Cada arquivo ganha uma linha em `origem.csv` (fonte e licença).
`... pncp --inicio AAAAMMDD --fim AAAAMMDD` baixa editais e contratos do PNCP (um por órgão)
e `... safedocs --dominio br` baixa PDFs de sites .br de 2021, lendo os ZIPs de 1,3 GB por
faixas (só o índice e os PDFs escolhidos).

Primeiro teste com 400 reais do NapierOne (100 de cada formato):

- **5 falsos positivos em 100 PDFs**, todos por indícios contados em dobro: 4 PDFs do
  Photoshop (editor de imagem + página só imagem, mesma causa) e 1 do InDesign (cada fonte
  duplicada somava 0,30). Agora cada causa conta uma vez: 0 falsos positivos. Esse 0 foi
  ajustado nesses mesmos arquivos; o número honesto sai do conjunto "small", ainda não usado.
- **"Texto colado" saiu da conta.** 67 de 100 .docx reais tinham até 2 min de edição com
  mais de 1.500 caracteres: o TotalTime do Word não é confiável ("Salvar como", modelos).
- DOCX, DOC e TXT reais: nenhum falso positivo.

Segundo teste, com reais **brasileiros** que nunca tinham passado pelo AIDA: 40 do PNCP
(`pncp`, um por órgão) e 59 do SAFEDOCS (`safedocs --dominio br`, um por site, de 2021):

- **2 falsos positivos em 99 (2 %)**, os dois editais com assinatura ICP-Brasil (Lacuna e
  BRy). Depois da assinatura esses programas acrescentam o DSS da **PAdES-LTV**
  (certificados, CRLs, OCSPs e VRI), que mantém a assinatura verificável: não é edição.
  `estrutura._so_validacao_ltv` reconhece essa atualização (DSS presente, nenhuma página,
  anotação, imagem, fonte ou formulário novo, e todo stream sem tipo referenciado pelo DSS)
  e ela deixa de contar como alteração e como revisão. Os dois passaram a sair `REAL`
  (assinatura intacta). Edição de verdade depois da assinatura continua sendo pega (testes).
- Os 2 % são o número honesto antes da correção; depois dela, 0 nesses mesmos 99.

## Diários oficiais do Querido Diário (23/10)

`... queridodiario --inicio AAAA-MM-DD --fim AAAA-MM-DD` baixa diários oficiais municipais
pela API pública do Querido Diário (Open Knowledge Brasil), um por emissor (município ou
associação de municípios). A API mudou para `api.queridodiario.org.br` e recusa o agente
padrão do Python: o baixador se identifica como `AIDA-Documents/1.0`.

100 diários de set–out/2026 (mPDF, XeTeX, Adobe, Word, BRy Signer, pyHanko...):

- **6 falsos positivos em 100 (6 %)** na primeira passada, o pior número até agora. Diário
  oficial é documento longo, digitado por gente e montado juntando atos.
- 5 eram **DV errado de verdade**: CNPJ/CPF digitado errado num documento real (1 em 17,
  4 em 89, ou o único CNPJ do diário). Com 0,60 um só DV errado já dava `IA/MANIPULADA`.
  Agora pesa 0,45 (dois ou mais somam até o limiar) e, com 10 ou mais identificadores e
  até 10 % errados, conta como digitação (0,30, uma vez). Os 2 PDFs do Gemini com CPF
  inventado continuam `IA/MANIPULADA` (0,30 + 0,45 = 0,615).
- 1 era **PAdES-LTV da BRy** não reconhecida: a tabela de referências vem em stream
  `/Type/XRef`, que agora é aceito como estrutura.
- 1 tinha **5 assinaturas copiadas de outros PDFs** (cada ato assinado e depois juntado):
  nenhum `/ByteRange` termina num `%%EOF` do arquivo. Não é edição depois da assinatura;
  vira o indício fraco `assinatura_de_outro_arquivo` (0,15) e não comprova origem.
- Depois: **2 em 100** nesses mesmos diários (ajustado neles, então otimista). Os dois
  somam indícios moderados de juntada (fonte duplicada, Benford, um DV errado). PNCP,
  SAFEDOCS e NapierOne continuam com 0.

## Gemini (21/10)

9 arquivos gerados no app do Gemini: 3 PDFs (botão Exportar da conversa e do Canvas),
3 DOCX, 1 TXT e 2 MD (o Canvas só baixa .md). **Nenhum tem C2PA**, nem menção a Gemini,
Google ou SynthID. A marca d'água SynthID do texto existe, mas a chave de detecção não é
pública: o AIDA não consegue lê-la.

- **PDF**: gerado por Chromium rodando em servidor (Creator `Chromium`, `Skia/PDF m136`),
  com texto só em fontes Type3, sem marcação e página de 595,92 × 842,88. O Chrome do
  usuário grava o user agent no Creator e embute fontes Type0. 0 de ~500 reais têm o padrão
  → `padrao_exportador_gemini` (0,30): moderado, porque sistemas web também usam Chromium.
- **DOCX da conversa**: python-docx, igual ao ChatGPT, e o AIDA já pega.
- **DOCX convertido no Google Docs**: sem `docProps`; marca do Docs, não do Gemini.
- **TXT/MD**: só o texto; nada a ler. `.md` passou a ser aceito como texto.
- Dois PDFs do Gemini (recibo e atestado) trouxeram **CPF inventado com dígito errado**,
  e o `dv_invalido` pegou: com o padrão do exportador, saíram `IA/MANIPULADA` (0,72).

## Aprendizado de máquina (início em 08/10)

`caracteristicas.py` transforma o PDF em 22 números de "estilo de código" (versão, object
streams, XMP, como embute as fontes, tamanho exato da página, filtros, início do conteúdo) e
dois de texto. `treinar.py` mede cada um sozinho, valida com regressão logística deixando um
documento de fora e só grava modelo com 30 ou mais documentos por classe. O estudo dos 7 PDFs
de 08/10 está em [`docs/estudo-documentos-2026-10-08.md`](../docs/estudo-documentos-2026-10-08.md).
Ainda não há modelo em produção: a decisão continua sendo a dos pesos acima.

## O que já aprendemos

- **O ChatGPT assina o PDF que gera.** O 0015 da coleta de 09/10, uma prova feita pelo
  ChatGPT com ReportLab, estava entre os reais e trazia um manifesto C2PA da OpenAI
  ("ChatGPT", `gpt-5-6`, `trainedAlgorithmicMedia`). A v0 dava só 0,405 (biblioteca de
  programação + revisão incremental). Agora o manifesto é lido e o documento sai
  `IA/MANIPULADA`; a revisão que só acrescenta o manifesto não conta como edição.
- **O Word embute a mesma fonte duas vezes** (Calibri TrueType/WinAnsi e Calibri
  Type0/Identity-H). A regra de subconjunto duplicado acusava os 3 artigos reais do Word;
  agora só conta subconjuntos do mesmo tipo.
- **PDFsam não é o Sejda.** O PDFsam grava `SAMBox (www.sejda.org)` no Producer e caía como
  "editor online". Agora é "organizador de páginas", peso 0,10.
- **Benford em amostra pequena engana.** Com 120 valores tirados da própria distribuição
  de Benford, o MAD fica em ~0,021 só por acaso, acima do limite de 0,015 de Nigrini. O MAD
  esperado ao acaso é ~0,033 com N = 50, ~0,014 com N = 300 e ~0,007 com N = 1000 (campo
  `mad_esperado_ao_acaso`). Uma nota tem dezenas de valores, então o desvio só conta quando o
  qui-quadrado também rejeita (p < 0,01), e com N < 50 Benford não entra na decisão.
- **Benford só nos valores monetários.** No texto corrido de um artigo o MAD deu 0,087
  (anos, páginas, seções). Contar só `1.234,56` resolve.
- **O Word grava dois `%%EOF`** num PDF recém-exportado (trailer híbrido vazio). Contar
  `%%EOF` direto acusaria edição em todo documento do Word.

## Limites conhecidos

- A validade criptográfica da assinatura não é verificada (use o Verificador ITI).
- PDF só-imagem e fotos de documento ainda não passam por OCR; caem em `INCONCLUSIVO`.
- A existência da nota na SEFAZ não é consultada (a chave com DV certo pode ser de outra nota).
- Um documento inteiro gerado por IA e salvo por um sistema "limpo" passa por todas as
  camadas estruturais. Ver a seção de próximos passos na pesquisa.
- Os pesos são um ponto de partida sem calibração: rodar `avaliar_lote` com documentos reais
  e manipulados antes de mostrar qualquer número no site.
