-- ==========================================================================
-- AIDA.ON — configuracao do acesso administrativo no Supabase
-- ==========================================================================
--
-- Rode este script no SQL Editor do painel do Supabase.
-- Ele resolve o item 1 do RELATORIO-MELHORIAS-AIDA.md: tirar a decisao de
-- "quem e admin" do navegador e coloca-la no banco.
--
-- ANTES DE RODAR — passos manuais obrigatorios (nao da para automatizar aqui):
--   1. Authentication > Users > conta admin@gmail.com > "Reset password".
--      A senha antiga (`admin3ds`) estava publicada no JS e esta comprometida.
--      Troque por uma senha longa e unica, guardada em gerenciador de senhas.
--   2. Se a conta admin ainda nao existir no Supabase Auth, crie-a por
--      Authentication > Users > "Add user" (com e-mail confirmado).
-- ==========================================================================


-- --------------------------------------------------------------------------
-- 1. Marcar a conta como administradora
-- --------------------------------------------------------------------------
-- `raw_app_meta_data` (app_metadata) so pode ser escrito pelo backend/service
-- role. Vai assinado dentro do JWT, entao o navegador nao consegue forjar.

update auth.users
set raw_app_meta_data = coalesce(raw_app_meta_data, '{}'::jsonb) || '{"role":"admin"}'::jsonb
where email = 'admin@gmail.com';

-- Conferencia:
-- select email, raw_app_meta_data from auth.users where email = 'admin@gmail.com';


-- --------------------------------------------------------------------------
-- 2. Funcao auxiliar: a requisicao atual e de um admin?
-- --------------------------------------------------------------------------
create or replace function public.e_admin()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select coalesce(
    (auth.jwt() -> 'app_metadata' ->> 'role') = 'admin',
    false
  );
$$;


-- --------------------------------------------------------------------------
-- 3. Row Level Security na tabela `usuarios`
-- --------------------------------------------------------------------------
-- Sem isto, a chave anon publica le a tabela inteira. Com isto:
--   - cada pessoa le e edita apenas a propria linha;
--   - o admin le e edita todas.

alter table public.usuarios enable row level security;

drop policy if exists "usuarios: leitura propria" on public.usuarios;
create policy "usuarios: leitura propria"
  on public.usuarios for select
  using (auth.jwt() ->> 'email' = email);

drop policy if exists "usuarios: insercao propria" on public.usuarios;
create policy "usuarios: insercao propria"
  on public.usuarios for insert
  with check (auth.jwt() ->> 'email' = email);

drop policy if exists "usuarios: atualizacao propria" on public.usuarios;
create policy "usuarios: atualizacao propria"
  on public.usuarios for update
  using (auth.jwt() ->> 'email' = email)
  with check (auth.jwt() ->> 'email' = email);

drop policy if exists "usuarios: admin le tudo" on public.usuarios;
create policy "usuarios: admin le tudo"
  on public.usuarios for select
  using (public.e_admin());

drop policy if exists "usuarios: admin escreve tudo" on public.usuarios;
create policy "usuarios: admin escreve tudo"
  on public.usuarios for all
  using (public.e_admin())
  with check (public.e_admin());


-- --------------------------------------------------------------------------
-- 4. Aplicar o mesmo padrao nas demais tabelas
-- --------------------------------------------------------------------------
-- Toda tabela exposta pela chave anon precisa de RLS. Sem policy, a tabela
-- fica inacessivel (falha fechada) — que e o comportamento seguro.
--
--   alter table public.<tabela> enable row level security;
--
-- Para conferir o que ainda esta aberto:
--
--   select tablename, rowsecurity
--   from pg_tables
--   where schemaname = 'public'
--   order by rowsecurity, tablename;
