# AIDA API (`/v1`)

Camada pública, versionada, sobre o AIDA Core — o que a página `/api` descreve
como "uma camada fina sobre o Core".

Ela **não contém lógica de detecção**. Recebe a requisição, autentica a chave,
valida formato e tamanho, aplica a cota, entra na fila, delega ao Core e devolve
o resultado no contrato `/v1`. Uma segunda implementação da mesma decisão
divergiria da primeira, e a que diverge em silêncio é sempre a que está em
produção.

```
cliente → [ borda HTTP ] → [ orquestração ] → [ AIDA Core ] → [ contrato /v1 ]
           chave, cota,      fila, cache        Space HF        resposta
           validação                            (7860)          estável
```

## O que existe aqui

| Roadmap da página `/api` | Onde está |
| ------------------------ | --------- |
| 01 Endpoint de imagem    | `POST /v1/analyze/image` — `app.py` |
| 02 Chaves de API         | `chaves_api.py`, `gerenciar_chaves.py`, `migracoes/migracao-api-keys.sql` |
| 03 Autenticação          | `Authorization: Bearer <chave>` — decorador `exigir_chave` em `app.py` |
| 04 Limites de uso        | `limites.py` — cota por chave, janela deslizante |
| 05 Documentação          | `GET /v1/docs` — gerada de `contrato.CONTRATO`, servido em `GET /v1/contract` |
| 06 Logs                  | `registro.py` — metadado por chamada, stdout + tabela `api_calls` |
| 07 Monitoramento         | `GET /v1/health` — Core alcançável, módulos carregados, latência, fila, cache |

## Endpoints

| Método   | Rota                                | Chave |
| -------- | ----------------------------------- | ----- |
| `POST`   | `/v1/analyze/image`                 | sim   |
| `GET`    | `/v1/analysis/{analysis_id}`        | sim   |
| `GET`    | `/v1/evidence/{analysis_id}/{mapa}` | sim   |
| `GET`    | `/v1/contract`                      | não   |
| `GET`    | `/v1/docs`                          | não   |
| `GET`    | `/v1/health`                        | não   |

```bash
curl -X POST https://<host>/v1/analyze/image \
  -H "Authorization: Bearer <sua-chave>" \
  -F "image=@foto.jpg" \
  -F "evidence=true"
```

```json
{
  "api_version": "v1",
  "analysis_id": "0842f5ce-…",
  "result": "REAL",
  "inconclusive": false,
  "out_of_domain": false,
  "confidence": "alta",
  "ai_probability": 0.086,
  "real_probability": 0.914,
  "module_scores": { "clip": 0.268, "forense": 0.016, "rigid": 0.455 },
  "quality": { "…": 0.0 },
  "limitations": [],
  "evidence": { "maps": { "espectro_magnitude": "/v1/evidence/0842f5ce-…/espectro_magnitude" } },
  "disclaimer": "Este resultado é probabilístico e serve como apoio à decisão…",
  "model_version": "AIDA-2.0"
}
```

## Decisões que valem conhecer antes de integrar

**`result` tem quatro valores.** `REAL`, `REAL_EDITADA`, `IA/MANIPULADA` e
`INCONCLUSIVO` vêm do Core exatamente como ele decidiu — a borda não recalcula, não arredonda e não
desempata. Um `if/else` binário do lado do cliente rotula como IA justamente o
que o sistema declarou indeterminado. Se o Core devolver um valor fora desse
vocabulário (contrato mudou do outro lado), a borda responde `INCONCLUSIVO`:
escolher um dos lados seria a borda decidindo.

`REAL_EDITADA` é uma foto que a análise de conteúdo considera real e cujo
arquivo registra edição em um editor de imagem (`edited` e `editors` dizem o
que foi encontrado). A informação vem dos metadados, não do modelo: uma foto
editada que perdeu os metadados (reenviada por app de mensagem, por exemplo)
sai como `REAL`. Trate `REAL_EDITADA` como real, não como manipulada.

**Exiba `ai_probability`, não `calibration.ai_probability_calibrated`.** O
limiar operacional vem do índice de Youden e não cai em 0,50. A escala de
exibição é uma transformação monótona da calibrada — mesma decisão, mesmo
ordenamento, corte em 50%. Mostrar a calibrada produz telas como "8% de IA" ao
lado do veredito "IA/MANIPULADA". A calibrada fica em `calibration`, para
métrica e auditoria.

**`disclaimer` é obrigatório na saída.** O retorno é indício técnico, não prova.
O campo viaja junto com o resultado e não deve ser omitido por quem integra.

**Nomes de campo em inglês, valores em português.** Os nomes seguem o exemplo
publicado na página `/api`. Os valores (`"REAL"`, `"baixa"`) são os do Core:
traduzi-los criaria um segundo vocabulário para a mesma decisão, e o histórico
do site — que grava o veredito como string — passaria a ter duas grafias para o
mesmo estado.

**Os mapas de evidência são servidos por proxy.** O Core devolve caminhos
relativos válidos só na origem dele. Quem integra recebe URLs desta API, e nunca
precisa alcançar o Core.

**Nome de arquivo não chega ao Core.** Só a extensão viaja (ela decide o
decoder). Nome de arquivo costuma carregar dado pessoal — `cpf-joao.jpg` — e não
muda a análise.

## Rodar local

```bash
pip install -r aida_api/requirements.txt
```

```bash
AIDA_API_DEV_KEYS=aida_teste python -m aida_api.app
```

Sobe em `http://localhost:8000`, falando com o Space em
`https://aidaon-aida-api.hf.space`. Para apontar para um Core local:
`AIDA_CORE_URL=http://127.0.0.1:7860`.

`AIDA_API_DEV_KEYS` existe **só** para desenvolvimento: são chaves em texto puro
na variável de ambiente. Em produção, o modo é Supabase, e a ausência das
variáveis derruba a rota com `503` em vez de abrir a porta.

Testes (não tocam a rede — o Core é dublado):

```bash
python -m pytest testes/test_api_v1.py -q
```

## Colocar em produção

1. Rode `migracoes/migracao-api-keys.sql` no SQL Editor do Supabase (cria
   `api_keys` e `api_calls`, ambas com RLS ligado e sem policy — só a service
   role alcança).
2. Configure no ambiente do deploy: `SUPABASE_URL` e
   `SUPABASE_SERVICE_ROLE_KEY`. **Não** é a chave `anon` que está no front-end:
   ela tem permissões diferentes e não serve aqui.
3. Emita a primeira chave:
   `python -m aida_api.gerenciar_chaves emitir "app de teste"`.
   O valor aparece uma única vez — o banco guarda só o `sha256`.
4. Publique (abaixo). Rodando por conta própria, use **um** worker:
   `gunicorn -w 1 --threads 8 --timeout 200 -b 0.0.0.0:8000 aida_api.app:app`.
   Cache, fila e cota vivem na memória do processo; com dois workers,
   `GET /v1/analysis/{id}` erra metade das vezes e a cota dobra. O `--timeout`
   precisa ser maior que `AIDA_CORE_TIMEOUT_S` (180 s).

### Onde a API roda: Space `AIDAON/aida-borda-api`

URL pública: `https://aidaon-aida-borda-api.hf.space` (é para onde a página
`/api` aponta, em `scripts/script-api.js`). O Space é gratuito (CPU basic) e
fica na mesma infraestrutura do Core, então a chamada borda → Core é rápida.

O deploy é feito pelo workflow `.github/workflows/publicar-api.yml`: a cada
push na `main` que mexe em `aida_api/` (ou manualmente, em Actions), ele roda
os testes e envia `deploy/Dockerfile`, `deploy/README.md` e o pacote
`aida_api/` para o Space. Não edite arquivos direto no Space: o próximo deploy
sobrescreve.

Configuração única:

- No GitHub (Settings > Secrets and variables > Actions): segredo `HF_TOKEN`,
  um token do Hugging Face com permissão de escrita no Space.
- No Space (Settings > Variables and secrets): `SUPABASE_URL`,
  `SUPABASE_SERVICE_ROLE_KEY` e `AIDA_CHAVE_INTERNA` (o mesmo valor configurado
  no Core, que isenta a borda do limite por cliente dele).
- **Não** defina `AIDA_API_DEV_KEYS` no Space. Com Supabase configurado ela é
  ignorada, mas não há motivo para deixá-la lá.

Um Space gratuito hiberna após cerca de 48 h sem acesso; a primeira chamada
depois disso espera o container subir.

Enquanto a API não estiver publicada, `vercel.json` continua redirecionando
`/api/v1/*` para a página `/api` — o comportamento que `docs/rotas.md` descreve.
Quando houver host de produção, essa regra sai e o caminho passa a ser servido
de verdade.

### O que ainda não é global

Cache, fila e contador de cota vivem no processo. Com várias instâncias atrás de
um balanceador, o teto efetivo de cota é multiplicado pelo número delas, e o
cache não é compartilhado — o custo é reprocessamento, nunca resposta errada.
Cota global exige um contador compartilhado (Redis/Postgres) no lugar de
`limites.LimitadorEmMemoria`; a interface `consumir` continua a mesma.

A validação de chave é cacheada por 60 s, então uma revogação passa a valer
depois desse intervalo. Para revogar na hora, reinicie o processo.

## Variáveis de ambiente

Ver `.env.example`. As que mais importam:

| Variável | Padrão | Papel |
| -------- | ------ | ----- |
| `AIDA_CORE_URL` | Space no HF | Onde vive o Core |
| `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` | — | Chaves e logs |
| `AIDA_API_DEV_KEYS` | — | Chaves locais, só desenvolvimento (ignorada com Supabase) |
| `AIDA_API_LIMITE` / `AIDA_API_JANELA_S` | 60 / 3600 | Cota por chave |
| `AIDA_API_CONCORRENCIA` | 2 | Análises simultâneas por processo |
| `AIDA_API_CACHE_TTL_S` | 900 | Reaproveitamento por conteúdo |
| `AIDA_API_MAX_MB` | 15 | Limite de tamanho, igual ao do Core |
| `AIDA_API_LOG_RETENCAO_DIAS` | 90 | Precisa bater com o aviso de privacidade |
