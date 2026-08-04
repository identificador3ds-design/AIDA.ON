# AIDA.ON - Modelo de Análise de Imagens

Projeto para extrair métricas estatísticas de imagens reais e imagens IA/manipuladas, gerar uma base CSV, treinar modelos de machine learning e disponibilizar análise individual por terminal ou API Flask.

## Estrutura

```text
aida_modelo/
├── dataset/
│   ├── reais/
│   └── ia/
├── metricas/
│   └── metricas_aida.csv
├── modelos/
├── extratores/
├── saidas/
│   ├── graficos/
│   ├── relatorios/
│   └── historico/
├── site_api/
│   ├── app.py
│   ├── templates/index.html
│   └── uploads/
├── config.py
├── gerar_csv.py
├── treinar_ml.py
├── analisar_imagem.py
├── menu.py
└── requirements.txt
```

## Onde colocar as imagens

Coloque imagens reais em:

```text
F:\Escola\TCC\aida_modelo\dataset\reais
```

Coloque imagens IA ou manipuladas em:

```text
F:\Escola\TCC\aida_modelo\dataset\ia
```

Formatos aceitos: `.jpg`, `.jpeg`, `.png`, `.webp`, `.bmp`, `.heic`, `.avif`.

Limite máximo por imagem: 15 MB. Arquivos maiores são recusados com mensagem clara.

## Instalação

No terminal, entre na pasta do projeto:

```powershell
cd F:\Escola\TCC\aida_modelo
```

Instale as bibliotecas:

```powershell
pip install -r requirements.txt
```

O pacote `pillow-heif` foi incluído para suporte a HEIC e AVIF. Se uma imagem estiver corrompida ou se o formato não puder ser lido, o sistema informa o erro.

## Arquivos principais

`config.py`: centraliza caminhos, extensões aceitas, limite de 15 MB, random state, divisão treino/teste e nomes dos arquivos salvos.

`extratores/`: contém FFT + Benford global, FFT + Benford 5x5, gradientes/textura, LSB e as métricas de Laplaciano, DoG e TSR.

`gerar_csv.py`: percorre `dataset/reais` e `dataset/ia`, aplica todos os extratores e salva `metricas/metricas_aida.csv` em `utf-8-sig`.

`treinar_ml.py`: treina Regressão Logística e Random Forest com 70% treino e 30% teste, compara por F1-score e salva o melhor modelo.

`analisar_imagem.py`: analisa uma imagem individual, mostra REAL ou IA/MANIPULADA, probabilidades, confiança, explicação simples e ID único.

`menu.py`: menu de terminal para executar as tarefas principais.

`site_api/app.py`: API Flask com `POST /analisar` e `GET /analise/<id_analise>`.

## Gerar CSV

Sempre gere novamente o CSV e retreine os modelos após adicionar ou alterar extratores, para que as novas métricas participem das previsões.

```powershell
python gerar_csv.py
```

O CSV será salvo em:

```text
F:\Escola\TCC\aida_modelo\metricas\metricas_aida.csv
```

Também serão gerados gráficos comparativos em:

```text
F:\Escola\TCC\aida_modelo\saidas\graficos
```

Para gerar somente os gráficos a partir do CSV existente:

```powershell
python gerar_csv.py --graficos
```

## Treinar os modelos

```powershell
python treinar_ml.py
```

Antes do treino, o sistema valida se existem imagens suficientes nas duas classes. Se uma pasta estiver vazia ou com poucas imagens, o treinamento é bloqueado.

São salvos em `modelos/`:

```text
modelo_regressao_logistica.pkl
modelo_random_forest.pkl
melhor_modelo.pkl
scaler.pkl
imputer.pkl
colunas_treinamento.json
desempenho_modelos.json
```

Relatórios e gráficos de treinamento são salvos em `saidas/relatorios` e `saidas/graficos`.

## Analisar uma imagem pelo terminal

```powershell
python analisar_imagem.py "D:\caminho\imagem.jpg"
```

Ou execute sem caminho e informe quando o programa pedir:

```powershell
python analisar_imagem.py
```

O resultado inclui:

- REAL ou IA/MANIPULADA;
- probabilidade de ser real;
- probabilidade de ser IA/manipulada;
- confiança baixa, média ou alta;
- explicação simples;
- ID único da análise, como `AIDA-2026-0001`.

Relatórios são salvos em:

```text
F:\Escola\TCC\aida_modelo\saidas\relatorios
```

O histórico CSV fica em:

```text
F:\Escola\TCC\aida_modelo\saidas\historico\historico_analises.csv
```

## Usar o menu

```powershell
python menu.py
```

Opções disponíveis:

1. criar/verificar estrutura de pastas;
2. gerar CSV de métricas;
3. treinar modelos;
4. analisar imagem individual;
5. gerar gráficos comparativos;
6. iniciar API Flask;
7. buscar relatório pelo ID;
8. sair.

## Iniciar a API Flask

```powershell
python site_api/app.py
```

Acesse:

```text
http://localhost:5000
```

## Enviar imagem pelo JavaScript

Exemplo com `fetch` e `FormData`:

```javascript
const dados = new FormData();
dados.append("imagem", arquivoSelecionado);
dados.append("historico", "true"); // ou "false"

const resposta = await fetch("/analisar", {
  method: "POST",
  body: dados
});

const json = await resposta.json();
```

Se `historico` for `true`, a imagem enviada fica em `site_api/uploads` e os dados são registrados. Se for `false`, a imagem é apagada após o processamento, mas o relatório e o registro da análise continuam sendo salvos.

## JSON retornado pela API

Sucesso:

```json
{
  "sucesso": true,
  "id_analise": "AIDA-2026-0001",
  "resultado": "REAL",
  "probabilidade_real": 0.87,
  "probabilidade_ia": 0.13,
  "confianca": "alta",
  "explicacao": "Texto simples para usuário comum.",
  "modelo_utilizado": "random_forest",
  "historico_habilitado": true,
  "imagem_mantida_no_historico": true,
  "relatorio_json": "caminho do relatório salvo"
}
```

Erro:

```json
{
  "sucesso": false,
  "erro": "mensagem clara do erro"
}
```

As métricas técnicas não são enviadas no JSON principal, para manter a resposta simples ao usuário.

## Buscar uma análise pelo ID

Pelo menu, use a opção 7.

Pela API:

```text
GET /analise/AIDA-2026-0001
```

A resposta traz data, imagem, resultado, probabilidades, confiança, caminhos dos relatórios e se a imagem foi mantida ou apagada.

## Interpretação do resultado

O sistema faz uma classificação binária: `REAL` ou `IA/MANIPULADA`. A confiança é calculada pela distância da probabilidade em relação a 50%. Quanto mais perto de 50%, menor a confiança.

O resultado é estatístico e depende da base usada no treinamento. Ele não é prova absoluta de autenticidade ou manipulação.

## Cuidados para o TCC

Use uma base equilibrada, com imagens reais e IA/manipuladas de origens variadas. Evite treinar com poucas imagens, muitas cópias do mesmo arquivo ou imagens com compressão/resolução muito diferentes entre as classes, pois isso pode fazer o modelo aprender ruídos da base em vez de sinais reais de manipulação.

O ideal é testar com imagens fora da base de treinamento e documentar limitações como compressão JPEG, redimensionamento, screenshots, filtros, metadados ausentes e diferenças entre geradores de IA.
