# Feelody 계정 연결
설정 전에는 비회원 달력을 그대로 사용할 수 있다. 비회원 일기는 해당 사이트의 브라우저 저장소에만 남고, 로그인 중에는 일기와 추천 결과를 Supabase에 저장한다. 계정 메뉴의 가져오기는 이 기기의 비회원 기록을 복사하며, 같은 날짜의 계정 기록과 기기 원본은 보존한다.

1. 새 Supabase 프로젝트의 SQL Editor에서 supabase/migrations/20261120_account_journals.sql 을 한 번 실행한다. 기존 profiles 테이블이 있으면 먼저 구조를 비교한다. 새 회원 기본 역할은 User이며 운영자가 Table Editor에서 Admin, User 또는 SQL NULL로 변경할 수 있다. 역할은 클라이언트에서 변경할 수 없으며 Admin도 다른 사용자의 일기를 읽지 못한다. 비회원은 Supabase 계정을 생성하지 않는다.
2. Authentication → URL Configuration에서 Site URL을 https://feelody.shop 으로, Redirect URLs에는 https://feelody.shop/ 를 등록한다. 로그인 테스트도 동일한 도메인에서 시작한다. Authentication → Providers에서 Google과 Kakao만 활성화한다. 각 개발자 콘솔의 redirect URI는 Supabase가 안내한 https://프로젝트주소/auth/v1/callback 이다. Kakao Login을 활성화하고 이메일 동의 항목과 Supabase의 이메일 요구 설정을 일치시킨다. Client Secret은 각 Supabase provider 설정에만 입력한다.
3. Cloudflare Pages의 Production 빌드 환경변수 SUPABASE_URL (Project URL), SUPABASE_PUBLISHABLE_KEY (sb_publishable_로 시작하는 공개 키)를 넣고 다시 배포한다. 두 값은 웹에 공개되므로 secret/service_role 키를 넣지 않는다. 추천 API 키는 별도 서버 변수로 유지한다.
4. 서로 다른 브라우저에서 같은 계정으로 로그인해 한 날짜의 일기 작성·조회·삭제가 반영되는지 확인한다. 다른 계정에서는 그 날짜의 기록이 없어야 한다. 공용 기기에서는 사용 후 로그아웃한다.
