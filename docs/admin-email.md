# 관리자 이메일 확인 설정

운영 주소는 https://feelody.shop 이다. 기존 관리자 콘솔 SQL을 적용한 프로젝트에서 진행한다. 회원 사이트 로그인은 그대로다.

1. Resend에서 본인 도메인 발신자를 인증하고 메일 발송 전용 API 키를 만든다. 가능하면 해당 도메인으로 키를 제한하고 인증 메일의 클릭 추적은 끈다. 실제 비용/한도는 본인 Resend 계정에서 확인한다.
2. Supabase Vault에 두 시크릿을 만든다. `feelody_resend_key`: Resend 발송 키, `feelody_admin_sender`: 인증한 발신 이메일(예: admin@feelody.shop). 실제 키를 SQL 파일, Git 또는 채팅에 넣지 않는다.
3. SQL Editor에서 [이메일 인증 마이그레이션](../supabase/migrations/20261123_admin_email.sql)을 한 번 실행한다. 기존 콘솔 RPC와 pricing_plans RLS도 세션별 인증 조건을 사용하게 된다. 스크립트가 Vault나 pg_net 큐에 대한 잘못된 공개 권한을 발견하면 중단되므로 검사를 삭제하지 말고 권한을 확인한다.
4. 아래 SQL에서 UUID는 public.profiles의 본인 Admin 행 id, 이메일은 본인이 관리하는 수신함으로 바꿔 실행한다. 이메일은 웹에서 등록·변경할 수 없다. 구글 로그인 계정과 다른 보안이 유지되는 수신함을 권장한다.

```sql
insert into feelody_private.admin_mail(user_id,email)
select id, lower(trim('수신할 이메일')) from public.profiles
where id='관리자 UUID'::uuid and role='Admin'
on conflict (user_id) do update set email=excluded.email;
```

5. Cloudflare 배포 후 /admin/login에서 Google 로그인 → 등록한 이메일 입력 → 메일함의 링크를 같은 브라우저에서 연다. 비공개 창이나 다른 기기에서 시작했다면 메일 앱의 내장 브라우저 대신 로그인을 시작했던 창에 링크를 붙여 넣는다. 본인 외의 사람에게 링크를 전달하지 않는다.

링크는 10분간 유효하고 한 번만 사용할 수 있다. 새 링크 발급 시 기존 링크와 이전 승인은 무효다. 재발급은 60초 간격이고 시간당 최대 5회다. 확인 후 30분이 지나면 재인증한다. 역할 변경은 수신 주소 등록을 제거하고, 주소를 바꾸면 기존 승인이 취소된다. 운영자 잠금 시 프로젝트 소유자가 대시보드 SQL Editor에서 등록 정보를 수정한다. 메일 발송은 비동기다. 화면은 실제 수신을 보장하지 않는다. 메일이 오지 않으면 스팸함, Resend 전송 로그, 발신 도메인 및 Supabase pg_net 응답 상태를 확인한다.

운영 점검: 일반 회원 403, Admin의 인증 전 보호 페이지 리디렉션 및 변경 거부, 올바른 링크 확인 후 접근, 같은 링크 재사용 거부, 다른 로그인 세션에서 사용 거부를 확인한다. 만료 후 재인증도 확인한다. DB에 재사용 가능한 인증 토큰을 보관하지 않는다. 발송 과정의 Vault 및 pg_net 관리 권한은 운영자에게만 부여해야 한다.
