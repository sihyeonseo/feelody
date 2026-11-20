-- Run once after 20261120_account_journals.sql. Safe to re-run.
begin;
set local lock_timeout = '5s';
lock table auth.users in share row exclusive mode;
alter table public.profiles
  add column if not exists email text,
  add column if not exists full_name text,
  add column if not exists avatar_url text,
  add column if not exists created_at timestamptz,
  add column if not exists updated_at timestamptz;

-- Backfill without writing role. Preserve timestamps when re-run.
insert into public.profiles as p (id, email, full_name, avatar_url, created_at, updated_at)
select id, email,
  coalesce(nullif(raw_user_meta_data->>'full_name',''), nullif(raw_user_meta_data->>'name','')),
  coalesce(nullif(raw_user_meta_data->>'avatar_url',''), nullif(raw_user_meta_data->>'picture','')),
  coalesce(created_at, now()), now()
from auth.users
on conflict (id) do update set email=excluded.email, full_name=excluded.full_name,
  avatar_url=excluded.avatar_url, created_at=coalesce(p.created_at,excluded.created_at),
  updated_at=excluded.updated_at
where (p.email,p.full_name,p.avatar_url) is distinct from
      (excluded.email,excluded.full_name,excluded.avatar_url)
   or p.created_at is null or p.updated_at is null;

alter table public.profiles
  alter column created_at set default now(), alter column created_at set not null,
  alter column updated_at set default now(), alter column updated_at set not null;

create or replace function public.feelody_profile_timestamp() returns trigger
language plpgsql set search_path = '' as $$
begin
  new.created_at := old.created_at;
  if (new.email,new.full_name,new.avatar_url,new.role) is distinct from
     (old.email,old.full_name,old.avatar_url,old.role) then
    new.updated_at := now();
  else
    new.updated_at := old.updated_at;
  end if;
  return new;
end $$;
revoke all on function public.feelody_profile_timestamp() from public, anon, authenticated;
drop trigger if exists feelody_profile_timestamp on public.profiles;
create trigger feelody_profile_timestamp before update on public.profiles
  for each row execute function public.feelody_profile_timestamp();

create or replace function public.feelody_new_profile() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  insert into public.profiles as p (id,email,full_name,avatar_url,created_at)
  values (new.id,new.email,
    coalesce(nullif(new.raw_user_meta_data->>'full_name',''),nullif(new.raw_user_meta_data->>'name','')),
    coalesce(nullif(new.raw_user_meta_data->>'avatar_url',''),nullif(new.raw_user_meta_data->>'picture','')),
    coalesce(new.created_at,now()))
  on conflict (id) do update set email=excluded.email,full_name=excluded.full_name,avatar_url=excluded.avatar_url
  where (p.email,p.full_name,p.avatar_url) is distinct from (excluded.email,excluded.full_name,excluded.avatar_url);
  return new;
end $$;
revoke all on function public.feelody_new_profile() from public, anon, authenticated;
drop trigger if exists feelody_new_profile on auth.users;
create trigger feelody_new_profile after insert or update of email,raw_user_meta_data on auth.users
  for each row execute function public.feelody_new_profile();
commit;
