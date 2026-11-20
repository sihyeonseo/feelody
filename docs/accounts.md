# Feelody 계정 연결
설정 전에는 비회원 달력을 그대로 사용할 수 있다. 비회원 일기는 해당 사이트의 브라우저 저장소에만 남고, 로그인 중에는 일기와 추천 결과를 Supabase에 저장한다. 계정 메뉴의 가져오기는 이 기기의 비회원 기록을 복사하며, 같은 날짜의 계정 기록과 기기 원본은 보존한다.

1. 새 Supabase 프로젝트의 SQL Editor에서 supabase/migrations/20261120_account_journals.sql 을 한 번 실행한다. 기존 profiles 테이블이 있으면 먼저 구조를 비교한다. 새 회원 기본 역할은 User이며 운영자가 Table Editor에서 Admin, User 또는 SQL NULL로 변경할 수 있다. 역할은 클라이언트에서 변경할 수 없으며 Admin도 다른 사용자의 일기를 읽지 못한다. 비회원은 Supabase 계정을 생성하지 않는다.
2. Authentication → URL Configuration에서 Site URL을 https://feelody.shop 으로, Redirect URLs에는 https://feelody.shop/api/account/callback 를 등록한다. 로그인 테스트도 동일한 도메인에서 시작한다. Authentication → Providers에서 Google만 활성화한다. Google Cloud 콘솔의 redirect URI는 Supabase가 안내한 https://프로젝트주소/auth/v1/callback 이다. 이미 Kakao가 활성화되어 있다면 끈다. Google Client Secret은 Supabase의 Google provider 설정에 입력한다.
3. Cloudflare Pages의 Production Pages Functions 환경변수 SUPABASE_URL (Project URL), SUPABASE_PUBLISHABLE_KEY (sb_publishable_로 시작하는 공개 키)를 넣고 다시 배포한다. Functions는 사용자 세션으로 RLS를 적용하므로 secret/service_role 키를 넣지 않는다. 추천 API 키는 별도 서버 변수로 유지한다.
4. 서로 다른 브라우저에서 같은 계정으로 로그인해 한 날짜의 일기 작성·조회·삭제가 반영되는지 확인한다. 다른 계정에서는 그 날짜의 기록이 없어야 한다. 공용 기기에서는 사용 후 로그아웃한다.

로그인 시작 위치(경로, 쿼리, 해시 및 열린 일기의 날짜)를 같은 사이트의 콜백에서 복원한다. 다른 도메인으로 복귀하려면 별도로 등록하는 것이 아니라 처음부터 해당 도메인에서 로그인하고 그 도메인의 콜백도 Supabase에 허용해야 한다. 인증 코드는 서버에서 교환하고 토큰은 HttpOnly 쿠키에 보관한다. 이전 버전에서 로그인한 회원은 한 번 다시 로그인하면 기존 DB 기록을 볼 수 있다.

프로필 확장: 기존 테이블 설치 후 [20261121_profile_details.sql](../supabase/migrations/20261121_profile_details.sql)을 SQL Editor에서 실행한다. 기존 회원의 created_at은 Auth 가입 시각, updated_at은 최초 동기화 시각부터 기록한다. 관리자는 role을 그대로 관리하며, 이름·사진은 인증 메타데이터에 없으면 NULL이다.

관리자 콘솔 설정 및 운영 확인: [관리자 안내](admin.md).
