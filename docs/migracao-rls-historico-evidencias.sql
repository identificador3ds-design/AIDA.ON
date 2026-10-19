-- ==========================================================================
-- AIDA.ON — RLS do histórico e bucket `evidencias` privado   (P0 da auditoria)
-- ==========================================================================
--
-- PROBLEMA (verificado em produção em 08/10/2026, só com contagens e HEAD):
--   * `historico_analises` respondia à chave anon PÚBLICA (a que está no JS
--     do site): 168 linhas legíveis, de 11 usuários distintos, com `user_id` e
--     `imagem_original`;
--   * `imagem_original` é URL de bucket PÚBLICO: 8 de 8 URLs testadas
--     responderam 200 sem autenticação.
--   Ou seja: qualquer visitante podia listar e abrir as fotos enviadas pelos
--   usuários. O docs/lgpd-inventario.md já listava os dois itens como pendentes.
--
-- ORDEM DE IMPLANTAÇÃO (importa):
--   1. Publicar o site com o script-historico.js que usa URL ASSINADA
--      (branch auditoria/p0-seguranca). Ele funciona com o bucket público
--      ou privado, então pode ir antes.
--   2. Rodar ESTE script no SQL Editor do Supabase.
--   3. Conferir com as consultas do final.
--
-- REVERSÃO: o bloco "ROLLBACK" no fim desfaz tudo (volta ao estado inseguro).
-- Depende de public.e_admin() (docs/supabase-admin-setup.sql).
-- ==========================================================================

begin;

-- --------------------------------------------------------------------------
-- 1. historico_analises: cada usuário só enxerga e mexe nas próprias linhas
-- --------------------------------------------------------------------------
alter table public.historico_analises enable row level security;

-- Remove qualquer política permissiva antiga (ex.: "using (true)").
do $$
declare p record;
begin
  for p in select policyname from pg_policies
           where schemaname = 'public' and tablename = 'historico_analises'
  loop
    execute format('drop policy %I on public.historico_analises', p.policyname);
  end loop;
end $$;

create policy "historico: dono le"
  on public.historico_analises for select to authenticated
  using (user_id::text = auth.uid()::text);

create policy "historico: dono insere"
  on public.historico_analises for insert to authenticated
  with check (user_id::text = auth.uid()::text);

create policy "historico: dono apaga"
  on public.historico_analises for delete to authenticated
  using (user_id::text = auth.uid()::text);

-- O painel admin lê `metodo` e `data_analise` para as estatísticas.
create policy "historico: admin le"
  on public.historico_analises for select to authenticated
  using (public.e_admin());

-- Sem UPDATE para ninguém pelo front-end: o registro é imutável.
revoke all on public.historico_analises from anon;


-- --------------------------------------------------------------------------
-- 2. Bucket `evidencias`: privado, pasta = auth.uid()
-- --------------------------------------------------------------------------
-- O front-end grava em `<user.id>/<arquivo>` (script-analise.js).
update storage.buckets set public = false where id = 'evidencias';

drop policy if exists "evidencias: dono le"     on storage.objects;
drop policy if exists "evidencias: dono envia"  on storage.objects;
drop policy if exists "evidencias: dono apaga"  on storage.objects;

create policy "evidencias: dono le"
  on storage.objects for select to authenticated
  using (bucket_id = 'evidencias' and (storage.foldername(name))[1] = auth.uid()::text);

create policy "evidencias: dono envia"
  on storage.objects for insert to authenticated
  with check (bucket_id = 'evidencias' and (storage.foldername(name))[1] = auth.uid()::text);

create policy "evidencias: dono apaga"
  on storage.objects for delete to authenticated
  using (bucket_id = 'evidencias' and (storage.foldername(name))[1] = auth.uid()::text);

commit;


-- --------------------------------------------------------------------------
-- 3. Conferência (rodar depois; tudo deve bater)
-- --------------------------------------------------------------------------
-- select rowsecurity from pg_tables
--  where schemaname='public' and tablename='historico_analises';      -- true
-- select policyname, cmd, roles from pg_policies
--  where tablename='historico_analises';                              -- 4 políticas
-- select public from storage.buckets where id='evidencias';            -- false
--
-- De fora (PowerShell/bash), com a chave anon do site, deve vir "*/0":
--   curl -sI "https://<projeto>.supabase.co/rest/v1/historico_analises?select=*&limit=0" \
--     -H "apikey: <anon>" -H "Authorization: Bearer <anon>" -H "Prefer: count=exact"
-- O script ferramentas/verificar_exposicao_supabase.py faz essa checagem.


-- --------------------------------------------------------------------------
-- ROLLBACK (só em emergência: volta a expor os dados)
-- --------------------------------------------------------------------------
-- begin;
-- update storage.buckets set public = true where id = 'evidencias';
-- drop policy if exists "historico: dono le" on public.historico_analises;
-- drop policy if exists "historico: dono insere" on public.historico_analises;
-- drop policy if exists "historico: dono apaga" on public.historico_analises;
-- drop policy if exists "historico: admin le" on public.historico_analises;
-- alter table public.historico_analises disable row level security;
-- commit;
