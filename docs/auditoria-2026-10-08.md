# Auditoria técnica do AIDA — ciclo 1 (08/10/2026)

Escopo verificado diretamente: site em produção (`www.aida-on.com.br`), Supabase (só leitura
anônima, contagens e HEAD), Spaces `aidaon/aida-api` e `aidaon/aida-video`, repositório GitHub
`identificador3ds-design/AIDA.ON`, cópias locais no Google Drive (G:) e no pendrive USB-PEDRO
(montado como F:; é o "D:" citado no `launch.json`).

Legenda de estados: **Concluído** = alterado e testado em branch local, **não publicado**.
Nada foi enviado a produção, ao GitHub ou ao Hugging Face neste ciclo.

## 1. Reconhecimento

| Componente | Onde | Versão auditada | Observação |
|---|---|---|---|
| Site estático (HTML/JS, PWA) | GitHub `AIDA.ON` → Vercel | `ce7b44b` (main) | `www.aida-on.com.br`; `aida-on.vercel.app` redireciona |
| API de imagem (Flask + CLIP + forense + RIGID, R6fp6) | HF Space `aidaon/aida-api` | `f2595a6` | modelos idênticos (SHA-256) aos do pendrive |
| API de vídeo/áudio/documentos | HF Space `aidaon/aida-video` | `1958104` | |
| Banco, login, storage | Supabase `nwzijdudhemuibsyzpub` | — | chave `anon` no JS (pública por desenho) |
| Testes do core | só em `aida-space/testes` (pendrive, sem git) | — | **fora do controle de versão** |

Cópias desatualizadas (não usar como base): `G:\...\AIDA.ON` (parado em 17/08), `G:\...\aida-space-git`
(4 commits), `F:\...\aida-video-space` (já registrado no RETOMAR de 02/10).

## 2. Linha de base (antes das correções)

| Indicador | Valor medido |
|---|---|
| Testes do site | 306 aprovados, 0 reprovados, 1 pulado (com PyAV instalado; sem ele, 53 falham por import) |
| Testes do core | 85 aprovados (no `aida-space` do pendrive; o repositório do Space não tem testes) |
| CI | inexistente (nenhum `.github/workflows`) |
| Vulnerabilidades em dependências (pip-audit) | 0 conhecidas nos 3 `requirements.txt` — ressalva: versões não fixadas, o resultado vale para as versões resolvidas hoje |
| JS (`node --check`) | 26 arquivos sem erro de sintaxe |
| Latência `/analisar` (640×480, produção) | ~4,3 s (5 amostras: 3,9–4,8 s); com 4 simultâneas: ~8,2 s, 0 erros |
| Robustez de entrada (9 casos) | 6 corretos, 1 erro 500, 1 aceitação indevida (400 MP), 1 sinal de viés de formato |

## 3. Achados

### P0 — confirmados

**P0-1 · Histórico e fotos dos usuários legíveis por qualquer visitante** — *Concluído no código; falta aplicar SQL*
- Evidência: com a chave anon do site, `historico_analises` devolveu 168 linhas de 11 usuários
  (`user_id`, `imagem_original`); 8/8 URLs `.../object/public/evidencias/...` responderam 200 sem login.
  Teste feito só com contagem e HEAD: nenhuma imagem foi baixada ou vista.
- Impacto: vazamento de dados pessoais (fotos enviadas) — risco LGPD alto. Já listado como pendente em `docs/lgpd-inventario.md`.
- Correção: `script-analise.js` grava o caminho (nome saneado), `script-historico.js` exibe por
  URL assinada de 1 h e apaga pelo caminho decodificado; `docs/migracao-rls-historico-evidencias.sql`
  liga RLS por dono e torna o bucket privado (com bloco de rollback).
- Ordem segura: publicar o site → rodar o SQL → conferir (`*/0` com a chave anon).
- Testes: `testes/test_historico_privacidade.py` (8, incluindo execução do JS no Node).

**P0-2 · A Vercel publicava o repositório inteiro** — *Concluído*
- Evidência: 200 em produção para `/aida_api/app.py`, `/aida_api/chaves_api.py`, `/docs/supabase-admin-setup.sql`,
  `/aida_modelo/site_api/uploads/imagem-aida.jpg`, `/aida_modelo/modelos/melhor_modelo.pkl`, `/testes/conftest.py`.
- Correção: `.vercelignore` em lista de permissão (só `index.html`, `manifest`, `service-worker.js`, `pages/`, `scripts/`, `styles/`, `assets/`).
- Testes: 3 em `test_rotas_e_assets.py` (nada proibido publicado; tudo que as páginas e o service worker usam continua publicado). Validados por mutação.
- Risco: um arquivo novo fora dessas pastas não sobe — o teste acusa.

### P1

**P1-1 · Imagem de 1×1 px derrubava a API (HTTP 500)** — *Concluído (branch do Space)*
- Reproduzido em produção e local: `ValueError: Invalid number of FFT data points (0)` em `textura_ruido.py`.
- Correção: `validar_dimensoes()` em `aida/utilitarios/imagem.py` (lado mínimo 8 px → 400).

**P1-2 · Bomba de descompressão aceita** — *Concluído (branch do Space)*
- PNG de 388 KB com 20000×20000 (400 MP) foi aceito e decodificado (9,8 s, ~1,2 GB em RGB).
- Correção: limite de 210 MP checado no cabeçalho, antes de decodificar (cobre câmeras de 200 MP).
- Testes: `testes/test_dimensoes_imagem.py` (8). Com o pipeline real, imagens válidas dão exatamente
  as mesmas probabilidades de produção (0,860 / 0,901 / 0,956).

**P1-3 · `admin_config` expõe e-mail e o bloqueio de conta é só no navegador** — *Planejado*
- `admin_config` tem leitura pública por política explícita e hoje contém 1 e-mail em `accountStates`.
- O bloqueio é decidido por `localStorage` → contornável. Correção proposta: guardar o estado da
  conta em `usuarios.status` (leitura só do dono, RLS já existe) ou banir pelo Supabase Auth via
  função `security definer` chamada pelo admin; tirar `accountStates` de `admin_config`.

**P1-4 · Suíte de testes do core fora do controle de versão** — *Concluído (branch do Space)*
- `testes/`, `pytest.ini` e `ferramentas/` entram no repositório do Space (93 testes, nenhum carrega modelo).

**P1-5 · Sem CI** — *Concluído no site*
- `.github/workflows/ci.yml`: pytest, `node --check`, pip-audit em todo push/PR. Não publica nada.
- Para bloquear merge: marcar os jobs como obrigatórios em *Settings → Branches → main*.
- `testes/test_segredos.py`: todo JWT versionado precisa ser `role=anon`.

### P2

| ID | Achado | Estado |
|---|---|---|
| P2-1 | CORS reflete qualquer origem nos dois Spaces (`ALLOWED_ORIGINS` / `AIDA_VIDEO_CORS` não definidos) | Bloqueado: configurar no painel do HF (infra) |
| P2-2 | Sem limitação de taxa na API de imagem: ~0,5 img/s de vazão, um cliente satura | Planejado |
| P2-3 | Excluir conta não remove dossiês do cache forense no servidor (expiram em 7 dias) | Planejado |
| P2-4 | `historico` interpolava `id`/URL sem escape em atributos | Concluído (P0-1) |
| P2-5 | Texto corrompido ("nÃ£o", "inspeÃƒÂ§ÃƒÂ£o") no validador TAC | Concluído + teste (62 arquivos checados) |
| P2-6 | `limiar_desacordo` = 0,992 desliga, na prática, o rebaixamento por desacordo entre módulos | Para decisão do grupo (mudar exige comparar com a linha de base) |
| P2-7 | `requirements` sem versões fixadas: builds não reprodutíveis | Planejado (gerar lock com `pip-compile`) |
| P2-8 | Docstring de `nivel_confianca` cita limiar 0,223 (o atual é 0,7426) | Planejado |

## 4. Auditoria do modelo

### 4.1 Processamento da resposta e limiares (revisão de código)
- `politica.decidir` aplica corretamente: banda de abstenção [0,6126; 0,8726] em torno do limiar
  0,7426, rebaixamento por qualidade < 0,35 e por fora-de-domínio; `REAL_EDITADA` só troca REAL
  (não mexe em probabilidade). A escala de exibição é monótona e não altera métricas de ranking.
- Produção = local: as mesmas imagens deram as mesmas probabilidades no Space e no pipeline local.
- `limiar_desacordo` 0,992 neutraliza o rebaixamento por desacordo (P2-6).
- O título do estado INCONCLUSIVO é vazio de propósito; a tela depende de `explicacao`/`motivos`.

### 4.2 Sensibilidade ao formato do arquivo (teste pareado, mesmos pixels)
Script: `avaliacao/sensibilidade_formato.py` (fora do repositório; resultados em `sens_*.csv`).
Cada imagem foi decodificada, reduzida a ≤ 1024 px, sem metadados, e salva em PNG, JPEG q95 e JPEG q85.

| Conjunto | PNG | JPEG q95 | JPEG q85 |
|---|---|---|---|
| 37 fotos reais (`FOTOS TCC REAL`) — falso positivo IA | 0% | 0% | 0% |
| 27 imagens IA (`dataset/ia/originais`, amostra sistemática 1/15) — detectadas | 85% [68–94] | 81% [63–92] | **63% [44–78]** |
| IA classificada como REAL (erro oposto) | 4% | 11% | 15% |

- PNG vs JPEG q85 nas imagens de IA: 6 perdem a detecção e nenhuma ganha (McNemar exato p = 0,031).
- 10 das 64 imagens mudam de veredito só pela troca de formato.
- Fotos reais são estáveis (diferença pareada mediana −0,001). **A hipótese inicial "PNG empurra
  para IA" não se confirmou nas fotos reais**; o efeito medido é a **perda de detecção de IA sob
  compressão JPEG**, que é o caminho comum em redes sociais e mensageiros.
- Ressalvas: as duas pastas são material de treino/validação do projeto (os números absolutos são
  otimistas; só a comparação pareada é a medida aqui); n = 27 dá intervalos largos.
- Recomendação (sem alterar o modelo agora): repetir em conjunto independente (OpenFake `core/test`,
  já usado pela equipe) com variantes JPEG q70–q90, e só então decidir aumento de dados com
  recompressão no treino, comparando com a linha de base R6fp6.

### 4.3 Teste cego de 20 imagens
O gabarito mostra que as 20 imagens vêm de `F:scolaTCCdataset...` (dados de treino):
serve como teste de funcionamento, não como medida de generalização.

## 5. Limitações deste ciclo

- Sem acesso ao painel do Supabase, da Vercel nem do HF: RLS, bucket, CORS e deploy não foram alterados.
- Teste de ponta a ponta com login não executado (exigiria credenciais de uma conta real).
- Escrita anônima no Supabase (INSERT/UPDATE/DELETE) não foi testada para não alterar dados reais.

## 6. Como reproduzir

```bash
# site
python -m pytest -o addopts="" -q              # 381 testes
# core (clone do Space, branch auditoria/validacao-dimensoes)
python -m pytest -o addopts="" -q              # 93 testes
# sensibilidade a formato (precisa dos modelos reais)
PYTHONPATH=<core> python sensibilidade_formato.py <pasta> REAL|IA saida.csv
```

## 7. Antes × depois (nas branches locais; produção ainda não mudou)

| Indicador | Antes | Depois |
|---|---|---|
| Testes do site | 306 ✓ / 1 pulado | 381 ✓ / 1 pulado |
| Testes do core no repositório do Space | 0 (85 só no pendrive) | 93 ✓ |
| CI | nenhum | pytest + sintaxe JS + pip-audit |
| Defeitos P0 abertos | 2 | 0 no código (P0-1 depende de aplicar o SQL) |
| Defeitos P1 abertos | 5 | 1 (P1-3) |
| Entradas inválidas que davam 500 / eram aceitas | 2 de 9 | 0 de 9 (local) |
| Arquivos internos servidos pela Vercel | 348 | 0 após deploy |

## 8. O que precisa da sua autorização / ação

1. **Publicar o site** (merge de `auditoria/p0-seguranca` em `main`; a Vercel faz o deploy). Sugestão: push da branch primeiro para ver o *preview* da Vercel.
2. **Rodar `docs/migracao-rls-historico-evidencias.sql`** no Supabase **depois** do passo 1.
3. **Publicar o Space** `aidaon/aida-api` com a branch `auditoria/validacao-dimensoes`.
4. Definir `ALLOWED_ORIGINS=https://www.aida-on.com.br,https://aida-on.com.br` no Space de imagem e `AIDA_VIDEO_CORS` (mesmo valor) no de vídeo.
5. Marcar os jobs do CI como obrigatórios na proteção da `main`.

## 9. Próximas prioridades (ciclo 2)

1. P1-3: bloqueio de conta no servidor e tirar e-mails de `admin_config`.
2. P2-2: limitação de taxa por IP em `/analisar` e `/video/analisar`.
3. Reavaliar a robustez a JPEG em conjunto independente antes de qualquer retreino.
4. P2-3: excluir conta também apaga o cache forense; prazo de retenção formal (LGPD).
5. Fixar versões (`pip-compile`) nos dois Spaces.
