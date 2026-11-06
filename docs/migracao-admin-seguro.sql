-- ==========================================================================
-- AIDA.ON — painel administrativo blindado (2FA obrigatório, auditoria e API)
-- ==========================================================================
--
-- Rode no SQL Editor do Supabase DEPOIS de:
--   docs/supabase-admin-setup.sql, aida_api/migracoes/migracao-api-keys.sql,
--   docs/migracao-admin-painel.sql e docs/migracao-status-conta.sql.
-- É idempotente: pode rodar de novo sem efeito colateral.
--
-- MODELO DE AMEAÇA
--   O site é estático e a chave anon é pública. Tudo o que o navegador mostra
--   pode ser lido e alterado por quem o abrir; por isso NENHUMA decisão de
--   acesso fica no front-end. O banco decide, e só responde como admin quando
--   as TRÊS condições valem ao mesmo tempo:
--     1. o JWT traz `app_metadata.role = 'admin'` (só a service role grava);
--     2. a sessão passou pelo segundo fator TOTP (`aal = 'aal2'`) — senha
--        vazada, sozinha, não abre nada;
--     3. o usuário está em `public.admin_contas` com `ativo = true` — revogar
--        um admin vale na hora, sem esperar o JWT expirar.
--
-- PASSOS MANUAIS (não dá para fazer por SQL com segurança):
--   a) Authentication > Users > "Add user" > aida@gmail.com.br, com
--      "Auto Confirm User" marcado. A senha é digitada ali, NUNCA neste
--      arquivo nem em código: o repositório é público.
--   b) Authentication > Providers/Multi-Factor: TOTP habilitado (padrão).
--   c) Rode este script.
--   d) Abra https://aida-on.com.br/admin LOGO EM SEGUIDA e cadastre o
--      autenticador (Google Authenticator, Authy, 1Password...). Até o
--      cadastro, quem souber a senha poderia cadastrar o próprio aplicativo;
--      depois dele, um segundo fator só entra com sessão aal2.
-- ==========================================================================

begin;

create extension if not exists pgcrypto with schema extensions;


-- --------------------------------------------------------------------------
-- 1. Lista de administradores (segunda chave, independente do JWT)
-- --------------------------------------------------------------------------
create table if not exists public.admin_contas (
  user_id     uuid primary key references auth.users (id) on delete cascade,
  email       text not null,
  ativo       boolean not null default true,
  criado_em   timestamptz not null default now()
);

alter table public.admin_contas enable row level security;
-- Sem policy: nenhuma role pública lê ou escreve. Só funções security definer.
revoke all on public.admin_contas from anon, authenticated;

-- Conta administrativa nova.
update auth.users
   set raw_app_meta_data = coalesce(raw_app_meta_data, '{}'::jsonb) || '{"role":"admin"}'::jsonb
 where lower(email) = 'aida@gmail.com.br';

insert into public.admin_contas (user_id, email)
select id, lower(email) from auth.users where lower(email) = 'aida@gmail.com.br'
on conflict (user_id) do update set ativo = true;

-- Conta antiga: a senha dela esteve publicada no repositório. Perde o papel.
update auth.users
   set raw_app_meta_data = coalesce(raw_app_meta_data, '{}'::jsonb) - 'role' - 'roles' - 'claims_admin'
 where lower(email) = 'admin@gmail.com';

delete from public.admin_contas where email = 'admin@gmail.com';


-- --------------------------------------------------------------------------
-- 2. e_admin(): papel + 2FA + lista. Todas as policies existentes já usam esta
--    função, então o endurecimento vale para usuarios, admin_config, api_keys,
--    api_calls e historico sem reescrever cada policy.
-- --------------------------------------------------------------------------
create or replace function public.e_admin()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select coalesce(
    (auth.jwt() -> 'app_metadata' ->> 'role') = 'admin'
    and (auth.jwt() ->> 'aal') = 'aal2'
    and exists (
      select 1 from public.admin_contas a
       where a.user_id = auth.uid() and a.ativo
    ),
    false
  );
$$;

revoke all on function public.e_admin() from public;
grant execute on function public.e_admin() to anon, authenticated;

create or replace function public.exigir_admin()
returns void
language plpgsql
stable
security definer
set search_path = public
as $$
begin
  if not public.e_admin() then
    raise exception 'acesso negado' using errcode = '42501';
  end if;
end;
$$;

revoke all on function public.exigir_admin() from public, anon, authenticated;


-- --------------------------------------------------------------------------
-- 3. Trilha de auditoria (somente acréscimo)
-- --------------------------------------------------------------------------
create table if not exists public.admin_audit (
  id           bigserial primary key,
  criado_em    timestamptz not null default now(),
  admin_id     uuid,
  admin_email  text,
  acao         text not null,
  alvo         text,
  detalhes     jsonb not null default '{}'::jsonb,
  ip           text,
  user_agent   text
);

create index if not exists admin_audit_criado_em_idx on public.admin_audit (criado_em desc);

alter table public.admin_audit enable row level security;
revoke all on public.admin_audit from anon, authenticated;
grant select on public.admin_audit to authenticated;

drop policy if exists "admin_audit: admin le" on public.admin_audit;
create policy "admin_audit: admin le"
  on public.admin_audit for select to authenticated using (public.e_admin());

-- Nem o admin edita ou apaga a trilha pelo navegador: sem grant e sem policy.
create or replace function public.admin_audit_imutavel()
returns trigger
language plpgsql
as $$
begin
  raise exception 'a trilha de auditoria não pode ser alterada';
end;
$$;

drop trigger if exists admin_audit_imutavel on public.admin_audit;
create trigger admin_audit_imutavel
  before update or delete on public.admin_audit
  for each row execute function public.admin_audit_imutavel();

create or replace function public.registrar_auditoria(p_acao text, p_alvo text, p_detalhes jsonb)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  cabecalhos jsonb;
begin
  begin
    cabecalhos := nullif(current_setting('request.headers', true), '')::jsonb;
  exception when others then
    cabecalhos := null;
  end;

  insert into public.admin_audit (admin_id, admin_email, acao, alvo, detalhes, ip, user_agent)
  values (
    auth.uid(),
    coalesce(auth.jwt() ->> 'email', auth.role()),
    left(p_acao, 80),
    left(p_alvo, 200),
    coalesce(p_detalhes, '{}'::jsonb),
    left(coalesce(cabecalhos ->> 'cf-connecting-ip',
                  split_part(cabecalhos ->> 'x-forwarded-for', ',', 1)), 64),
    left(cabecalhos ->> 'user-agent', 300)
  );
end;
$$;

revoke all on function public.registrar_auditoria(text, text, jsonb) from public, anon, authenticated;

-- Diferença entre duas linhas, sem campos sensíveis.
create or replace function public.diferenca_jsonb(antigo jsonb, novo jsonb)
returns jsonb
language sql
immutable
as $$
  select coalesce(jsonb_object_agg(k, jsonb_build_object('de', antigo -> k, 'para', novo -> k)), '{}'::jsonb)
    from jsonb_object_keys(coalesce(novo, '{}'::jsonb) || coalesce(antigo, '{}'::jsonb)) k
   where k not in ('hash_chave')
     and (antigo -> k) is distinct from (novo -> k);
$$;

-- Gatilhos: registram toda alteração administrativa, venha do painel, de uma
-- chamada REST direta ou do SQL Editor. Não dá para "esquecer" de auditar.
create or replace function public.auditar_api_keys()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  dif jsonb;
begin
  if tg_op = 'INSERT' then
    perform public.registrar_auditoria('api_key.emitida', new.prefixo,
      to_jsonb(new) - 'hash_chave');
  elsif tg_op = 'DELETE' then
    perform public.registrar_auditoria('api_key.apagada', old.prefixo,
      to_jsonb(old) - 'hash_chave');
  else
    dif := public.diferenca_jsonb(to_jsonb(old), to_jsonb(new)) - 'tokens_usados' - 'ultimo_uso_em';
    -- Débito de token e marcação de uso pela própria API não poluem a trilha;
    -- zerar o uso pelo painel, sim, é registrado.
    if dif <> '{}'::jsonb or (public.e_admin() and new.tokens_usados is distinct from old.tokens_usados) then
      perform public.registrar_auditoria('api_key.alterada', new.prefixo,
        public.diferenca_jsonb(to_jsonb(old), to_jsonb(new)) - 'ultimo_uso_em');
    end if;
  end if;
  return null;
end;
$$;

drop trigger if exists auditar_api_keys on public.api_keys;
create trigger auditar_api_keys
  after insert or update or delete on public.api_keys
  for each row execute function public.auditar_api_keys();

create or replace function public.auditar_admin_config()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  perform public.registrar_auditoria('site.config_alterada', 'admin_config',
    public.diferenca_jsonb(
      case when tg_op = 'INSERT' then '{}'::jsonb else old.config end,
      new.config));
  return null;
end;
$$;

drop trigger if exists auditar_admin_config on public.admin_config;
create trigger auditar_admin_config
  after insert or update on public.admin_config
  for each row execute function public.auditar_admin_config();

create or replace function public.auditar_usuarios_status()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  if new.status is distinct from old.status then
    perform public.registrar_auditoria('usuario.status', new.email,
      jsonb_build_object('de', old.status, 'para', new.status));
  end if;
  return null;
end;
$$;

drop trigger if exists auditar_usuarios_status on public.usuarios;
create trigger auditar_usuarios_status
  after update on public.usuarios
  for each row execute function public.auditar_usuarios_status();


-- --------------------------------------------------------------------------
-- 4. Privilégio mínimo nas tabelas da API
-- --------------------------------------------------------------------------
-- O admin LÊ chaves e chamadas pelo painel; escreve só pelas funções abaixo,
-- que validam cada campo. O hash da chave nem é legível pelo navegador.
revoke all on public.api_keys from anon, authenticated;
grant select (id, prefixo, descricao, empresa, contato, plano, tokens_total, tokens_usados,
              escopo, limite_por_janela, revogada, criada_em, ultimo_uso_em, revogada_em,
              expira_em)
  on public.api_keys to authenticated;

drop policy if exists "api_keys: admin tudo" on public.api_keys;
drop policy if exists "api_keys: admin le" on public.api_keys;
create policy "api_keys: admin le"
  on public.api_keys for select to authenticated using (public.e_admin());

revoke all on public.api_calls from anon, authenticated;
grant select on public.api_calls to authenticated;

-- A configuração pública continua legível por todos; só o admin (aal2) grava.
revoke insert, update, delete, truncate on public.admin_config from anon;


-- --------------------------------------------------------------------------
-- 5. Funções do painel (RPC). Cada uma revalida o admin no servidor.
-- --------------------------------------------------------------------------
create or replace function public.admin_validar_texto(valor text, campo text, maximo integer, obrigatorio boolean)
returns text
language plpgsql
immutable
as $$
declare
  limpo text := nullif(btrim(coalesce(valor, '')), '');
begin
  if limpo is null and obrigatorio then
    raise exception '% é obrigatório', campo using errcode = '22023';
  end if;
  if limpo is not null and length(limpo) > maximo then
    raise exception '% passa de % caracteres', campo, maximo using errcode = '22023';
  end if;
  if limpo ~ '[[:cntrl:]]' then
    raise exception '% tem caracteres de controle', campo using errcode = '22023';
  end if;
  return limpo;
end;
$$;

create or replace function public.admin_validar_plano(p_plano text)
returns text
language plpgsql
immutable
as $$
begin
  if coalesce(p_plano, '') not in ('free', 'basico', 'pro', 'enterprise', 'custom') then
    raise exception 'plano inválido' using errcode = '22023';
  end if;
  return p_plano;
end;
$$;

-- Confirma no servidor que a sessão é de admin e registra o acesso.
create or replace function public.admin_registrar_acesso()
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
begin
  perform public.exigir_admin();
  perform public.registrar_auditoria('admin.acesso', auth.jwt() ->> 'email', '{}'::jsonb);
  return jsonb_build_object('email', auth.jwt() ->> 'email', 'aal', auth.jwt() ->> 'aal');
end;
$$;

-- Emissão: a chave nasce no banco, com gerador criptográfico, e só o hash
-- fica gravado. O valor bruto volta UMA vez nesta resposta. Mesmo formato da
-- emissão em Python (aida_api/chaves_api.py): "aida_" + 43 caracteres base64url.
create or replace function public.admin_emitir_chave(
  p_empresa            text,
  p_contato            text,
  p_descricao          text,
  p_plano              text,
  p_tokens_total       integer,
  p_limite_por_janela  integer,
  p_dias_validade      integer
)
returns jsonb
language plpgsql
volatile
security definer
set search_path = public
as $$
declare
  v_chave   text;
  v_linha   public.api_keys;
begin
  perform public.exigir_admin();

  if coalesce(p_tokens_total, 0) < 0 or p_tokens_total > 100000000 then
    raise exception 'cota de tokens inválida' using errcode = '22023';
  end if;
  if coalesce(p_limite_por_janela, 60) < 0 or p_limite_por_janela > 100000 then
    raise exception 'limite por janela inválido' using errcode = '22023';
  end if;
  if p_dias_validade is not null and (p_dias_validade < 1 or p_dias_validade > 3650) then
    raise exception 'validade deve ficar entre 1 e 3650 dias' using errcode = '22023';
  end if;

  v_chave := 'aida_' || rtrim(translate(encode(extensions.gen_random_bytes(32), 'base64'), '+/', '-_'), '=');

  insert into public.api_keys (hash_chave, prefixo, descricao, empresa, contato, plano,
                               tokens_total, tokens_usados, escopo, limite_por_janela,
                               revogada, expira_em)
  values (
    encode(extensions.digest(v_chave, 'sha256'), 'hex'),
    left(v_chave, 11),
    public.admin_validar_texto(p_descricao, 'descrição', 200, false),
    public.admin_validar_texto(p_empresa, 'empresa', 120, true),
    public.admin_validar_texto(p_contato, 'contato', 160, false),
    public.admin_validar_plano(coalesce(p_plano, 'free')),
    coalesce(p_tokens_total, 0),
    0,
    'analyze:image',
    coalesce(p_limite_por_janela, 60),
    false,
    case when p_dias_validade is null then null else now() + make_interval(days => p_dias_validade) end
  )
  returning * into v_linha;

  return jsonb_build_object('id', v_linha.id, 'prefixo', v_linha.prefixo, 'chave', v_chave);
end;
$$;

create or replace function public.admin_atualizar_chave(
  p_id                 uuid,
  p_empresa            text,
  p_contato            text,
  p_descricao          text,
  p_plano              text,
  p_tokens_total       integer,
  p_limite_por_janela  integer,
  p_expira_em          timestamptz,
  p_sem_expiracao      boolean
)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  perform public.exigir_admin();

  if p_tokens_total is not null and (p_tokens_total < 0 or p_tokens_total > 100000000) then
    raise exception 'cota de tokens inválida' using errcode = '22023';
  end if;
  if p_limite_por_janela is not null and (p_limite_por_janela < 0 or p_limite_por_janela > 100000) then
    raise exception 'limite por janela inválido' using errcode = '22023';
  end if;

  update public.api_keys
     set empresa           = coalesce(public.admin_validar_texto(p_empresa, 'empresa', 120, false), empresa),
         contato           = case when p_contato is null then contato
                                  else public.admin_validar_texto(p_contato, 'contato', 160, false) end,
         descricao         = case when p_descricao is null then descricao
                                  else public.admin_validar_texto(p_descricao, 'descrição', 200, false) end,
         plano             = case when p_plano is null then plano else public.admin_validar_plano(p_plano) end,
         tokens_total      = coalesce(p_tokens_total, tokens_total),
         limite_por_janela = coalesce(p_limite_por_janela, limite_por_janela),
         expira_em         = case when coalesce(p_sem_expiracao, false) then null
                                  else coalesce(p_expira_em, expira_em) end
   where id = p_id and not revogada;

  if not found then
    raise exception 'chave inexistente ou revogada' using errcode = 'P0002';
  end if;
end;
$$;

create or replace function public.admin_adicionar_tokens(p_id uuid, p_quantidade integer)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  perform public.exigir_admin();

  if p_quantidade is null or p_quantidade < 1 or p_quantidade > 100000000 then
    raise exception 'quantidade inválida' using errcode = '22023';
  end if;

  update public.api_keys
     set tokens_total = case when tokens_total = 0 then tokens_usados + p_quantidade
                             else tokens_total + p_quantidade end
   where id = p_id and not revogada;

  if not found then
    raise exception 'chave inexistente ou revogada' using errcode = 'P0002';
  end if;
end;
$$;

create or replace function public.admin_zerar_uso_chave(p_id uuid)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  perform public.exigir_admin();
  update public.api_keys set tokens_usados = 0 where id = p_id and not revogada;
  if not found then
    raise exception 'chave inexistente ou revogada' using errcode = 'P0002';
  end if;
end;
$$;

-- Revogação é definitiva: chave revogada não volta. Para pausar, use limite 0.
create or replace function public.admin_revogar_chave(p_id uuid)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  perform public.exigir_admin();
  update public.api_keys set revogada = true, revogada_em = now() where id = p_id and not revogada;
  if not found then
    raise exception 'chave inexistente ou já revogada' using errcode = 'P0002';
  end if;
end;
$$;

create or replace function public.admin_resumo()
returns jsonb
language plpgsql
stable
security definer
set search_path = public
as $$
declare
  r jsonb;
begin
  perform public.exigir_admin();

  select jsonb_build_object(
    'usuarios',           (select count(*) from public.usuarios),
    'usuarios_bloqueados',(select count(*) from public.usuarios where status <> 'active'),
    'analises',           (select count(*) from public.historico_analises),
    'chaves_ativas',      (select count(*) from public.api_keys where not revogada
                             and (expira_em is null or expira_em > now())),
    'chaves_revogadas',   (select count(*) from public.api_keys where revogada),
    'empresas',           (select count(distinct lower(empresa)) from public.api_keys
                            where not revogada and empresa is not null),
    'tokens_usados',      (select coalesce(sum(tokens_usados), 0) from public.api_keys),
    'tokens_contratados', (select coalesce(sum(tokens_total), 0) from public.api_keys
                            where not revogada and tokens_total > 0),
    'tokens_disponiveis', (select coalesce(sum(greatest(tokens_total - tokens_usados, 0)), 0)
                             from public.api_keys where not revogada and tokens_total > 0),
    'chamadas_24h',       (select count(*) from public.api_calls where criada_em > now() - interval '24 hours'),
    'erros_24h',          (select count(*) from public.api_calls
                            where criada_em > now() - interval '24 hours' and status >= 400),
    'chamadas_30d',       (select count(*) from public.api_calls where criada_em > now() - interval '30 days')
  ) into r;

  return r;
end;
$$;

-- Execução: só usuários autenticados chegam às funções; dentro delas,
-- exigir_admin() barra quem não é admin com 2FA.
do $$
declare
  f text;
begin
  foreach f in array array[
    'public.admin_registrar_acesso()',
    'public.admin_emitir_chave(text, text, text, text, integer, integer, integer)',
    'public.admin_atualizar_chave(uuid, text, text, text, text, integer, integer, timestamptz, boolean)',
    'public.admin_adicionar_tokens(uuid, integer)',
    'public.admin_zerar_uso_chave(uuid)',
    'public.admin_revogar_chave(uuid)',
    'public.admin_resumo()'
  ] loop
    execute format('revoke all on function %s from public, anon', f);
    execute format('grant execute on function %s to authenticated', f);
  end loop;
end;
$$;

revoke all on function public.admin_validar_texto(text, text, integer, boolean) from public, anon, authenticated;
revoke all on function public.admin_validar_plano(text) from public, anon, authenticated;
revoke all on function public.diferenca_jsonb(jsonb, jsonb) from public, anon, authenticated;
revoke all on function public.auditar_api_keys() from public, anon, authenticated;
revoke all on function public.auditar_admin_config() from public, anon, authenticated;
revoke all on function public.auditar_usuarios_status() from public, anon, authenticated;


-- --------------------------------------------------------------------------
-- 6. Exclusão de conta: a proteção da conta admin deixa de depender do e-mail
-- --------------------------------------------------------------------------
create or replace function public.excluir_minha_conta()
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
  usuario_id uuid := auth.uid();
  usuario_email text;
begin
  if usuario_id is null then
    raise exception 'Usuario nao autenticado';
  end if;

  if exists (select 1 from public.admin_contas a where a.user_id = usuario_id) then
    raise exception 'A conta administrativa nao pode ser excluida por este fluxo';
  end if;

  select email into usuario_email
  from auth.users
  where id = usuario_id;

  delete from public.historico_analises
  where user_id = usuario_id;

  delete from public.usuarios
  where usuario_email is not null
    and lower(email) = lower(usuario_email);

  delete from auth.users
  where id = usuario_id;
end;
$$;

revoke all on function public.excluir_minha_conta() from public;
revoke all on function public.excluir_minha_conta() from anon;
grant execute on function public.excluir_minha_conta() to authenticated;

commit;

-- --------------------------------------------------------------------------
-- Conferência
-- --------------------------------------------------------------------------
--   select email, raw_app_meta_data from auth.users where email in ('aida@gmail.com.br', 'admin@gmail.com');
--   select * from public.admin_contas;
--   -- Como anon/autenticado comum, deve falhar com 42501:
--   select public.admin_resumo();
--
-- Revogar um admin na hora:
--   update public.admin_contas set ativo = false where email = '...';
--
-- Retenção da auditoria (rodar como postgres; o gatilho bloqueia o navegador,
-- então desligue-o só durante a limpeza):
--   alter table public.admin_audit disable trigger admin_audit_imutavel;
--   delete from public.admin_audit where criado_em < now() - interval '1 year';
--   alter table public.admin_audit enable trigger admin_audit_imutavel;
