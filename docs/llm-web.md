# Vercel에서 LLM API만으로 Feelody 시범 운영하기

웹 기본 경로는 **일기 → Vercel Function → 외부 LLM → 요약·공감·추천 3곡과 이유**다. 기존 E5/KURE 모델과 30→3 실험 코드는 보존하지만 이 경로에서는 실행하지 않는다. GPU, 비공개 실행 ZIP, 가사 인덱스, 켜 둔 개인 PC가 필요 없다.

## 설정: 코드를 입력하는 곳이 아니라 환경변수 칸

Vercel → Feelody 프로젝트 → Settings → Environment Variables에서 아래 값을 추가한다. Production에 적용한다. Preview에서도 사용할 때만 Preview를 함께 선택한다. 키를 이 문서, GitHub, 채팅, web/ 파일에 넣지 않는다.

### OpenAI 키인 경우

| Name | Value |
|---|---|
| OPENAI_API_KEY | 발급받은 실제 API 키 |
| FEELODY_LLM_PROVIDER | openai (기본값, 생략 가능) |
| FEELODY_LLM_MODEL | gpt-4.1-mini (기본값, 생략 가능) |

따라서 OpenAI 키라면 **OPENAI_API_KEY 한 개만 등록해도** 기본 모델을 요청하도록 구성돼 있다. 해당 계정에서 모델 사용과 API 이용이 가능해야 한다. 다른 모델을 지정하려면 Chat Completions와 JSON 객체 출력을 지원하는 모델을 쓴다.

### Google AI Studio의 Gemini 키인 경우

| Name | Value |
|---|---|
| GEMINI_API_KEY | 발급받은 실제 API 키 |
| FEELODY_LLM_PROVIDER | gemini |
| FEELODY_LLM_MODEL | 본인 계정에서 사용 가능한 Gemini 모델 ID |

Gemini 모델 ID는 생략하지 않는다. 제공사의 모델 폐기·전환에 따라 오래된 이름을 기본값으로 넣지 않았다. 두 제공사 키가 모두 있으면 FEELODY_LLM_PROVIDER를 명시한다. 다른 제공사 키는 이 두 변수에 넣어도 동작하지 않는다.

설정 저장 후 **Deployments → 최신 배포 → Redeploy**. 웹 브라우저를 새로고침하고 날짜 선택 → 일기 입력 → 기분 선택 → ‘저장하고 AI 추천받기’를 누른다. 사용 전에 화면 안내에서 일기를 외부 제공사로 보낸다는 점을 확인할 수 있다. 첫 검수는 개인 정보 없는 짧은 일기로 한다.

기존 FEELODY_API_ORIGIN은 기본 LLM 모드에서 사용하지 않는다. FEELODY_WEB_MODE를 설정해 둔 경우 삭제하거나 llm으로 변경한다. 기존 연구 모델 웹으로 돌아가려면 local로 설정하고 이전 모델 API 주소를 지정해 재배포한다. 모델 API나 MCP 코드에는 변경이 없다.

## Vercel 빌드 설정과 결과

- Root Directory: 저장소 루트. Framework Preset: Other. Build: node web/build.mjs. Output: dist. 저장소 vercel.json에 설정했다.
- api/recommend.mjs는 Node.js 서버 함수이며 .vercelignore에서 별도로 포함한다. 기존 Python 모델 코드는 배포 대상에 포함하지 않는다.
- GET /api/recommend는 configured와 제공사 이름만 반환한다. 키나 실제 외부 호출은 없다. POST만 일기 한 편을 한 번 전송한다.
- 답변: 일기 요약, 공감 문장, 서로 다른 세 곡(title/artist/reason)과 youtube_url. 요약·공감·이유를 화면과 날짜별 브라우저 기록에 보관한다.
- 노래 링크는 **YouTube 검색 URL**이다. 실제 영상의 존재나 공식 영상 여부를 확인한 직접 재생 링크가 아니다. 외부 LLM이 제시한 URL을 사용하지 않는다.
- 곡명·가수·설명은 LLM이 가진 지식에 근거하므로 틀릴 수 있다. 현재는 가사 검색이나 카탈로그 대조를 수행하지 않는다. 기존 사람 평가 수치는 이 웹 경로의 품질 수치가 아니다.
- 설정 누락, 제공사 한도, 실패·시간 초과는 화면에 표시하고 일기는 남긴다. 임의 선곡을 새 AI 결과로 대신 생성하지 않는다. 새 추천을 시작하면 그 날짜의 이전 추천 카드·설명을 지우고 새 응답만 표시한다. 실패하면 곡을 임의로 대체하지 않는다. 일기 원문과 다른 날짜의 기록은 보존한다.

## 키·요금·데이터

키는 Vercel 함수에서만 읽고 빌드 산출물과 브라우저로 보내지 않는다. 일기와 선택 기분을 선택된 제공사로 보내며, 함수는 원문·키·제공사 오류 본문을 직접 로깅하지 않는다. OpenAI 요청은 store:false를 사용하지만 이 설정이 제공사의 모든 보존 정책을 없애는 것은 아니다. 일기 원문과 결과는 사용자의 브라우저 저장소에 남는다.

한 번 누를 때 최대 한 번 호출하며 자동 재시도는 없다. 4,000자 입력, 2,500 출력 토큰 상한, 45초 제공사 대기 제한을 적용했다. 동일 함수 인스턴스에서 같은 IP당 1분 5회, 동시 호출 3회를 제한한다. 이 제한은 재시작·다중 인스턴스를 통합하지 않으므로 월 결제 차단선이나 인증이 아니다. API 사용량은 제공사 요금/한도에 따르며 무료를 보장하지 않는다. 중단하려면 FEELODY_LLM_ENABLED=0으로 바꿔 재배포한다. 공개 규모를 키우기 전에는 제공사 사용량 한도 및 영속적인 요청 제한을 추가한다.

## 확인 방법과 이번 검증 범위

로컬에서 Node.js 22 이상으로 실행:

    node --test tests/llm-api.test.mjs
    node tests/web-llm.cjs
    node web/build.mjs

위 검사는 외부 호출을 가짜 응답으로 대체한다. OpenAI/Gemini 요청 형식, 설정 누락, 잘못된 응답, 곡 중복, 제공사 오류, 한도/시간 초과, 노출 데이터, 화면 저장·복원·원문 편집을 검사한다. 실제 API 키를 이용한 유료 호출과 Vercel 원격 배포 검수는 별도다. 새 배포 후 /api/recommend의 configured:true를 확인한 다음 일기 한 편으로 실제 결과와 제공사 사용량을 확인한다. 사용자 계정의 키·모델 권한은 자동으로 검증한 것으로 주장하지 않는다.

공식 자료: [Vercel Node.js Functions](https://vercel.com/docs/functions/runtimes/node-js), [환경변수](https://vercel.com/docs/environment-variables), [OpenAI JSON 출력](https://developers.openai.com/api/docs/guides/structured-outputs), [Gemini OpenAI 호환 API](https://ai.google.dev/gemini-api/docs/openai).


## 기다리는 화면과 속도 확인

추천 대기 중에는 실제 경과 초와 움직이는 음반 아이콘을 표시한다. 이 브라우저에서 같은 제공사·모델·추론 설정으로 최근 24시간 안에 성공한 요청이 있으면 최근 최대 5회의 실제 소요 범위도 표시한다. 첫 요청에는 임의 예상 시간을 만들지 않는다. 이 범위는 성공한 이전 요청의 관측값이며, 실패·시간 초과는 포함하지 않으므로 완료 보장이나 통계적 예측 구간이 아니다. 모델/추론 설정 변경 시 다른 기록을 섞지 않는다. 완료·실패·편집·화면 이동 시 타이머를 정리한다.

API 성공 응답의 timing.provider_ms는 외부 제공사 호출부터 응답 해석까지, timing.server_ms는 핸들러 실행부터 결과까지의 시간이다. 브라우저는 별도로 제출→결과 확인 시간을 측정한다. 서버 시간이 짧고 브라우저 시간이 길면 네트워크·콜드 스타트 등 추가 구간을 살펴야 한다. provider_ms가 길어도 추론 자체와 제공사 대기를 분리해서 측정한 것은 아니다.

Gemini에서 속도와 품질을 비교하려면 **FEELODY_LLM_REASONING_EFFORT=medium**을 추가하고 재배포할 수 있다. low/medium/high/xhigh 중 해당 모델이 지원하는 값을 사용한다. 생략하면 모델 기본 설정을 유지한다. 현재 코드는 이 값을 Gemini 요청에만 보낸다. Gemini 4 Hydrogen 기본 추론 수준은 high이며 공식 문서는 medium/low를 더 빠른 응답이 필요한 경우의 선택지로 설명한다. Feelody에서 속도 개선이나 품질 유지가 검증된 것은 아니므로 같은 일기들로 시간을 측정하고 추천 결과도 비교한다. [Google 추론 수준 안내](https://aistudio.google.com/docs/thinking#understanding-thinking-levels) · [OpenAI 호환 API 매핑](https://aistudio.google.com/docs/openai#thinking).

## 동일한 세 곡이 보일 때 (2026-11-19 진단)

공개 배포의 config와 API 상태가 LLM 모드, Gemini Hydrogen, low임을 확인했다. 개인정보 없는 두 일기로 실제 호출했을 때 한 건은 HTTP 502로 실패했고, 다른 건은 LLM이 요약·공감·서로 다른 세 곡과 이유를 반환했다. 성공 건의 provider_ms는 23,284ms였다. 이 두 건만으로 사용자가 보고한 서로 다른 일기의 반복 추천 원인은 확정할 수 없다.

같은 원문 재요청에서 과거 성공 카드를 유지하던 동작은 제거했다. 요청마다 서버 request_id와 generated_at을 새로 부여하고, 화면에는 성공한 응답의 생성 시각을 표시한다. 입력 변경 후 다른 결과가 도착하면 세 곡·이유·링크를 모두 새 응답으로 교체한다. 설정을 읽지 못했을 때 LLM 화면이 조용히 로컬 선곡으로 전환되지 않으며 config/app.js를 재검증한다. 제공사 오류는 안전한 provider_status와 code로 구별한다. 원문·키·제공사 오류 전문은 반환하지 않는다.

‘다른 세 곡 추천받기’를 누르면 현재 세 곡의 곡명·가수를 excluded_songs로 보내고 LLM에게 그 세 곡을 제외하도록 요청한다. 결과가 여전히 동일 곡(곡명+가수 정규화 기준)을 포함하면 오류로 처리하며 자동 재호출하지 않는다. 일반 추천은 이전 일기의 곡을 강제로 제외하지 않는다. 같은 감정에 같은 곡이 나오는 것 자체를 버그라고 단정하지 않는다.

YouTube 링크는 이번 LLM이 반환한 곡명·가수에 맞춰 서버가 만든 검색 주소다. 브라우저도 해당 검색어와 주소 형식을 검증한다. 직접 재생 가능한 공식 영상 URL 검증 기능은 아니다.
