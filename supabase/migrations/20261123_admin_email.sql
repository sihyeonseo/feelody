-- Apply after 20261122_admin_console.sql. Requires Supabase Vault and pg_net.
begin;
create extension if not exists pg_net;
create schema if not exists feelody_private;
revoke all on schema feelody_private from public,anon,authenticated;
create table feelody_private.admin_mail (
 user_id uuid primary key references public.profiles(id) on delete cascade,
 email text not null check(email=lower(trim(email)) and length(email) between 3 and 254),
 session_id uuid, digest bytea, expires_at timestamptz, valid_until timestamptz,
 sent_at timestamptz, window_start timestamptz, sent_count integer not null default 0
);
revoke all on feelody_private.admin_mail from public,anon,authenticated;
alter table feelody_private.admin_mail enable row level security;
-- Changing a mailbox or removing an Admin role invalidates any outstanding grant.
create function feelody_private.reset_mail() returns trigger language plpgsql security definer set search_path='' as $$
begin
 if tg_table_schema='public' then
   delete from feelody_private.admin_mail where user_id=old.id;
 else
   new.session_id=null; new.digest=null; new.valid_until=null; new.expires_at=null;
 end if;
 return new;
end $$;
create trigger reset_admin_mail after update of role on public.profiles for each row
 when(old.role is distinct from new.role) execute function feelody_private.reset_mail();
create trigger reset_mail_destination before update of email on feelody_private.admin_mail for each row
 when(old.email is distinct from new.email) execute function feelody_private.reset_mail();

create function public.feelody_admin_verified() returns boolean language sql stable security definer set search_path='' as $$
 select exists(select 1 from feelody_private.admin_mail m join public.profiles p on p.id=m.user_id
 join auth.sessions s on s.id=m.session_id and s.user_id=m.user_id
 where p.role='Admin' and p.id=auth.uid() and m.session_id=(auth.jwt()->>'session_id')::uuid
 and m.valid_until>now() and (s.not_after is null or s.not_after>now()));
$$;
-- Existing member RPC and pricing RLS both use this predicate.
create or replace function public.feelody_is_admin() returns boolean language sql stable security invoker set search_path='' as $$
 select public.feelody_admin_verified();
$$;

create function public.feelody_admin_send_mail(address text) returns void language plpgsql security definer set search_path='' as $$
declare m feelody_private.admin_mail%rowtype; sid uuid:=(auth.jwt()->>'session_id')::uuid;
 token text; api_key text; sender text; ts timestamptz:=clock_timestamp();
begin
 if not exists(select 1 from public.profiles p join auth.sessions s on s.user_id=p.id where p.id=auth.uid() and p.role='Admin' and s.id=sid and (s.not_after is null or s.not_after>ts)) then
 raise exception 'Denied' using errcode='42501'; end if;
 select * into m from feelody_private.admin_mail where user_id=auth.uid() for update;
 if not found or lower(trim(address)) is distinct from m.email then return; end if;
 if m.sent_at>ts-interval '60 seconds' or (m.window_start>ts-interval '1 hour' and m.sent_count>=5) then return; end if;
 select decrypted_secret into api_key from vault.decrypted_secrets where name='feelody_resend_key';
 select decrypted_secret into sender from vault.decrypted_secrets where name='feelody_admin_sender';
 if coalesce(api_key,'')='' or coalesce(sender,'')='' then raise exception 'Mail configuration unavailable'; end if;
 token:=replace(gen_random_uuid()::text,'-','')||replace(gen_random_uuid()::text,'-','');
 update feelody_private.admin_mail set session_id=sid,digest=sha256(convert_to(token,'UTF8')),expires_at=ts+interval '10 minutes',valid_until=null,
 sent_at=ts,window_start=case when window_start>ts-interval '1 hour' then window_start else ts end,
 sent_count=case when window_start>ts-interval '1 hour' then sent_count+1 else 1 end where user_id=m.user_id;
 perform net.http_post(url:='https://api.resend.com/emails',
 headers:=jsonb_build_object('Authorization','Bearer '||api_key,'Content-Type','application/json'),
 body:=jsonb_build_object('from',sender,'to',jsonb_build_array(m.email),'subject','Feelody 관리자 접속 확인',
 'text','로그인을 시작한 브라우저에서 10분 안에 다음 링크를 여세요. 본인이 요청하지 않았다면 무시하세요.'||chr(10)||'https://feelody.shop/admin/confirm#'||token));
end $$;
create function public.feelody_admin_confirm_mail(token text) returns boolean language plpgsql security definer set search_path='' as $$
begin
 if token is null or token !~ '^[a-f0-9]{64}$' then return false; end if;
 update feelody_private.admin_mail m set digest=null,expires_at=null,valid_until=now()+interval '30 minutes'
 where m.user_id=auth.uid() and m.session_id=(auth.jwt()->>'session_id')::uuid and m.expires_at>clock_timestamp()
 and m.digest=sha256(convert_to(token,'UTF8')) and exists(select 1 from public.profiles p join auth.sessions s on s.user_id=p.id where p.id=m.user_id and p.role='Admin' and s.id=m.session_id and (s.not_after is null or s.not_after>now()));
 return found;
end $$;
revoke all on function feelody_private.reset_mail(),public.feelody_admin_verified(),public.feelody_admin_send_mail(text),public.feelody_admin_confirm_mail(text) from public,anon,authenticated;
grant execute on function public.feelody_admin_verified(),public.feelody_admin_send_mail(text),public.feelody_admin_confirm_mail(text) to authenticated;
-- Do not enqueue credentials on an installation exposing the backing queue or Vault to API roles.
do $$declare r text; begin foreach r in array array['anon','authenticated'] loop
 if (has_schema_privilege(r,'net','USAGE') and has_table_privilege(r,'net.http_request_queue','SELECT'))
 or (has_schema_privilege(r,'vault','USAGE') and has_table_privilege(r,'vault.decrypted_secrets','SELECT')) then
 raise exception 'Unsafe mail queue or Vault read grant for %',r; end if;
end loop; end $$;
commit;
