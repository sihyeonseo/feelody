# Vercel에서 체험하기

1. Vercel → Add New → Project에서 GitHub의 `sihyeonseo/feelody`를 Import한다.
2. Root Directory는 저장소 루트(`./`), Framework Preset은 **Other**로 유지하고 Deploy한다. 저장소의 `vercel.json`이 빌드 명령 `node web/build.mjs`와 출력 폴더 `dist`를 지정한다. 예시 모드에는 키나 서버가 필요 없다.
3. 일기의 주제를 선택하고 ‘검색만’과 ‘재순위화’를 바꾸면 동일 일기의 실제 추천과 0~3점 사람 평가를 비교할 수 있다. 주제는 익명화한 설명이며 평가에 쓴 원문 입력과 다르다.

## 내 일기로 실행하는 법

실시간 추천기는 E5-large로 원문 가사 30개 그룹을 검색하고 KURE-Reranker-nano로 3개를 고른다. 추론을 원하는 기계에서 다음을 준비한다.

- 개인 카탈로그와 짝이 맞는 `artifacts/b1_e5_v01/groups.json` 및 `artifacts/modern_large_dev01/{manifest.json,groups_*.npy}`. 기존 실험 파일을 그대로 사용한다. E5 revision 및 가사 그룹 파일 체크섬이 다르면 시작하지 않는다. 기존 데이터가 없다면 앞선 로컬 실험의 입력과 인덱스가 필요하다.
- 아래 명령은 저장소 루트에서 실행한다. 첫 실행에는 고정 revision의 모델 다운로드가 필요하다. GPU가 없으면 CPU를 쓴다. 로컬 UI와 API는 같은 주소에서 열린다.

    python -m pip install -r requirements.txt
    python -m uvicorn live_top3:app --host 127.0.0.1 --port 8765

브라우저에서 http://127.0.0.1:8765 로 접속해 '내 일기'를 선택한다. API 계약은 `POST /recommend`, 요청 `{"diary":"…"}`, 응답 `{"songs":[{"title":"…","artist":"…","searchRank":14}, ...]}`이다. 파일이나 DB에 일기를 저장하지 않는다.

Vercel 화면에서도 실시간으로 사용하려면 다른 호스트에 이 API를 HTTPS로 제공해야 한다. 모델 서버의 `FEELODY_WEB_ORIGINS`에는 허용할 Vercel 웹 origin(쉼표로 구분), Vercel의 `FEELODY_API_ORIGIN`에는 모델 서버의 HTTPS origin(마지막 슬래시 없이)을 넣고 다시 배포한다. 이 URL은 공개 설정이며 키를 넣지 않는다. 로컬 주소는 공용 모델 서버 주소로 쓸 수 없다. CORS는 인증이 아니므로 외부 공개 운영 시에는 모델 호스트에서 요청 제한을 설정한다.

정적 빌드만 로컬에서 확인하려면 `node web/build.mjs` → `python -m http.server 8000 -d dist` → http://localhost:8000 순서로 진행한다.
