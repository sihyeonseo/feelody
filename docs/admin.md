# Feelody administration
관리자 접근에는 [이메일 인증 설정](admin-email.md)도 필요하다. Google 로그인과 역할 확인만으로는 관리 화면에 접근할 수 없다.

1. Apply the account and profile-details migrations first. Then run [the admin migration](../supabase/migrations/20261122_admin_console.sql) once in Supabase SQL Editor. This creates pricing_plans and two functions; do not grant profile UPDATE to site users. The migration expects pricing_plans not to exist. If you created that table separately, compare its columns and policies before running. No service_role key is required.
2. Assign an existing trusted account the Admin enum value in public.profiles in the Supabase dashboard. The website cannot grant roles.
3. Deploy Pages and open https://feelody.shop/admin/login. Use Google with the same callback settings as normal sign-in. /admin, /admin/members, and /admin/plans have no public site navigation or analytics scripts.
4. Acceptance: guest redirected to admin login; User receives 403; email-verified Admin can create an inactive test plan, change the price, and reload to verify persistence. Remove the Admin role in Supabase and confirm the next request is denied. Test read isolation with separate accounts. Ordinary users cannot query the admin-members RPC or read/modify plans. Admins get limited member details, not private diaries. No payments or refunds are processed.
