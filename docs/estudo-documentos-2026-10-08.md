# Estudo — AIDA Documents com os PDFs de 08/10/2026

Primeiro lote rotulado para o aprendizado de máquina: pasta **DOCS GATO** do Drive.

| Arquivo | Rótulo | Conteúdo | Produtor | Páginas |
|---|---|---|---|---|
| Documento-IA.pdf | IA | prova "A Cartomante" (Etec) | pypdf (regravou um ReportLab) | 3 |
| Documento-IA2.pdf | IA | orçamento fictício "Nexora" (o de 29/09) | ReportLab | 1 |
| Documento-IA3.pdf | IA | gabarito da prova "A Cartomante" | ReportLab | 1 |
| Documento-REAL.pdf | REAL | Revista Fonte nº 20 (Prodemge, dez/2018) | PDFsam Basic (SAMBox) | 9 |
| Documento-REAL2.pdf | REAL | artigo de A. Cereda Jr. (2018) | Word 2016 | 2 |
| Documento-REAL3.pdf | REAL | artigo de A. Cereda Jr. (2017) | Word 2016 | 2 |
| Documento-REAL4.pdf | REAL | artigo de A. Cereda Jr. (2017) | Word 2016 | 2 |

## 1. Regras de antes: invertidas

Com as regras da v0, os reais tinham suspeita **maior** que os de IA (AUC 0,00):

| | Antes | Depois |
|---|---|---|
| REAL (PDFsam) | 0,405 (Sejda "editor online" + modificado 52 dias depois) | 0,235 |
| REAL2–4 (Word) | 0,30 ("Calibri embutida duas vezes") | 0,00 |
| IA (pypdf) | 0,00 | 0,15 (biblioteca de programação) |
| IA2, IA3 (ReportLab) | 0,15 | 0,15 |
| **AUC da suspeita** | **0,00** | **0,75** |

Três correções, todas com teste:

1. **Fonte duplicada**: o Word embute a Calibri como TrueType (WinAnsi) e de novo como Type0
   (Identity-H) para os caracteres fora do WinAnsi. Não é edição. Agora só conta quando os
   dois subconjuntos são do mesmo tipo.
2. **PDFsam ≠ Sejda**: o PDFsam Basic grava `SAMBox (www.sejda.org)`. Virou "organizador de
   páginas" (peso 0,10), e não "editor online" (0,30).
3. **pypdf/pikepdf** entram como biblioteca de programação: o Documento-IA.pdf foi gerado no
   ReportLab e regravado pelo pypdf, que apagou o Producer original.

Os 7 continuam `INCONCLUSIVO`, e isso está certo: nenhum tem assinatura digital nem chave de
NF-e, então nada comprova a origem.

## 2. Características (`aida_documents/caracteristicas.py`)

22 números, quase todos de "estilo de código" do arquivo (Adhatarao e Lauradoux, 2022).
AUC de cada uma sozinha (1,0 = todo IA acima de todo real; 0,0 = o contrário; 0,5 = não separa):

| Característica | Real (média) | IA (média) | AUC |
|---|---|---|---|
| fontes padrão sem embutir (Helvetica) | 0,00 | 1,00 | 1,00 |
| página A4 exata do ReportLab (595,2756 × 841,8898) | 0 | 1 | 1,00 |
| conteúdo começa com `BT /F1 12 Tf 14.4 TL ET` | 0 | 1 | 1,00 |
| linhas `_____` para preencher (por mil caracteres) | 0,00 | 1,59 | 1,00 |
| versão do PDF | 1,6 | 1,4 | 0,00 |
| xref stream / XMP / idioma | 1 | 0 | 0,00 |
| fontes em subconjunto | 0,89 | 0,00 | 0,00 |
| bytes por página (log) | 12,3 | 8,6 | 0,00 |
| ASCII85 | 0 | 0,67 | 0,83 |
| travessões por mil caracteres | 0,73 | 1,38 | 0,58 |
| criação = modificação | 0,75 | 0,67 | 0,46 |

Regressão logística, deixando um documento de fora por vez: **AUC 1,00, 7 de 7 certos**
(prob. de IA: reais 0,07–0,17; IA 0,52–0,88).

## 3. Por que esse 100 % não vale

**Onze características separam as classes sozinhas.** Isso não é sinal de IA: é o conjunto
contando "ReportLab × Word". Todos os de IA saíram de script Python e todos os reais saíram
do Word ou do PDFsam. O modelo aprendeu o **programa**, não a **IA**. Outros atalhos:

- **data**: os reais são de 2017–2018 (antes do ChatGPT) e os de IA de 2026. Por isso o ano
  ficou fora das características de propósito;
- **assunto**: provas e orçamento (IA) × artigos e revista (real). A característica "linhas
  de preencher" separa só porque nenhum real é uma prova em branco;
- **tamanho**: 3 IA × 4 reais. Com N = 7 qualquer AUC tem intervalo enorme.

Por isso `treinar.py` recusa gravar modelo com menos de 30 documentos por classe e marca os
números como "só de estudo".

## 4. O que coletar para o próximo lote

O que quebra os atalhos é ter **o mesmo programa nas duas classes**:

| Pasta | O que pôr | Por quê |
|---|---|---|
| `ia/` | texto do ChatGPT/Gemini/Claude colado no **Word** e exportado em PDF | o caso difícil de verdade; hoje passa como real |
| `ia/` | documento pedido à IA e exportado pelo Google Docs, Canva e navegador | outros programas na classe IA |
| `ia/` | notas, recibos e comprovantes **editados** (iLovePDF, Sejda, Foxit, Canva) | a manipulação que o produto promete achar |
| `reais/` | PDFs reais feitos por **sistemas** (boletos, NF-e, extratos, comprovantes PIX) | o domínio do produto; muitos saem de iText/Jasper |
| `reais/` | provas e listas de exercício reais de professores (Word, Google Docs) | o mesmo assunto das provas de IA |
| `reais/` | documentos reais de 2025–2026 | tirar a data como atalho |

Planilha de coleta (passo a passo, metas, variedade e prompts): [`AIDA_Documents_Coleta.xlsx`](AIDA_Documents_Coleta.xlsx).

Meta mínima: 30 por classe, com pelo menos 3 programas diferentes em cada uma. Organizar como
`<pasta>/reais/*.pdf` e `<pasta>/ia/*.pdf` (ou `manipulados/`) e rodar:

```bash
python -m aida_documents.treinar "<pasta>" --saida estudo_documentos
```

Com o lote maior, o estudo da seção 2 deve mostrar quais características continuam separando
**dentro** do mesmo programa (ex.: só os PDFs do Word). As que não separarem saem do modelo.

## 5. Sobre detectar o texto escrito por IA

Quando a IA escreve e uma pessoa exporta pelo Word, o arquivo é idêntico ao de um humano: a
única pista fica no texto. O lote atual tem só duas características de texto (travessões e
linhas de preencher), e nenhuma se sustenta. Detectores de texto de IA têm taxa de falso
positivo alta, ainda mais em português, e são fáceis de enganar com paráfrase. No AIDA esse
sinal deve entrar, se entrar, como indício fraco e explicável, nunca sozinho.
