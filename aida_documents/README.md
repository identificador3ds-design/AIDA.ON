# AIDA Documents

Triagem de PDFs enviados como prova (nota fiscal, recibo, comprovante, boleto, laudo).
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
| Identificadores | `numeros.py` | DV de CNPJ (inclusive o alfanumérico), CPF e chave de acesso NF-e/NFC-e; UF, mês e modelo da chave; CNPJ do emitente da chave presente no documento | 0,60 |
| Assinatura | `estrutura.py` | bytes acrescentados depois do trecho coberto pelo `/ByteRange` | 0,50 |
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

## Aprendizado de máquina (início em 08/10)

`caracteristicas.py` transforma o PDF em 22 números de "estilo de código" (versão, object
streams, XMP, como embute as fontes, tamanho exato da página, filtros, início do conteúdo) e
dois de texto. `treinar.py` mede cada um sozinho, valida com regressão logística deixando um
documento de fora e só grava modelo com 30 ou mais documentos por classe. O estudo dos 7 PDFs
de 08/10 está em [`docs/estudo-documentos-2026-10-08.md`](../docs/estudo-documentos-2026-10-08.md).
Ainda não há modelo em produção: a decisão continua sendo a dos pesos acima.

## O que já aprendemos

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
