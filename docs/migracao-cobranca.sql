-- Migração: cobrança por créditos (assinaturas da API, uso por ciclo) e
-- formulário comercial da página de preços.
--
-- Rode no SQL Editor do Supabase. Idempotente. Pressupõe
-- aida_api/migracoes/migracao-api-keys.sql e docs/supabase-admin-setup.sql
-- (função public.e_admin) já executados.
--
-- Regras (config/pricing.json):
--   imagem = 1 crédito; vídeo = 10 créditos por minuto iniciado.
--   Ciclo mensal ancorado na data da assinatura. Créditos NÃO acumulam.
--   overage 'block'  (API Free): débito acima do incluído é recusado (a API responde 429).
--   overage 'charge' (pagos):    passa, e o que exceder vira excedente do ciclo.
--
-- Os termos (créditos incluídos, preço do excedente, moeda) são copiados para
-- a assinatura no momento da contratação: mudar o pricing.json depois não
-- altera retroativamente o que já foi vendido.
--
-- Chave com assinatura: deixe `api_keys.tokens_total = 0` (a cota legada do
-- painel, debitada pelo trigger api_calls_debita_token, continua existindo
-- para chaves antigas e é independente desta).

-- ------------------------------------------------------------------------- --
-- 1. Assinaturas
-- ------------------------------------------------------------------------- --
create table if not exists public.assinaturas_api (
  id                  uuid primary key default gen_random_uuid(),
  chave_id            uuid not null references public.api_keys (id) on delete cascade,
  usuario_id          uuid,
  plano_id            text not null,
  mercado             text not null check (mercado in ('BR', 'INTL')),
  moeda               text not null check (moeda in ('BRL', 'USD')),
  ciclo_cobranca      text not null default 'monthly' check (ciclo_cobranca in ('monthly', 'annual')),
  creditos_incluidos  integer not null check (creditos_incluidos >= 0),
  excedente           text not null check (excedente in ('block', 'charge', 'negotiated')),
  preco_excedente     numeric(12, 6),
  ancora_ciclo        timestamptz not null default now(),
  ativa               boolean not null default true,
  gateway_assinatura  text,
  criada_em           timestamptz not null default now(),
  cancelada_em        timestamptz,
  constraint assinaturas_api_excedente_com_preco
    check (excedente <> 'charge' or preco_excedente is not null)
);

-- Uma assinatura ativa por chave.
create unique index if not exists assinaturas_api_uma_ativa
  on public.assinaturas_api (chave_id) where ativa;

comment on table public.assinaturas_api is
  'Plano de cada chave da API. Termos copiados de config/pricing.json na contratação.';

-- ------------------------------------------------------------------------- --
-- 2. Uso por ciclo (saldo e excedente) e lançamentos
-- ------------------------------------------------------------------------- --
create table if not exists public.uso_ciclos (
  assinatura_id        uuid not null references public.assinaturas_api (id) on delete cascade,
  ciclo_inicio         timestamptz not null,
  ciclo_fim            timestamptz not null,
  creditos_incluidos   integer not null,
  creditos_usados      integer not null default 0 check (creditos_usados >= 0),
  creditos_excedentes  integer generated always as (greatest(0, creditos_usados - creditos_incluidos)) stored,
  atualizado_em        timestamptz not null default now(),
  primary key (assinatura_id, ciclo_inicio)
);

create table if not exists public.uso_creditos (
  id             bigserial primary key,
  criada_em      timestamptz not null default now(),
  assinatura_id  uuid not null references public.assinaturas_api (id) on delete cascade,
  ciclo_inicio   timestamptz not null,
  tipo           text not null check (tipo in ('image', 'video', 'estorno')),
  creditos       integer not null,
  referencia     text
);

create index if not exists uso_creditos_ciclo_idx on public.uso_creditos (assinatura_id, ciclo_inicio);

comment on table public.uso_ciclos is
  'Saldo por ciclo de cobrança. creditos_excedentes alimenta a fatura do excedente.';
comment on table public.uso_creditos is
  'Livro de débitos e estornos (auditoria). A referência é o sha256 do arquivo, nunca o arquivo.';

alter table public.assinaturas_api enable row level security;
alter table public.uso_ciclos      enable row level security;
alter table public.uso_creditos    enable row level security;

drop policy if exists "assinaturas_api: admin le" on public.assinaturas_api;
create policy "assinaturas_api: admin le" on public.assinaturas_api for select using (public.e_admin());
drop policy if exists "uso_ciclos: admin le" on public.uso_ciclos;
create policy "uso_ciclos: admin le" on public.uso_ciclos for select using (public.e_admin());
drop policy if exists "uso_creditos: admin le" on public.uso_creditos;
create policy "uso_creditos: admin le" on public.uso_creditos for select using (public.e_admin());

-- ------------------------------------------------------------------------- --
-- 3. Ciclo mensal ancorado (mesma regra de aida_api/medicao.ciclo_atual:
--    dia 31 vira o último dia do mês mais curto — o "+ interval" do Postgres
--    já faz esse ajuste).
-- ------------------------------------------------------------------------- --
create or replace function public.cobranca_ciclo(p_ancora timestamptz, p_agora timestamptz)
returns table (inicio timestamptz, fim timestamptz)
language plpgsql
stable  -- timestamptz + meses depende do TimeZone da sessão
as $$
declare
  v_meses integer;
begin
  if p_agora < p_ancora then
    return query select p_ancora, p_ancora + interval '1 month';
    return;
  end if;
  v_meses := (extract(year from p_agora) - extract(year from p_ancora)) * 12
           + (extract(month from p_agora) - extract(month from p_ancora));
  if p_ancora + make_interval(months => v_meses) > p_agora then
    v_meses := v_meses - 1;
  end if;
  return query select p_ancora + make_interval(months => v_meses),
                      p_ancora + make_interval(months => v_meses + 1);
end;
$$;

-- Resposta comum das RPCs (lida por aida_api/medicao.MedidorSupabase).
create or replace function public.cobranca_estado(
  p_ass public.assinaturas_api, p_inicio timestamptz, p_fim timestamptz,
  p_usados integer, p_permitido boolean, p_lancamento bigint default null
)
returns jsonb
language sql
immutable
as $$
  select jsonb_build_object(
    'medido', true,
    'permitido', p_permitido,
    'plano_id', p_ass.plano_id,
    'excedente', p_ass.excedente,
    'incluidos', p_ass.creditos_incluidos,
    'usados', p_usados,
    'preco_excedente', p_ass.preco_excedente,
    'moeda', p_ass.moeda,
    'ciclo_inicio', p_inicio,
    'ciclo_fim', p_fim,
    'lancamento_id', p_lancamento
  );
$$;

-- ------------------------------------------------------------------------- --
-- 4. Débito atômico: o FOR UPDATE na linha do ciclo serializa chamadas
--    simultâneas da mesma chave, então o plano grátis não passa do limite.
-- ------------------------------------------------------------------------- --
create or replace function public.cobranca_debitar(
  p_hash_chave text, p_creditos integer, p_tipo text, p_referencia text default null
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_ass     public.assinaturas_api;
  v_inicio  timestamptz;
  v_fim     timestamptz;
  v_usados  integer;
  v_lanc    bigint;
begin
  if p_creditos is null or p_creditos < 1 or p_creditos > 1000000 then
    raise exception 'quantidade de créditos inválida' using errcode = '22023';
  end if;
  if p_tipo not in ('image', 'video') then
    raise exception 'tipo de uso inválido' using errcode = '22023';
  end if;

  select a.* into v_ass
    from public.assinaturas_api a
    join public.api_keys k on k.id = a.chave_id
   where k.hash_chave = p_hash_chave and a.ativa
   limit 1;
  if not found then
    return jsonb_build_object('medido', false);
  end if;

  select c.inicio, c.fim into v_inicio, v_fim from public.cobranca_ciclo(v_ass.ancora_ciclo, now()) c;

  insert into public.uso_ciclos (assinatura_id, ciclo_inicio, ciclo_fim, creditos_incluidos)
  values (v_ass.id, v_inicio, v_fim, v_ass.creditos_incluidos)
  on conflict (assinatura_id, ciclo_inicio) do nothing;

  select creditos_usados into v_usados
    from public.uso_ciclos
   where assinatura_id = v_ass.id and ciclo_inicio = v_inicio
   for update;

  if v_ass.excedente = 'block' and v_usados + p_creditos > v_ass.creditos_incluidos then
    return public.cobranca_estado(v_ass, v_inicio, v_fim, v_usados, false);
  end if;

  update public.uso_ciclos
     set creditos_usados = creditos_usados + p_creditos, atualizado_em = now()
   where assinatura_id = v_ass.id and ciclo_inicio = v_inicio
  returning creditos_usados into v_usados;

  insert into public.uso_creditos (assinatura_id, ciclo_inicio, tipo, creditos, referencia)
  values (v_ass.id, v_inicio, p_tipo, p_creditos, left(p_referencia, 128))
  returning id into v_lanc;

  return public.cobranca_estado(v_ass, v_inicio, v_fim, v_usados, true, v_lanc);
end;
$$;

-- Estorno de uma análise que falhou depois do débito.
create or replace function public.cobranca_estornar(
  p_hash_chave text, p_creditos integer, p_ciclo_inicio timestamptz, p_referencia text default null
)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  v_ass public.assinaturas_api;
begin
  if p_creditos is null or p_creditos < 1 or p_creditos > 1000000 then
    raise exception 'quantidade de créditos inválida' using errcode = '22023';
  end if;

  select a.* into v_ass
    from public.assinaturas_api a
    join public.api_keys k on k.id = a.chave_id
   where k.hash_chave = p_hash_chave and a.ativa
   limit 1;
  if not found then
    return;
  end if;

  update public.uso_ciclos
     set creditos_usados = greatest(0, creditos_usados - p_creditos), atualizado_em = now()
   where assinatura_id = v_ass.id and ciclo_inicio = p_ciclo_inicio;

  insert into public.uso_creditos (assinatura_id, ciclo_inicio, tipo, creditos, referencia)
  values (v_ass.id, p_ciclo_inicio, 'estorno', -p_creditos, left(p_referencia, 128));
end;
$$;

-- Consulta do ciclo atual (GET /v1/usage). Não cria linha nem trava.
create or replace function public.cobranca_uso(p_hash_chave text)
returns jsonb
language plpgsql
stable
security definer
set search_path = public
as $$
declare
  v_ass     public.assinaturas_api;
  v_inicio  timestamptz;
  v_fim     timestamptz;
  v_usados  integer;
begin
  select a.* into v_ass
    from public.assinaturas_api a
    join public.api_keys k on k.id = a.chave_id
   where k.hash_chave = p_hash_chave and a.ativa
   limit 1;
  if not found then
    return jsonb_build_object('medido', false);
  end if;

  select c.inicio, c.fim into v_inicio, v_fim from public.cobranca_ciclo(v_ass.ancora_ciclo, now()) c;
  select coalesce(max(creditos_usados), 0) into v_usados
    from public.uso_ciclos
   where assinatura_id = v_ass.id and ciclo_inicio = v_inicio;

  return public.cobranca_estado(v_ass, v_inicio, v_fim, v_usados, true);
end;
$$;

-- Só a service role (a borda da API) chama as RPCs de cobrança. Sem isto, a
-- chave anon do front-end poderia debitar ou estornar créditos de terceiros.
revoke all on function public.cobranca_debitar(text, integer, text, text)          from public, anon, authenticated;
revoke all on function public.cobranca_estornar(text, integer, timestamptz, text)  from public, anon, authenticated;
revoke all on function public.cobranca_uso(text)                                    from public, anon, authenticated;
grant execute on function public.cobranca_debitar(text, integer, text, text)         to service_role;
grant execute on function public.cobranca_estornar(text, integer, timestamptz, text) to service_role;
grant execute on function public.cobranca_uso(text)                                   to service_role;

-- ------------------------------------------------------------------------- --
-- 5. Formulário comercial (Enterprise, Checagem/ONG, contratação, chave grátis)
-- ------------------------------------------------------------------------- --
-- Dado pessoal: nome, empresa e e-mail de quem pede contato. Inventariado em
-- docs/lgpd-inventario.md. Retenção sugerida: 12 meses (PENDENTE de validação).
create table if not exists public.contatos_comerciais (
  id               uuid primary key default gen_random_uuid(),
  criado_em        timestamptz not null default now(),
  tipo             text not null check (tipo in ('enterprise', 'checagem_ong', 'subscribe', 'api_free')),
  plano_id         text check (plano_id is null or char_length(plano_id) <= 40),
  mercado          text check (mercado is null or mercado in ('BR', 'INTL')),
  idioma           text check (idioma is null or idioma in ('pt-BR', 'en-US')),
  nome             text not null check (char_length(btrim(nome)) between 1 and 120),
  empresa          text not null check (char_length(btrim(empresa)) between 1 and 160),
  email            text not null check (char_length(email) <= 254 and email ~ '^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$'),
  volume_estimado  bigint not null check (volume_estimado between 1 and 1000000000),
  mensagem         text check (mensagem is null or char_length(mensagem) <= 2000),
  consentimento    boolean not null check (consentimento),
  atendido_em      timestamptz
);

alter table public.contatos_comerciais enable row level security;

-- O público só INSERE, e só as colunas do formulário (não escolhe criado_em,
-- id nem atendido_em). Não há policy de SELECT para o público: quem envia não
-- lê de volta nem o próprio registro — por isso o site usa Prefer: return=minimal.
revoke all on public.contatos_comerciais from anon, authenticated;
grant insert (tipo, plano_id, mercado, idioma, nome, empresa, email, volume_estimado, mensagem, consentimento)
  on public.contatos_comerciais to anon, authenticated;

drop policy if exists "contatos_comerciais: publico insere" on public.contatos_comerciais;
create policy "contatos_comerciais: publico insere"
  on public.contatos_comerciais for insert to anon, authenticated
  with check (consentimento and atendido_em is null);

drop policy if exists "contatos_comerciais: admin le" on public.contatos_comerciais;
create policy "contatos_comerciais: admin le"
  on public.contatos_comerciais for select using (public.e_admin());

drop policy if exists "contatos_comerciais: admin atualiza" on public.contatos_comerciais;
create policy "contatos_comerciais: admin atualiza"
  on public.contatos_comerciais for update using (public.e_admin()) with check (public.e_admin());

grant select, update on public.contatos_comerciais to authenticated;

-- Descarte após a retenção (rode periodicamente quando o prazo for validado):
--   delete from public.contatos_comerciais where criado_em < now() - interval '12 months';
