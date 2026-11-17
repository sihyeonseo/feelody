# Vercel에서 체험하기

1. Vercel → Add New → Project에서 GitHub의 `sihyeonseo/feelody`를 Import한다.
2. Root Directory는 저장소 루트(`./`), Framework Preset은 **Other**로 유지하고 Deploy한다. 저장소의 `vercel.json`이 빌드 명령 `node web/build.mjs`와 출력 폴더 `dist`를 지정한다. 예시 모드에는 키나 서버가 필요 없다.
3. 달력에서 날짜를 누르고 일기와 기분을 저장한다. 감정 표현이 있으면 간단한 단어 규칙으로 기분을 제안하며 직접 바꿀 수 있다. 정적 배포만 하면 일기만 저장한다. 새 추천은 연결된 모델의 응답으로만 표시한다. 카드를 누르면 YouTube 검색으로 이동한다. 기록은 해당 주소의 브라우저 저장소에만 남고 다른 기기와 동기화되지 않는다. 브라우저 데이터를 삭제하면 기록도 삭제된다.
4. 우측 상단 ‘추천 실험실’에서 일기의 주제를 선택하고 ‘검색만’과 ‘재순위화’를 바꾸면 동일 일기의 실제 추천과 0~3점 사람 평가를 비교할 수 있다. 주제는 익명화한 설명이며 평가에 쓴 원문 입력과 다르다.

## 내 일기로 실행하는 법

실시간 추천기는 E5-large로 원문 가사 30개 그룹을 검색하고 KURE-Reranker-nano로 3개를 고른다. 추론을 원하는 기계에서 다음을 준비한다.

- 개인 카탈로그와 짝이 맞는 `artifacts/b1_e5_v01/groups.json` 및 `artifacts/modern_large_dev01/{manifest.json,groups_*.npy}`. 기존 실험 파일을 그대로 사용한다. E5 revision 및 가사 그룹 파일 체크섬이 다르면 시작하지 않는다. 기존 데이터가 없다면 앞선 로컬 실험의 입력과 인덱스가 필요하다.
- 아래 명령은 저장소 루트에서 실행한다. 첫 실행에는 고정 revision의 모델 다운로드가 필요하다. GPU가 없으면 CPU를 쓴다. 로컬 UI와 API는 같은 주소에서 열린다.

    python -m pip install -r requirements.txt
    python -m uvicorn live_top3:app --host 127.0.0.1 --port 8765

브라우저에서 http://127.0.0.1:8765 로 접속해 달력에서 날짜를 선택한다. API 계약은 `POST /recommend`, 요청 `{"diary":"…"}`, 응답 `{"songs":[{"title":"…","artist":"…","searchRank":14}, ...]}`이다. 파일이나 DB에 일기를 저장하지 않는다.

Vercel 화면에서도 실시간으로 사용하려면 다른 호스트에 이 API를 HTTPS로 제공해야 한다. 모델 서버의 `FEELODY_WEB_ORIGINS`에는 허용할 Vercel 웹 origin(쉼표로 구분), Vercel의 `FEELODY_API_ORIGIN`에는 모델 서버의 HTTPS origin(마지막 슬래시 없이)을 넣고 다시 배포한다. 이 URL은 공개 설정이며 키를 넣지 않는다. 로컬 주소는 공용 모델 서버 주소로 쓸 수 없다. CORS는 인증이 아니므로 외부 공개 운영 시에는 모델 호스트에서 요청 제한을 설정한다.

정적 빌드만 로컬에서 확인하려면 `node web/build.mjs` → `python -m http.server 8000 -d dist` → http://localhost:8000 순서로 진행한다.

### 내 PC를 끈 상태로 모델 쓰기 (선택: Modal GPU)

비공개 실행 묶음 안에는 두 인덱스와 코드가 함께 들어 있다. 폴더 전체를 GitHub에 올리지 않는다. PowerShell에서 압축을 푼 폴더로 이동한 후:

    python -m pip install "modal>=1.1,<2"
    python -m modal setup
    $env:FEELODY_WEB_ORIGINS = "https://내-Feelody-서비스주소"
    python -m modal deploy deploy/host_model.py

배포 명령은 모델 파일을 준비하고 비공개 인덱스를 자신의 Modal 워크스페이스로 보낸다. 출력된 HTTPS 주소를 열면 같은 달력에서 실제 모델을 바로 쓸 수 있다. 기존 Vercel 달력을 사용하려면 프로젝트 Settings → Environment Variables에서 Production의 `FEELODY_API_ORIGIN`에 출력된 HTTPS origin(마지막 / 없이)을 입력하고 **Redeploy**한다. 두 주소를 서로 바꿔 넣지 않는다. `/healthz`에서 ready와 두 모델 ID를 확인할 수 있다. 엔드포인트는 URL을 아는 사람이 호출할 수 있으며 GPU 사용 비용이 발생할 수 있다. 공개 테스트 전에 계정 예산을 설정하고, 테스트 종료 후 `python -m modal app stop feelody-top3`로 중단할 수 있다.
