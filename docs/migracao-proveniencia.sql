-- Migração: colunas de proveniência no histórico do AIDA.ON
--
-- Rode no SQL Editor do Supabase. É idempotente (IF NOT EXISTS), então pode ser
-- executada mais de uma vez sem efeito colateral.
--
-- Enquanto esta migração não roda, o front-end detecta a ausência das colunas e
-- grava o histórico no formato antigo — ver `salvarHistoricoSupabase` em
-- scripts/script-analise.js. Nada quebra; só não se guarda a proveniência.
--
-- O que NÃO é gravado, de propósito: o manifesto C2PA completo, a lista de
-- assertions e as evidências brutas. São grandes, contêm dados de terceiros e
-- não são necessários para reconstruir a decisão. O que fica é o suficiente
-- para responder "por que esta imagem recebeu este resultado".

alter table public.historico_analises
  add column if not exists provenance_status        text,
  add column if not exists provenance_score         double precision,
  add column if not exists provenance_confidence    text,
  add column if not exists c2pa_present             boolean default false,
  add column if not exists c2pa_valid               boolean default false,
  add column if not exists ai_generated_claim       boolean default false,
  add column if not exists generator                text,
  add column if not exists generator_confidence     double precision,
  add column if not exists software                 text,
  add column if not exists probabilidade_conteudo   double precision,
  add column if not exists model_version            text;

-- Consulta típica do TCC: quantas análises tinham credencial verificável, e
-- quanto a proveniência discordou da análise de conteúdo.
comment on column public.historico_analises.provenance_status is
  'Estado da camada de proveniência. NO_PROVENANCE_FOUND não significa imagem real.';
comment on column public.historico_analises.probabilidade_conteudo is
  'Probabilidade de IA ANTES da fusão com a proveniência, para auditoria.';

create index if not exists historico_analises_provenance_status_idx
  on public.historico_analises (provenance_status);
