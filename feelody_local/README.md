# Feelody · 로컬 서비스 0.2
## 1. 처음 실행 (Windows · 기존 Anaconda 환경)
저장소 루트 README의 설치 및 인덱스 준비 단계를 먼저 완료하세요. 아래 명령은 저장소 루트에서 실행합니다.
기존 8765번 서버가 실행 중이면 그 실행 창에서 Ctrl+C로 종료하거나 새 서비스에 --port 8767을 지정합니다.

    python -m pip install -r feelody_local/requirements.txt
    python -m feelody_local

터미널에 Application startup complete가 보이면 http://127.0.0.1:8765 를 엽니다. 일기를 입력하고 추천 버튼을 누른 뒤 곡명·아티스트와 멜론 링크를 확인합니다. 링크를 누를 때만 멜론 페이지로 이동합니다. 추천 요청에는 일기만 들어가고 링크에는 곡 ID만 들어갑니다. 종료는 Ctrl+C입니다. 설치할 때는 인터넷이 필요하지만 추론에는 로컬 모델 폴더를 사용합니다.
서버를 종료하면 서비스도 종료됩니다. 다른 사람에게 제공되는 주소는 없습니다.

## 2. 구성과 API
브라우저 → POST /api/recommend → FastAPI 입력 검증 → engine.build가 만든 recommend 함수 → 응답 → 브라우저.
시작 시 모델과 곡 인덱스를 한 번 읽고, B3의 곡별 감정 프로필도 한 번만 계산합니다. 한 프로세스 안에서 추론은 한 번에 하나씩 실행합니다. 모델 학습, 회원 계정, 원문 보관, 외부 작업 큐는 없습니다.
- web/: 입력, 로딩, 오류, 동점 결과, 멜론 링크
- api.py: GET /health, POST /api/recommend, 정적 파일 제공. 추천 오류 시 본문이나 예외 내용을 응답·로그에 남기지 않습니다.
- engine.py: 기존 E5 인덱스와 B1/B3 연결. B1로 실행: python -m feelody_local --model b1
- GET /openapi.json: 기계 판독용 API 명세
- 요청 예: {"diary":"친구 얼굴을 보니 마음이 놓였다."}
- 정상 응답 형식: {"songs":[{"song_id":"...","title":"...","artist":"..."}]}
- 1~4000자 범위의 비어 있지 않은 문자열을 받습니다. 입력 오류 422, 추천 처리 실패 500입니다. 코사인 값을 확률로 표시하지 않습니다.

## 3. 실제 성능 측정 (내 PC)
    python -m feelody_local.bench

새 프로세스와 별도 로컬 포트로 같은 예시 일기를 두 번 보내고 측정용 서버를 종료합니다. 결과는 프로젝트 폴더의 feelody_bench_날짜_시간.json입니다.
start_to_first_result_ms는 서버 실행부터 첫 곡 수신까지, first_request_ms와 second_request_ms는 각각 준비된 서버에 보낸 첫 번째·두 번째 HTTP 요청 시간입니다. sampled_peak_process_rss_mib는 50ms 간격으로 관측한 서버 프로세스의 최대 RSS라서 순간 최대치와 다를 수 있습니다. 이 결과는 네트워크 배포 성능이나 동시 사용자 처리량이 아닙니다. 비교 측정 시 같은 PC, 같은 모델, 같은 입력을 쓰고 다른 서비스는 종료하세요. 패키지 버전 보존: python -m pip freeze > feelody_local_env.txt

## 4. 선택: 내 PC에서만 Docker로 실행
Docker Desktop에서 Linux 컨테이너를 사용할 수 있을 때:
    docker compose -f feelody_local/compose.yaml up --build
브라우저에서 http://127.0.0.1:8766 을 엽니다. 중지 후 정리:
    docker compose -f feelody_local/compose.yaml down

이 구성은 모델 파일을 이미지에 중복 저장하지 않고 기존 파이썬 파일 두 개와 인덱스 폴더를 읽기 전용으로 연결합니다. 첫 빌드는 CPU용 PyTorch 등 패키지를 내려받습니다. 모델·인덱스 원본 또는 경로가 다르면 시작이 실패합니다. B1 코드 해시는 인덱스와 일치해야 하며, 검사 우회 대신 해당 인덱스를 만들 때 쓴 원본을 사용합니다. 현재 공개 배포용 이미지가 아닙니다.
로컬 Docker 자원 보기: docker stats (중지는 Ctrl+C). 위 Python 벤치마크는 네이티브 프로세스 측정이며 Docker 수치와 섞지 마세요.

## 5. 모델 없이 API 확인 (선택)
    python -m pip install "httpx>=0.27,<0.29"
    python -m feelody_local.check_api

가짜 추천 함수로 화면 파일, 정상 요청, 동점곡, 잘못된 입력, 모델 오류 경로를 검사합니다. 실제 추천 품질을 측정하지 않습니다. 실제 모델 테스트는 1번, 실제 성능 측정은 3번입니다.
