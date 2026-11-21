alter table public.profiles add column deleted_at timestamptz;
create policy active_profile on public.profiles as restrictive for select to public using (deleted_at is null);
create policy active_diary_owner on public.diary_entries as restrictive for all to authenticated
using (exists(select 1 from public.profiles where id=(select auth.uid()) and deleted_at is null))
with check (exists(select 1 from public.profiles where id=(select auth.uid()) and deleted_at is null));
-- Preserve an existing email-verification requirement on installations that use one.
do $migration$ begin
 if to_regprocedure('public.feelody_admin_verified()') is null then
 execute $ddl$create or replace function public.feelody_is_admin() returns boolean language sql stable security invoker set search_path='' as $ select exists(select 1 from public.profiles where id=auth.uid() and role='Admin' and deleted_at is null) $ $ddl$;
 else
 execute $ddl$create or replace function public.feelody_is_admin() returns boolean language sql stable security invoker set search_path='' as $ select public.feelody_admin_verified() and exists(select 1 from public.profiles where id=auth.uid() and role='Admin' and deleted_at is null) $ $ddl$;
 end if;
end $migration$;
create or replace function public.feelody_admin_members(page_no integer default 1) returns jsonb
 language plpgsql stable security definer set search_path='' as $$
begin
 if auth.uid() is null or not public.feelody_is_admin() then
  raise exception 'Administrator required' using errcode='42501';
 end if;
 if page_no is null or page_no not between 1 and 100000 then
  raise exception 'Invalid page' using errcode='22023';
 end if;
 return jsonb_build_object('total',(select count(*) from public.profiles where deleted_at is null),
 'admins',(select count(*) from public.profiles where deleted_at is null and role='Admin'),
 'members',coalesce((select jsonb_agg(to_jsonb(m) order by m.created_at desc,m.id) from
 (select id,email,full_name,role,created_at from public.profiles where deleted_at is null order by created_at desc,id limit 25 offset ((page_no-1)*25)) m),'[]'::jsonb));
end $$;

create schema if not exists feelody_private;
create function feelody_private.withdraw_self() returns void language plpgsql security definer set search_path='' as $$
begin
 if auth.uid() is null then raise insufficient_privilege; end if;
 update public.profiles set deleted_at=now() where id=auth.uid() and deleted_at is null;
end $$;
revoke all on function feelody_private.withdraw_self() from public,anon,authenticated;
grant usage on schema feelody_private to authenticated;
grant execute on function feelody_private.withdraw_self() to authenticated;
create function public.feelody_withdraw() returns void language sql security invoker set search_path='' as $$select feelody_private.withdraw_self()$$;
revoke all on function public.feelody_withdraw() from public,anon,authenticated;
grant execute on function public.feelody_withdraw() to authenticated;