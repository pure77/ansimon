# 안심온 - LLM·RAG 파트 (담당: 강권영)

기획안 역할 분담표 기준 담당 범위: **문서 수집·청킹, 검색, 프롬프트, 출력 스키마, 근거 검증**

이 폴더는 그 5가지를 각각 모듈로 구현하고, `pipeline.py`에서 하나의 엔드투엔드 흐름으로
연결한 실행 가능한 참조 구현이다. 소스 문서는 질병관리청 「대상자별 온열질환 예방 매뉴얼」
(2025.07)과 동일한 구조(대분류/대상자별 소제목/공통수칙/응급조치/쉼터 안내)로 구성한
참고용 샘플 PDF를 사용한다.

> **주의**: 이 환경에서는 `kdca.go.kr` 원문 다운로드가 네트워크 egress 정책으로 차단되어
> 실제 파일을 받아올 수 없었다. 그래서 `data/heat_illness_manual.pdf`는 원문을 그대로
> 긁어온 사본이 아니라, 같은 목차/대상자 구성(노인·임신부·장애인·심뇌혈관질환자·신장질환자·
> 혈압질환자·당뇨질환자·실외근로자·어린이·응급조치)으로 직접 작성한 대체 문서다.
> 팀원이 실제 원문 PDF를 받으면 같은 경로에 덮어쓰고 `python3 ingest.py`만 다시 돌리면 된다
> (ingest.py는 표지의 "발행기관/발행일/적용대상/원문 URL" 라벨과 "■ N. 제목" /
> "▶ 대상자: 이름" / "• 목록" / "N) 번호목록" 구조 규칙만 지키면 어떤 문서든 파싱한다).

```
anshimon-rag/
├── data/
│   └── heat_illness_manual.pdf     # 참고용 샘플 문서 (실제 KDCA 원문 아님, 위 주의사항 참고)
├── fixtures/
│   └── sample_seoul_shelters.csv   # 서울시 쉼터류 원천 데이터 샘플(실데이터 아님, 구조 예시)
├── ingest.py                       # 1) 문서 수집·청킹
├── retrieval.py                    # 2) 검색
├── prompt_builder.py                # 3) 프롬프트
├── schemas.py                       # 4) 출력 스키마 (기획안 6.1~6.3 계약)
├── evidence_verifier.py             # 5) 근거 검증 (+쉼터 실존 검증)
├── shelter_reference.py             # 서울시 쉼터류 원천 데이터 로더/조회 인덱스
├── llm_client.py                    # 실제 API 호출 + 오프라인 mock 폴백
├── pipeline.py                      # 엔드투엔드 진입점 (Spring이 호출할 함수)
├── server.py                        # Spring 연동용 FastAPI 서버 (HTTP로 붙을 때)
└── out/
    ├── documents.json               # 문서 메타데이터
    └── chunks.jsonl                 # 청크 60건
```

## 실행 순서

**중요: 아래 모든 `.py` 파일과 `data/`, `fixtures/`, `out/` 폴더가 반드시 같은 폴더 안에
그대로 있어야 합니다.** 파일들을 서로 다른 위치에 흩어서 다운로드하면
`ModuleNotFoundError: No module named 'prompt_builder'` 같은 에러가 납니다.

### macOS / Linux

```bash
cd anshimon-rag
pip install -r requirements.txt

python3 ingest.py       # PDF -> chunks.jsonl (문서 수집·청킹)
python3 retrieval.py    # 검색 단독 테스트
python3 prompt_builder.py  # 프롬프트 페이로드 확인
python3 evidence_verifier.py  # 근거 검증 로직 단독 테스트
python3 shelter_reference.py  # 쉼터 실존 검증 인덱스 단독 테스트
python3 llm_client.py   # 생성 단계 단독 테스트 (mock)
python3 pipeline.py     # 전체 파이프라인 (Spring 연동 시 이 함수 형태로 호출)
```

### Windows (VS Code / PowerShell)

```powershell
cd anshimon-rag
pip install -r requirements.txt

python ingest.py
python retrieval.py
python prompt_builder.py
python evidence_verifier.py
python shelter_reference.py
python llm_client.py
python pipeline.py
```

`python`이 안 먹으면 `py` 로 대체하세요 (`py ingest.py` 등).
반드시 VS Code 터미널의 현재 경로가 `anshimon-rag` 폴더 안인지(`cd anshimon-rag` 실행 여부)
프롬프트에 표시된 경로로 먼저 확인하세요.

`ALAN_API_KEY`(+ `ALAN_API_URL`) 환경변수가 있으면 `llm_client.py`가 실제 Alan API를
호출하고, 없으면 검색된 근거 청크에서 문장을 그대로 채택하는 결정론적 mock 생성기로
자동 폴백한다. 따라서 API 키 없이도 검색→프롬프트→생성→검증 전체 흐름을 데모/테스트할 수 있다.

> **주의**: `llm_client._call_real_api()`는 Alan API의 정확한 엔드포인트/요청·응답
> 필드명을 확인하지 못한 상태에서 일반적인 REST LLM API 관례로 작성한 최선의 추정
> 구현이다. 실제 Alan API 문서(ESTsoft가 해커톤 참가팀에 배포한 문서)를 받으면
> `llm_client.py` 상단 TODO 주석에 표시된 4곳(엔드포인트/인증헤더/요청body/응답파싱)을
> 맞춰 수정해야 한다.

## 1. 문서 수집·청킹 (`ingest.py`)

- 기획안 4.2 원칙 그대로 구현:
  - 문서 메타데이터(제목/기관/발행일/원문 URL/적용대상) 필수 저장
  - 표·목록(•, -, 번호)은 문단과 분리해 **의미 단위**로 청크 생성
  - 각 청크는 상위 제목 경로(`heading_path`)를 함께 저장
  - `active` 플래그로 비활성화(삭제 대신 이력 보존) 지원 — 같은 문서를 재적재하면
    이전 버전 문서/청크는 삭제되지 않고 `active=False`로 남고, 새 버전이 `active=True`로 추가된다
- 대상자별 자동 태깅(`target_audience`): 노인, 임신부, 장애인, 심뇌혈관질환자,
  신장질환자, 혈압질환자, 당뇨질환자, 실외근로자, 어린이, 응급조치 등.
  "▶ 대상자: X" 소제목 아래 청크는 구조적으로, 그 외 청크는 본문 키워드로 태깅된다.
- 결과: 문서 1건 → **청크 60건** (`out/chunks.jsonl`)

## 2. 검색 (`retrieval.py`)

- TF-IDF(char n-gram) + 코사인 유사도. 한국어 형태소 분석기 없이도 동작하도록
  문자 단위 n-gram을 사용해 오프라인/제약 환경에서도 안정적으로 실행됨.
- 대상자 태그로 1차 필터링(해당 대상자 + GENERAL + EMERGENCY) 후 질의 유사도로
  재정렬 → 노인 프로필이면 "노인" 관련 청크가 우선 검색됨.
- 인터페이스가 검색 로직과 분리돼 있어, 운영 단계에서 문장 임베딩 + 벡터DB로
  교체해도 `pipeline.py`는 수정할 필요 없음.

## 3. 프롬프트 (`prompt_builder.py`)

- Spring이 넘기는 구조화 컨텍스트(프로필/위험도/기상/쉼터)와 RAG 근거 청크를
  분리된 블록으로 직렬화
- 시스템 프롬프트에 강제 규칙 명시:
  1. 근거 청크 밖 사실 생성 금지 (hallucination 차단)
  2. 문장마다 `evidenceChunkIds` 첨부 의무화
  3. 응급 증상 문구는 승인된 고정 템플릿 그대로 사용
  4. 출력은 JSON 하나만 (자유 텍스트 금지)
- `build_messages()`가 system/messages 페이로드 형태로 바로 반환 (`llm_client.py`가 Alan API 호출에 그대로 사용)

## 4. 출력 스키마 (`schemas.py`)

- 기획안 6.1(ML 응답)/6.2(안내 계획)/6.3(통화 결과) 계약을 **pydantic**으로 강제
- `InterventionPlan.to_contract_json()`이 기획안 6.2 예시와 동일한 필드명(camelCase)으로 직렬화
- enum(RiskLevel, TriState, ContactStatus 등)으로 잘못된 값 자체를 코드 레벨에서 차단
- Spring이 최종 검증하기 전, LLM/RAG 계층에서 1차 스키마 방어선 역할

## 5. 근거 검증 (`evidence_verifier.py`)

LLM(또는 mock) 출력이 저장되기 전 아래 4가지를 검사한다.

| 항목 | 실패 시 |
|---|---|
| 안내 문장에 `evidenceChunkIds`가 비어있음 | ERROR |
| 이번 검색에 없던 chunk_id를 인용(조작/환각) | ERROR |
| 응급 증상 문구가 고정 템플릿과 다름 | ERROR |
| 문장 속 숫자가 구조화 컨텍스트와 직접 매칭 안 됨 | WARNING (Spring 재대조 권고) |

ERROR가 하나라도 있으면 `pipeline.py`가 `GuidanceGenerationError`를 던져
**자동전화 발신을 보류**시킨다 (기획안 완료기준의 "누락된 핵심 데이터가 있으면
자동전화가 보류된다" 원칙을 근거 오류 상황까지 확장 적용).

### 5-1. 쉼터 실존 검증 (`shelter_reference.py`) — 서울 열린데이터광장 연동

기존 근거 검증이 "쉼터 정보의 숫자가 컨텍스트와 일치하는가"만 봤다면, 이번에 추가된
`shelter_reference.py`는 **"그 쉼터가 실제로 존재하는 시설인가"** 를 서울시 공식 데이터로
교차 검증한다.

- 대상 데이터셋 (서울 열린데이터광장, 공공누리 1유형)
  - [서울시 스마트쉼터 현황](https://data.seoul.go.kr/dataList/OA-22311/F/1/datasetView.do) (시군구/시설명/설치장소/상세주소/설치년도)
  - [서울시 그늘막 현황](https://data.seoul.go.kr/dataList/OA-22309/F/1/datasetView.do)
  - [서울시 쿨링포그(물안개분사장치) 현황](https://data.seoul.go.kr/dataList/OA-22310/F/1/datasetView.do)
  - (팀 기존 확보) 무더위쉼터 공공데이터 (OA-21065)
- `ShelterReferenceIndex.load_from_xlsx()` / `.load_from_csv()` 로 원본 파일을 적재하고,
  `find_by_name_or_address()` / `exists()` 로 느슨한 문자열 매칭 조회를 한다.
- **주의**: data.seoul.go.kr의 다운로드 버튼은 자바스크립트 트리거라 자동 수집이 불가능하다.
  팀원이 직접 다운로드한 `.xlsx`를 `data/서울시_스마트쉼터_현황.xlsx` (그늘막/쿨링포그/무더위쉼터도
  동일 명명 규칙, `shelter_reference.DEFAULT_XLSX_SOURCES` 참고)로 저장하면 `load_default_index()`가
  자동으로 로드한다. 파일이 없으면 `fixtures/sample_seoul_shelters.csv`(예시 구조, **실제 데이터
  아님**)로 폴백해 파이프라인이 계속 테스트 가능하도록 했다.
- `evidence_verifier.verify_guidance_output()`에 `shelter_ref` 인자로 주입하면, 안내 계획에
  포함된 쉼터가 원천 데이터에 없을 경우 **ERROR**를 발생시켜 `pipeline.py`가 자동전화를
  보류하도록 이미 연결해 두었다 (`pipeline.py` 실행 시 케이스 2 예시 참고).

### 5-2. TMAP 도보 경로 연동 (`t-map_location_connection_ansimon` / `recommend.py`) — shelter 모듈 출력 소비

`shelter` 모듈(별도 저장소, `recommend.py`)이 어르신 좌표 기준으로 TMAP 보행자 경로까지
계산해 `walk_minutes`/`crossings`/`route`/`needs_review`가 포함된 쉼터 후보를 넘겨준다.
이 계층은 그 계약을 아래처럼 그대로 이어받는다.

- `schemas.ShelterRecommendation`에 `lat`/`lon`/`walk_minutes`/`walk_meters`/`crossings`/
  `open_status`/`needs_review`/`route`/`alternatives` 필드를 추가했다 (`AlternativeShelter`
  서브모델 포함). `recommend.py` 원본은 snake_case, Spring 계약은 camelCase라
  `llm_client.py`/`pipeline.py` 양쪽 다 두 케이싱을 모두 읽는다.
- **`needs_review: true`는 evidence_verifier가 ERROR로 승격**시켜 `pipeline.py`가 자동전화를
  보류한다 — recommend.py 쪽 실패 처리 원칙(ANSIMON_WORKFLOW §11: "TMAP 실패/도보 20분
  초과는 직선거리로 대체하지 않고 사람에게 넘긴다")을 이 계층에서도 그대로 존중하는 것이다
  (`pipeline.py` 실행 시 케이스 4 예시 참고).
- `route`(예: `["80m 이동", "횡단보도 건너기", "도착"]`)는 전화 안내 문구로, `crossings`는
  사회복지사가 "혼자 이동 가능한가"를 판단하는 근거로, `alternatives`는 어르신이 다른 곳을
  원할 때 바로 답할 수 있는 대안으로 그대로 `InterventionPlan.recommendedShelter`에 실려
  contact 모듈까지 전달된다 (`pipeline.py` 케이스 3 예시 참고).

## Spring 연동 지점

```python
from pipeline import generate_intervention_plan

plan_json = generate_intervention_plan(
    elderly_id=101,
    risk_snapshot_id=812,
    elderly_profile={...},   # elderly 모듈에서 조회
    risk_snapshot={...},     # risk 모듈(Python ML 결과)에서 조회
    shelter={...},           # shelter 모듈(TMAP 검증 완료 후보)에서 조회
    weather={...},           # weather 모듈에서 조회
)
# plan_json 은 기획안 6.2 "최종 안내 계획" 스키마와 동일
# -> guidance 모듈이 그대로 저장/버전관리, contact 모듈이 전화 대본으로 사용
```

Spring이 Python을 직접 임베딩하지 않고 **HTTP로** 붙는 경우엔 아래 `server.py`를 쓴다.

## Spring 연동 서버 (`server.py`)

`generate_intervention_plan()`을 FastAPI로 감싼 것. Spring 백엔드가 내부망에서
HTTP로 호출하는 구조를 쓸 때 사용한다.

```bash
uvicorn server:app --host 0.0.0.0 --port 8000
```

- `GET /health` — 헬스체크
- `POST /v1/intervention-plans` — body에 `elderlyId`/`riskSnapshotId`/`elderlyProfile`/
  `riskSnapshot`/`shelter`/`weather`를 실어 보내면(camelCase, `generate_intervention_plan()`
  파라미터와 1:1 대응) 아래처럼 응답한다.
  - **200**: 기획안 6.2 "최종 안내 계획" JSON 그대로 반환
  - **422**: 근거 검증 ERROR로 자동전화가 보류돼야 한다는 뜻. body에
    `{"error": "GUIDANCE_GENERATION_BLOCKED", "message": "...", "issues": [...]}`가 담겨
    있으니 Spring은 이 상태 코드를 받으면 자동전화를 걸지 않고 issues를 로그/알림으로 노출해야 한다.
  - **503**: `out/chunks.jsonl`이 없는 등 RAG 저장소가 아직 준비 안 된 상태 (먼저 `python3 ingest.py` 필요)

요청 예시:
```bash
curl -X POST http://localhost:8000/v1/intervention-plans \
  -H "Content-Type: application/json" \
  -d '{
    "elderlyId": 101,
    "riskSnapshotId": 812,
    "elderlyProfile": {"targetAudience": ["ELDERLY"], "age": 82, "livesAlone": true},
    "riskSnapshot": {"riskLevel": "HIGH", "riskScore": 0.83, "riskFactors": ["독거", "고령"]},
    "shelter": {"name": "...", "address": "...", "walkMinutes": 3, "needsReview": false},
    "weather": {"temperatureC": 36.2, "heatWarning": "폭염경보"}
  }'
```

FastAPI가 자동으로 만들어주는 API 문서는 `http://localhost:8000/docs`에서 확인 가능하다.

## 다음 단계 (해커톤 중 확장 포인트)

- 검색을 TF-IDF → 문장 임베딩(예: 로컬 sentence-transformers 또는 API 임베딩)으로 교체
- 실제 Alan API 문서를 받으면 `llm_client._call_real_api()`의 TODO 4곳(엔드포인트/인증헤더/
  요청body/응답파싱)만 맞춰 고치면 됨 — `ALAN_API_KEY`/`ALAN_API_URL`은 이미 연결돼 있음
- 팀원이 질병관리청 원문 PDF와 서울시 스마트쉼터/그늘막/쿨링포그 xlsx를 실제로 받아 `data/`에
  넣으면 `ingest.py`/`shelter_reference.py`가 샘플 데이터 대신 실데이터로 자동 전환됨
- 통화 결과(`CallOutcome`) 파싱용 별도 프롬프트/검증 모듈 추가 (6.3 계약 대응, 현재는 스키마만 정의됨)
