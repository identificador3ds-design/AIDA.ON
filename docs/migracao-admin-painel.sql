-- Migração: painel administrativo (configuração remota + planos/tokens das chaves)
--
-- Rode no SQL Editor do Supabase. Idempotente. Pressupõe que
-- docs/supabase-admin-setup.sql (função public.e_admin) e
-- aida_api/migracoes/migracao-api-keys.sql já foram executados.

-- 1. Configuração do site em uma linha única, lida por todas as páginas.
--    Antes ela vivia só no localStorage do navegador do admin — ou seja, não
--    valia para mais ninguém.
create table if not exists public.admin_config (
  id             integer primary key default 1 check (id = 1),
  config         jsonb not null default '{}'::jsonb,
  atualizado_em  timestamptz not null default now()
);

insert into public.admin_config (id, config) values (1, '{}'::jsonb)
on conflict (id) do nothing;

alter table public.admin_config enable row level security;

drop policy if exists "admin_config: leitura publica" on public.admin_config;
create policy "admin_config: leitura publica"
  on public.admin_config for select using (true);

drop policy if exists "admin_config: admin escreve" on public.admin_config;
create policy "admin_config: admin escreve"
  on public.admin_config for all
  using (public.e_admin()) with check (public.e_admin());

-- 2. Empresa, plano e cota de tokens por chave de API.
alter table public.api_keys add column if not exists empresa        text;
alter table public.api_keys add column if not exists contato        text;
alter table public.api_keys add column if not exists plano          text not null default 'free';
alter table public.api_keys add column if not exists tokens_total   integer not null default 0;
alter table public.api_keys add column if not exists tokens_usados  integer not null default 0;

comment on column public.api_keys.tokens_total is
  'Cota total de análises do plano. 0 = ilimitado.';

-- 3. Admin enxerga e administra chaves e log de chamadas pelo painel.
drop policy if exists "api_keys: admin tudo" on public.api_keys;
create policy "api_keys: admin tudo"
  on public.api_keys for all
  using (public.e_admin()) with check (public.e_admin());

drop policy if exists "api_calls: admin le" on public.api_calls;
create policy "api_calls: admin le"
  on public.api_calls for select using (public.e_admin());

-- 4. Débito de token por análise atendida.
--    A API já grava cada chamada em api_calls; o trigger debita 1 token da
--    chave sempre que entra uma análise com status 200. Assim a cota conta
--    mesmo com a API publicada antes desta migração.
create or replace function public.api_calls_debita_token()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  if new.status = 200 and new.rota like '/v1/analyze/%' and new.prefixo_chave is not null then
    update public.api_keys
       set tokens_usados = tokens_usados + 1
     where prefixo = new.prefixo_chave;
  end if;
  return new;
end;
$$;

drop trigger if exists api_calls_debita_token on public.api_calls;
create trigger api_calls_debita_token
  after insert on public.api_calls
  for each row execute function public.api_calls_debita_token();

-- Versão anterior desta migração criava uma RPC; não é mais usada.
drop function if exists public.api_consumir_token(text);

-- 5. Admin pode apagar contas (a tabela usuarios já tem policy de admin em
--    supabase-admin-setup.sql). Nada a fazer aqui.
