alter table public.profiles add column terms_accepted_at timestamptz, add column terms_version text, add column ai_opt_in_at timestamptz;
alter table public.profiles add constraint terms_record_pair check ((terms_accepted_at is null)=(terms_version is null));
create function feelody_private.save_choices(accept_required boolean,allow_ai boolean,allow_activity boolean) returns void language plpgsql security definer set search_path='' as $$
declare uid uuid:=auth.uid(); p public.profiles%rowtype;
begin
 if uid is null or allow_ai is null or allow_activity is null or accept_required is null then raise insufficient_privilege; end if;
 select * into strict p from public.profiles where id=uid and deleted_at is null for update;
 if p.terms_accepted_at is null and not accept_required then raise insufficient_privilege;end if;
 if allow_activity is distinct from (p.activity_opt_in_at is not null) then perform feelody_private.activity(case when allow_activity then 'enable' else 'disable' end,'');end if;
 update public.profiles set terms_accepted_at=coalesce(terms_accepted_at,now()),terms_version=coalesce(terms_version,'2026-11-21'),ai_opt_in_at=case when allow_ai then coalesce(ai_opt_in_at,now()) end where id=uid;
end $$;
create function public.feelody_save_choices(accept_required boolean,allow_ai boolean,allow_activity boolean) returns void language sql security invoker set search_path='' as $$select feelody_private.save_choices(accept_required,allow_ai,allow_activity)$$;
revoke all on function feelody_private.save_choices(boolean,boolean,boolean), public.feelody_save_choices(boolean,boolean,boolean) from public,anon,authenticated;
grant execute on function feelody_private.save_choices(boolean,boolean,boolean),public.feelody_save_choices(boolean,boolean,boolean) to authenticated;
create policy member_terms_required on public.diary_entries as restrictive for all to authenticated using(exists(select from public.profiles where id=(select auth.uid()) and terms_accepted_at is not null)) with check(exists(select from public.profiles where id=(select auth.uid()) and terms_accepted_at is not null));