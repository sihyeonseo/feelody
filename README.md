# Feelody | 오늘의 일기, 세 곡의 플레이리스트

한국어 일기와 감정이 닮은 K-pop 세 곡을 가사에서 찾는다. 현재 경로는 **원문 가사 → E5-large 검색 30곡 → KURE-nano 재순위화 → 3곡**이다. 같은 가사 그룹은 검색 후보에서 한 번만 센다.

**[Vercel 배포 및 새 일기 입력 안내](docs/vercel.md)** · `web/`에는 모델 서버 없이 볼 수 있는 실험 예시 10편이 있다. 첫 화면은 로그인 없는 마음 달력이다. 날짜별 일기·기분·세 곡을 브라우저에 저장한다. 모델 서버가 없으면 일기만 저장한다. API 연결 후에는 원문 일기로 계산한 세 곡을 표시한다. 기존 비교 화면은 “추천 실험실”에 있다. 아래 B1/B3 서비스는 초기 한 곡 추천 버전이다.

**포트폴리오 설계:** [시스템 구조·API·운영 계획](docs/system-design.md) · [토스 요구 역량·평가 설계·확인된 결과](docs/evaluation-and-portfolio.md). 현재 구현과 앞으로 검증할 범위를 구분했다.

## 최근 10편에서 확인한 점

사람이 감정 적합도를 0~3점으로 매겼다. 2점 이상인 추천은 검색만 썼을 때 4/30자리, KURE 적용 후 10/30자리였다. 같은 열 편을 비교한 파일럿이며 일반화 성능 추정치는 아니다. [공개 집계](reports/top3_pilot.json) · [주제별 추천과 사람 평가](web/cases.json)

- 추임새 반복 축약은 고유 가사 2,242개 중 90개를 바꿨지만, 같은 후보 30개를 고정하면 열 편 모두 최종 3곡과 순서가 그대로였다. 현재는 원문 사용.
- 검색 쏠림 보정 후 열 편의 300개 후보 자리에서 고유 가사 수가 117→200으로 늘었다. 기존 사람 채점으로 확인되는 적합 후보는 20→19개였다. 품질 개선이 확인되지 않아 기본 추천에는 적용하지 않았다.
- 039번은 검색 19위와 22위에 사람이 적합하다고 본 곡이 있었는데 KURE의 최종 세 곡은 모두 0점이었다. 검색과 재순위화의 실패를 구분한 사례다.

**연구 코드**: `live_top3.py`는 현재 30→3 서비스, `feelody_top3.py`와 `feelody_rerank_preview.py`는 이전 50곡 BGE 실험, `research/adlib_ablation.py`는 고정 후보에서 추임새 축약 전후를 비교하는 코드다. 공개 저장소에는 원문 데이터나 모델 인덱스가 포함되지 않는다.

## 초기 B1/B3 실험 결과

| 질문 | 평가 | 결과 |
|---|---|---|
| 실제 1위 곡의 감정이 일기와 어울리는가? | 고전 일기 파일럿 10편. 모델을 가리고 가사를 읽어 0~3점 평가, 2점 이상을 적합으로 집계 | 직접 검색(B1) 3/10, 감정 앵커(B3) 4/10 |
| 사람이 골라 둔 참고곡이 후보에 있는가? | 현대 일기 개발셋 114편. 일기당 참고곡 1곡이 상위 50개 가사 그룹에 포함된 횟수 | B1 16/114, B3 13/114 |
| 내 PC에서 얼마나 걸리는가? | Windows CPU, B3 서비스 새 프로세스 1회, 같은 입력으로 HTTP 요청 2회 | 준비 후 첫 요청 31.43ms, 두 번째 요청 21.57ms. 프로세스 시작부터 첫 결과까지 약 10.50초 |

첫 두 행은 다른 데이터와 다른 질문이다. 참고곡을 놓쳐도 좋은 곡을 추천할 수 있다. 파일럿 10편만으로 어느 모델의 추천 품질이 더 좋다고 결론내리지 않았다. [실험 기록·한계](docs/experiments.md)와 [측정 결과](reports/) 참고.

## 추천 방식과 서비스

1. **인덱스 생성:** 카탈로그에서 공백 정규화 후 동일한 가사는 한 번만 계산하고 원래 곡 ID를 모두 연결한다. 긴 가사는 384개 내용 토큰 단위로 나누고 조각 벡터를 토큰 수로 가중 평균한 뒤 정규화한다.
2. **B1 직접 검색:** E5-small로 일기와 가사를 각각 인코딩하고 코사인 유사도가 가장 높은 곡을 찾는다.
3. **B3 감정 비교:** 일기와 각 가사를 14개의 감정 설명 문장과 비교한다. 예를 들어 ‘안도’가 그 글의 다른 감정보다 얼마나 강한지 상대값을 구하고, 두 글의 감정 패턴을 비교한다. 학습된 감정 분류 확률은 아니다.
4. **서비스:** 브라우저가 FastAPI에 일기를 보내면 메모리에 올려 둔 로컬 인덱스로 검색하고 곡명·가수·곡 ID를 반환한다. 모델은 시작할 때 한 번 로드한다. DB와 배포 서버는 쓰지 않는다.

## 실행하기 (저장소 루트에서)

**① 데이터나 모델 없이 API 동작만 확인**
    
    python -m pip install -r requirements-test.txt
    python -m feelody_local.check_api

가짜 추천기를 연결해 화면 파일, 정상 요청, 동점, 빈 입력과 오류 응답을 검사한다. 이 검사는 모델을 다운로드하지 않는다.

**② 내 PC에서 추천 서비스 실행** — 기존 연구 환경은 Windows, Anaconda, Python 3.13.9, CPU였다. 새 환경이라면:

    conda create -n feelody python=3.13.9 -y
    conda activate feelody
    python -m pip install -r requirements.txt

기존 인덱스가 있다면 로컬에서만 이 저장소의 `artifacts/b1_e5_v01/`로 복사한다. 없다면 `song_id,title,artist,lyrics_text` 네 열을 포함하는 본인 카탈로그를 `data/songs_catalog_v01.csv`에 두고 다음 명령을 한 번 실행한다. 모델 다운로드에는 인터넷이 필요하다. 기존 인덱스는 덮어쓰지 않는다.

    python feelody_e5.py build --revision 614241f622f53c4eeff9890bdc4f31cfecc418b3

이제 서버를 열고 브라우저에서 **http://127.0.0.1:8765** 에 접속한다.

    python -m feelody_local

기본 모드는 B3다. B1로 보려면 `python -m feelody_local --model b1`로 실행한다. 종료는 Ctrl+C. [서비스·벤치마크·Docker 사용법](feelody_local/README.md)

**③ 실제 카탈로그 없이 검색 과정만 체험** — ②의 패키지 설치 후 아래 두 명령을 실행한다. 동봉된 세 행은 직접 만든 설명 문장과 가상 곡 ID다. 이 데모로 연구 결과나 실제 곡 추천 품질을 재현할 수는 없다.

    python feelody_e5.py build --catalog examples/catalog_demo.csv --index artifacts/demo --revision 614241f622f53c4eeff9890bdc4f31cfecc418b3
    python feelody_e5.py recommend --index artifacts/demo --text "마음이 놓이고 편안하다."

## 어디를 보면 되나

| 경로 | 내용 |
|---|---|
| [feelody_local/](feelody_local/) | 로컬 웹 화면, API, 추천기 연결, 벤치마크, API 검사 |
| [feelody_e5.py](feelody_e5.py) · [feelody_b3.py](feelody_b3.py) | 가사 인덱스와 B1·B3 점수 계산 |
| [feelody_blind_pilot.py](feelody_blind_pilot.py) · [feelody_rank_choice.py](feelody_rank_choice.py) | 실제 1위 추천 블라인드 채점, 두 모델 1위 후보의 순위 결합 |
| [feelody_compare.py](feelody_compare.py) | 초기 B1과 한국어 BGE(B2) 비교 실험 |
| [feelody_modern_baseline.py](feelody_modern_baseline.py) · [feelody_modern_large.py](feelody_modern_large.py) | 같은 현대 일기 개발셋에서 참고곡 순위 비교 |
| [examples/](examples/) · [reports/](reports/) | 공개 데모 입력과 원문을 제외한 기존 측정 기록 |

실제 가사·일기 원문, 모델 가중치, 평가자가 보는 가사 HTML과 생성 인덱스는 포함하지 않는다. 공개 파일만으로는 집계 검산과 데모·API 검사가 가능하고, 원 실험 재실행에는 같은 비공개 입력이 필요하다.
