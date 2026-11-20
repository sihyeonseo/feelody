-- Apply after 20261121_profile_details.sql, as project owner.
begin;
create function public.feelody_is_admin() returns boolean
 language sql stable security invoker set search_path='' as $$
 select exists(select 1 from public.profiles where id=(select auth.uid()) and role='Admin');
$$;
revoke all on function public.feelody_is_admin() from public,anon,authenticated;
grant execute on function public.feelody_is_admin() to authenticated;
-- Members can only read their own profile through the existing table policy.
-- Cross-member reporting is limited to this deliberately narrow projection.
create function public.feelody_admin_members(page_no integer default 1) returns jsonb
 language plpgsql stable security definer set search_path='' as $$
begin
 if auth.uid() is null or not public.feelody_is_admin() then
  raise exception 'Administrator required' using errcode='42501';
 end if;
 if page_no is null or page_no not between 1 and 100000 then
  raise exception 'Invalid page' using errcode='22023';
 end if;
 return jsonb_build_object('total',(select count(*) from public.profiles),
 'admins',(select count(*) from public.profiles where role='Admin'),
 'members',coalesce((select jsonb_agg(to_jsonb(m) order by m.created_at desc,m.id) from
 (select id,email,full_name,role,created_at from public.profiles order by created_at desc,id limit 25 offset ((page_no-1)*25)) m),'[]'::jsonb));
end $$;
revoke all on function public.feelody_admin_members(integer) from public,anon,authenticated;
grant execute on function public.feelody_admin_members(integer) to authenticated;

create table public.pricing_plans (
 id uuid primary key default gen_random_uuid(),
 name text not null unique check (char_length(trim(name)) between 1 and 80),
 monthly_usd_cents integer not null check(monthly_usd_cents between 0 and 99999999),
 active boolean not null default false
);
alter table public.pricing_plans enable row level security;
revoke all on public.pricing_plans from public,anon,authenticated;
grant select on public.pricing_plans to authenticated;
grant insert(name,monthly_usd_cents,active),update(name,monthly_usd_cents,active) on public.pricing_plans to authenticated;
create policy admins_manage_plans on public.pricing_plans for all to authenticated
 using ((select public.feelody_is_admin())) with check ((select public.feelody_is_admin()));
commit;
