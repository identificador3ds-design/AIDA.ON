-- Migração: chaves e log de chamadas da AIDA API
--
-- Rode no SQL Editor do Supabase. É idempotente (IF NOT EXISTS), então pode ser
-- executada mais de uma vez sem efeito colateral.
--
-- A tabela guarda o HASH da chave (sha256), nunca o valor bruto. Isso não é
-- zelo decorativo: a service role que a API usa tem acesso total ao banco, e um
-- vazamento desta tabela com chaves em texto puro entregaria acesso à análise
-- para quem obtivesse o dump. Com hash, o dump não vale nada.
--
-- `prefixo` existe para você reconhecer a chave em listagens e logs sem
-- conseguir reconstruí-la — são os primeiros caracteres, não o suficiente para
-- autenticar.

create table if not exists public.api_keys (
  id                 uuid primary key default gen_random_uuid(),
  hash_chave         text not null unique,
  prefixo            text not null,
  descricao          text,
  escopo             text not null default 'analyze:image',
  limite_por_janela  integer not null default 60,
  revogada           boolean not null default false,
  criada_em          timestamptz not null default now(),
  ultimo_uso_em      timestamptz,
  revogada_em        timestamptz,
  expira_em          timestamptz
);

create index if not exists api_keys_hash_idx    on public.api_keys (hash_chave);
create index if not exists api_keys_prefixo_idx on public.api_keys (prefixo);

comment on column public.api_keys.hash_chave is
  'sha256 da chave. O valor bruto aparece uma única vez, na emissão, e não é recuperável.';
comment on column public.api_keys.limite_por_janela is
  'Cota de chamadas por janela (AIDA_API_JANELA_S). 0 suspende a chave sem revogá-la.';

-- Log de chamadas: auditoria e diagnóstico.
--
-- Metadado apenas. A imagem enviada NÃO é gravada, nem o nome original do
-- arquivo — nome de arquivo costuma carregar dado pessoal ("cpf-joao.jpg") e
-- não ajuda em nada a diagnosticar. O hash permite reconhecer que duas chamadas
-- trataram do mesmo arquivo sem guardar o arquivo.
create table if not exists public.api_calls (
  id             bigserial primary key,
  criada_em      timestamptz not null default now(),
  prefixo_chave  text,
  rota           text,
  status         integer,
  codigo_erro    text,
  duracao_s      double precision,
  duracao_core_s double precision,
  hash_arquivo   text,
  tamanho_bytes  bigint,
  resultado      text,
  cache          text,
  id_analise     text
);

create index if not exists api_calls_criada_em_idx on public.api_calls (criada_em desc);
create index if not exists api_calls_chave_idx     on public.api_calls (prefixo_chave, criada_em desc);

comment on table public.api_calls is
  'Metadado de chamadas da AIDA API. Retenção declarada no aviso de privacidade (docs/lgpd-inventario.md).';

-- RLS ligado e sem policy: nenhuma role pública alcança estas tabelas. A API
-- fala com elas pela service role, que passa por cima do RLS. Sem esta linha,
-- a chave anon exposta no front-end conseguiria ler a tabela de chaves.
alter table public.api_keys  enable row level security;
alter table public.api_calls enable row level security;

-- Descarte após a retenção declarada. Rode periodicamente (pg_cron ou manual):
--   delete from public.api_calls where criada_em < now() - interval '90 days';
