-- Execute uma vez no SQL Editor do Supabase.
-- A funcao usa somente o usuario autenticado e nao aceita IDs enviados pelo navegador.
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

  select email into usuario_email
  from auth.users
  where id = usuario_id;

  if lower(usuario_email) = 'admin@gmail.com' then
    raise exception 'A conta administrativa nao pode ser excluida por este fluxo';
  end if;

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
