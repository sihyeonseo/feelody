# Cloudflare Pages에서 Feelody 배포하기

GitHub 연동 Pages 프로젝트에서 저장소 루트, Production 브랜치 main, Framework None, 빌드 명령 `node web/build.mjs`, 출력 폴더 `dist`를 사용한다. Python 모델 설치는 필요 없다. 자동 의존성 설치 단계에서 연구용 패키지를 설치한다면 빌드 변수 SKIP_DEPENDENCY_INSTALL=1을 사용한다.

Workers & Pages → Feelody → Settings → Variables and Secrets에서 Production 환경에 등록한다.

| 유형 | 이름 | 값 |
|---|---|---|
| Secret (암호화) | GEMINI_API_KEY | 본인의 Google AI Studio 키 |
| Text | FEELODY_LLM_PROVIDER | gemini |
| Text | FEELODY_LLM_MODEL | gemini-3.5-flash-lite (계정에서 사용 가능한 모델) |

변수를 저장하고 최신 main 배포를 다시 실행한다. 키는 브라우저 코드, GitHub, 채팅에 넣지 않는다. 기본 웹 모드는 llm이므로 FEELODY_WEB_MODE와 FEELODY_API_ORIGIN은 설정할 필요가 없다. 선택적으로 OpenAI를 쓰면 OPENAI_API_KEY 및 provider=openai를 사용한다.

- 사이트 루트 404: Production 배포 성공 여부 및 dist/index.html 출력을 확인한다.
- GET /api/recommend: JSON의 configured가 true이면 필수 설정이 읽혔다. 키 유효성은 검사하지 않는다. HTML 또는 404이면 Functions가 포함된 최신 커밋으로 배포됐는지 확인한다.
- 일기와 기분을 입력하고 추천받기를 눌러 서로 다른 세 곡과 추천 이유를 확인한다. POST만 외부 모델을 호출한다. 502는 모델 이름·키 권한, 429는 요청 제한·제공사 한도를 확인한다. YouTube 링크는 검색 주소다.
- /api/*만 Pages Functions로 전달한다. 인스턴스별 요청 제한은 전체 비용 상한이 아니다. LLM 제공사의 과금은 별도다. FEELODY_LLM_ENABLED=0을 설정하고 재배포하면 추천 호출을 중단한다.
- 로컬 계약 테스트: Node 22.12 이상에서 node --test tests/llm-api.test.mjs. 모의 제공사를 사용한다. Pages 환경에서 로컬 확인: node web/build.mjs 이후 npx wrangler pages dev dist. 로컬 비밀값은 Git에서 제외된 .dev.vars를 사용한다.
