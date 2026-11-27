create or replace function feelody_private.withdraw_self()
returns void language plpgsql security definer set search_path = '' as $$
declare
  member_id uuid := auth.uid();
begin
  if member_id is null then raise insufficient_privilege; end if;

  -- Serialize the rare closure operation with profile role and status changes.
  lock table public.profiles in share row exclusive mode;
  if exists (select 1 from public.profiles where id = member_id and role = 'Admin' and deleted_at is null)
     and not exists (select 1 from public.profiles where id <> member_id and role = 'Admin' and deleted_at is null) then
    raise exception using errcode = 'PT409', message = 'last_admin';
  end if;
  update public.profiles set deleted_at = now() where id = member_id and deleted_at is null;
end $$;
