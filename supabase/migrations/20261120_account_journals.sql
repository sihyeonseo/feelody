begin;
create type public.feelody_role as enum ('Admin','User');
create table public.profiles (
 id uuid primary key references auth.users(id) on delete cascade,
 role public.feelody_role default 'User'
);
create function public.feelody_new_profile() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
 insert into public.profiles(id) values(new.id);
 return new;
end $$;
revoke all on function public.feelody_new_profile() from public, anon, authenticated;
create trigger feelody_new_profile after insert on auth.users for each row execute function public.feelody_new_profile();
insert into public.profiles(id) select id from auth.users on conflict do nothing;
create table public.diary_entries (
 user_id uuid not null references auth.users(id) on delete cascade,
 day date not null, entry jsonb not null check(jsonb_typeof(entry)='object' and entry ? 'text' and entry ? 'mood'), primary key(user_id,day)
);
alter table public.profiles enable row level security;
alter table public.diary_entries enable row level security;
revoke all on public.profiles, public.diary_entries from public, anon, authenticated;
grant select on public.profiles to authenticated;
grant select, insert, update, delete on public.diary_entries to authenticated;
create policy own_profile on public.profiles for select to authenticated using(id=(select auth.uid()));
create policy own_diary on public.diary_entries for all to authenticated using(user_id=(select auth.uid())) with check(user_id=(select auth.uid()));
commit;
