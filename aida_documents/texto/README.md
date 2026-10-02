# AIDA Documents · texto

Indícios de texto gerado por IA em PDF, DOCX e TXT, em português e inglês. Três estados:
`HUMANO`, `IA` e `INCONCLUSIVO`. Página: `pages/index-texto.html` (rota `/texto`).

```bash
python -m aida_documents.texto.detector trabalho.pdf
python -m aida_documents.texto.calibrar "G:/Meu Drive/TCC/textos_teste" --idioma pt --cache medidas_pt.json
python -m pytest testes/test_aida_documents_texto.py
```

Dependências: `pypdf` (já no projeto). Para a perplexidade, `torch` e `transformers`
(opcionais: sem eles o resultado é sempre `INCONCLUSIVO`). Para calibrar, `scikit-learn`.

## Etapas

| Etapa | Arquivo | O que faz |
|---|---|---|
| Extração | `extracao.py` | PDF página a página (pypdf); DOCX pelo XML do corpo, sem cabeçalho, rodapé nem tabelas; TXT |
| Limpeza | `limpeza.py` | tira linhas repetidas nas bordas de ≥ 40% das páginas, números de página, títulos, sumário e a lista de referências; reúne palavras hifenizadas e remonta os parágrafos |
| Estilo | `estilo.py` | idioma, divisão em frases, variação do comprimento das frases, diversidade lexical (MATTR), marcadores típicos de LLM |
| Perplexidade | `perplexidade.py` | surpresa média por token com um GPT-2 pequeno do idioma, e o quanto ela varia entre frases |
| Decisão | `detector.py` | trechos de ~120 palavras, regressão logística por trecho, agregação por documento, três estados |
| Calibração | `calibrar.py` | ajusta os pesos no treino, escolhe os limiares na validação (teto de falso positivo) e reporta no teste |
| Rotas | `servidor.py` | `/documento/texto/analisar` (202 + tarefa), `/documento/texto/tarefa/<id>`, `/documento/texto/saude` |

Modelos (nome do Hub ou pasta local): `AIDA_TEXTO_MODELO_PT` (padrão
`pierreguillou/gpt2-small-portuguese`), `AIDA_TEXTO_MODELO_EN` (padrão `gpt2`).

## Sem calibração não há veredito

Os parâmetros embutidos em `detector.py` são um chute de partida. Enquanto não existir
`calibracao.json` para o idioma (e para o mesmo modelo de linguagem), o relatório mostra o
indicador e os trechos com `calibrado: false` e o resultado fica `INCONCLUSIVO`.

Para calibrar: pelo menos 20 documentos por classe em `<pasta>/humano` e `<pasta>/ia`
(quanto mais, melhor; o ideal são centenas, de gêneros variados). Humanos de preferência
anteriores a 2022; IA de vários modelos (ChatGPT, Claude, Gemini) e com os mesmos temas e
gêneros dos humanos, senão o classificador aprende o tema e não a autoria.

## Limites conhecidos

- **Falso positivo em texto formal.** Texto técnico, jurídico, acadêmico, traduzido ou
  passado por corretor é previsível sem ser de IA. O limiar `IA` é escolhido para acusar no
  máximo 1% dos humanos da validação, mas isso só vale para gêneros parecidos com os da
  calibração.
- **Texto de IA reescrito** ou parafraseado passa.
- **Envelhece.** Cada geração de LLM muda a assinatura; a lista de marcadores e a
  calibração precisam ser refeitas com textos de modelos novos.
- PDF só-imagem não é lido (sem OCR). Documento com mais de 12.000 palavras: só o começo.
- O GPT-2 pequeno é uma referência fraca. Próximo passo natural: Binoculars (razão entre
  dois modelos), que reduz o falso positivo em texto formal, ao custo de mais CPU.
