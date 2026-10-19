-- ==========================================================================
-- AIDA.ON — bloqueio de conta no SERVIDOR e fim do e-mail exposto (P1-3)
-- ==========================================================================
--
-- PROBLEMA (verificado em 08/10/2026):
--   * o bloqueio/exclusão de conta pelo painel vivia em `admin_config.config.accountStates`,
--     uma tabela de LEITURA PÚBLICA (política "admin_config: leitura publica"): o e-mail das
--     contas bloqueadas ficava visível para qualquer visitante;
--   * o bloqueio só era aplicado no navegador (localStorage), então era contornável.
--
-- SOLUÇÃO:
--   * `usuarios.status` ('active' | 'blocked' | 'deleted'), que só o admin altera;
--   * o RLS do histórico recusa gravação de conta que não está 'active';
--   * `accountStates` sai de `admin_config` (o painel novo deixa de publicá-lo).
--
-- ORDEM: rodar DEPOIS de publicar o site com o script-administrador.js novo (ele grava o
-- status em `usuarios`) e DEPOIS de docs/migracao-rls-historico-evidencias.sql.
-- Depende de public.e_admin() (docs/supabase-admin-setup.sql).
-- ==========================================================================

begin;

alter table public.usuarios add column if not exists status text not null default 'active';
alter table public.usuarios drop constraint if exists usuarios_status_valido;
alter table public.usuarios add constraint usuarios_status_valido
  check (status in ('active', 'blocked', 'deleted'));

-- Migra o que o painel tinha publicado (e-mail -> status) antes de apagar de admin_config.
update public.usuarios u
   set status = c.value ->> 'status'
  from public.admin_config a,
       jsonb_each(coalesce(a.config -> 'accountStates', '{}'::jsonb)) c
 where a.id = 1
   and lower(u.email) = lower(c.key)
   and c.value ->> 'status' in ('blocked', 'deleted');

update public.admin_config set config = config - 'accountStates' where id = 1;

-- Só o admin muda `status`. A política "usuarios: atualizacao propria" deixa o dono editar
-- a própria linha — sem esta trava, uma conta bloqueada se desbloquearia sozinha.
create or replace function public.usuarios_status_so_admin()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  if tg_op = 'INSERT' and coalesce(new.status, 'active') <> 'active' and not public.e_admin() then
    raise exception 'status de conta só pode ser definido pelo administrador';
  end if;
  if tg_op = 'UPDATE' and new.status is distinct from old.status and not public.e_admin() then
    raise exception 'status de conta só pode ser alterado pelo administrador';
  end if;
  return new;
end;
$$;

drop trigger if exists usuarios_status_so_admin on public.usuarios;
create trigger usuarios_status_so_admin
  before insert or update on public.usuarios
  for each row execute function public.usuarios_status_so_admin();

-- Conta bloqueada/excluída não grava histórico (o bloqueio passa a valer no servidor).
drop policy if exists "historico: dono insere" on public.historico_analises;
create policy "historico: dono insere"
  on public.historico_analises for insert to authenticated
  with check (
    user_id::text = auth.uid()::text
    and not exists (
      select 1 from public.usuarios u
       where lower(u.email) = lower(auth.jwt() ->> 'email')
         and u.status <> 'active'
    )
  );

commit;

-- Conferência:
--   select config ? 'accountStates' from public.admin_config where id = 1;      -- false
--   select status, count(*) from public.usuarios group by status;
--
-- ROLLBACK:
--   drop trigger if exists usuarios_status_so_admin on public.usuarios;
--   drop function if exists public.usuarios_status_so_admin();
--   (a política de insert volta a ser a de migracao-rls-historico-evidencias.sql)
--   alter table public.usuarios drop column status;
