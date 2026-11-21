create extension if not exists pg_cron;
alter table public.profiles add column activity_opt_in_at timestamptz;
create table feelody_private.member_activity(
 member_id uuid not null references public.profiles(id) on delete cascade,
 event text not null check(event in ('login','logout','visit')),
 screen text not null check((event='visit' and screen in ('calendar','entry','research','study')) or (event<>'visit' and screen='')),
 occurred_at timestamptz not null default clock_timestamp()
);
alter table feelody_private.member_activity enable row level security;
revoke all on feelody_private.member_activity from public,anon,authenticated;
create index on feelody_private.member_activity(occurred_at);
create index on feelody_private.member_activity(member_id);
create function feelody_private.activity(action text, screen text) returns void language plpgsql security definer set search_path='' as $$
declare uid uuid:=auth.uid(); consent timestamptz; shared text;
begin
 if uid is null then raise insufficient_privilege; end if;
 select activity_opt_in_at into consent from public.profiles where id=uid and deleted_at is null for update;
 if not found then return; end if;
 if action='disable' then
  update public.profiles set activity_opt_in_at=null where id=uid;
  delete from feelody_private.member_activity where member_id=uid; return;
 end if;
 select decrypted_secret into shared from vault.decrypted_secrets where name='feelody_activity_writer';
 if length(coalesce(shared,''))<32 or shared is distinct from (current_setting('request.headers',true)::jsonb->>'x-feelody-writer') then raise insufficient_privilege; end if;
 if action='enable' then update public.profiles set activity_opt_in_at=coalesce(activity_opt_in_at,now()) where id=uid;return;end if;
 if consent is not null then insert into feelody_private.member_activity(member_id,event,screen) values(uid,action,screen);end if;
end $$;
create function public.feelody_activity(action text,screen text default '') returns void language sql security invoker set search_path='' as $$select feelody_private.activity(action,screen)$$;
revoke all on function feelody_private.activity(text,text), public.feelody_activity(text,text) from public,anon,authenticated;
grant execute on function feelody_private.activity(text,text), public.feelody_activity(text,text) to authenticated;
create function feelody_private.clear_closed_activity() returns trigger language plpgsql security definer set search_path='' as $$
begin new.activity_opt_in_at=null;delete from feelody_private.member_activity where member_id=new.id;return new;end $$;
revoke all on function feelody_private.clear_closed_activity() from public,anon,authenticated;
create trigger clear_closed_activity before update of deleted_at on public.profiles for each row when (new.deleted_at is not null) execute function feelody_private.clear_closed_activity();
select cron.schedule('feelody_expire_member_activity','7 * * * *',$job$delete from feelody_private.member_activity where occurred_at + interval '3 months' <= now()$job$);