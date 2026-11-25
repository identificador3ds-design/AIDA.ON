-- ==========================================================================
-- AIDA API — garante o registro de chamadas e o débito de tokens
-- ==========================================================================
--
-- Sintoma que esta migração corrige: a análise pela API funciona, o "Último
-- uso" da chave atualiza, mas "Usados" continua em 0 no painel.
--
-- O débito acontece assim: a API grava uma linha em public.api_calls a cada
-- chamada, e o trigger api_calls_debita_token soma 1 em api_keys.tokens_usados
-- quando a linha é de uma análise atendida (status 200). Duas coisas quebram
-- isso: a tabela criada por uma versão antiga da migração, sem alguma coluna
-- que a API envia (o Supabase recusa a linha inteira), ou o trigger ausente.
--
-- Rode no SQL Editor do Supabase. É idempotente: pode rodar de novo.
-- ==========================================================================

begin;

-- 1. Colunas que a API envia (aida_api/registro.py).
alter table public.api_calls add column if not exists criada_em      timestamptz not null default now();
alter table public.api_calls add column if not exists prefixo_chave  text;
alter table public.api_calls add column if not exists rota           text;
alter table public.api_calls add column if not exists status         integer;
alter table public.api_calls add column if not exists codigo_erro    text;
alter table public.api_calls add column if not exists duracao_s      double precision;
alter table public.api_calls add column if not exists duracao_core_s double precision;
alter table public.api_calls add column if not exists hash_arquivo   text;
alter table public.api_calls add column if not exists tamanho_bytes  bigint;
alter table public.api_calls add column if not exists resultado      text;
alter table public.api_calls add column if not exists cache          text;
alter table public.api_calls add column if not exists id_analise     text;

-- 2. Débito de token por análise atendida (mesma função de
--    docs/migracao-admin-painel.sql, recriada aqui caso falte).
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

commit;

-- 3. Diagnóstico: últimas chamadas gravadas. Vazio depois de uma análise pela
--    API = a linha não está chegando (veja o log do Space: "aida_api_log_recusado").
select criada_em, prefixo_chave, rota, status, codigo_erro
  from public.api_calls
 order by criada_em desc
 limit 10;
