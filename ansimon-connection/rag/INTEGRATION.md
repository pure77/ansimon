# TMAP 쉼터 추천 × LLM/RAG 통합

`est-hackathon_tmap/shelter/recommend.py` 를 `anshimon-rag` 안으로 합쳐,
**위경도만 주면 쉼터 선정 → 도보경로 → 안내문 생성 → 근거검증까지 한 번에** 끝나게 했다.

```
위경도
  ↓  shelter_client.py    서울열린데이터광장 쉼터 목록 → 직선거리 상위 5곳 → TMAP 보행경로
쉼터 1곳 (도보 3분 / 횡단보도 1회 / 경로 문장 / 대안 4곳)
  ↓  prompt_builder.py    프로필·위험도·기상·쉼터 + RAG 근거청크를 블록으로 분리
  ↓  llm_client.py        Alan API (규격 자동탐색) → 실패 시 mock 폴백
안내 문장 + evidenceChunkIds
  ↓  evidence_verifier.py 근거 조작 / 응급문구 변형 / 쉼터 실존 / needs_review 검사
  ↓  schemas.py           InterventionPlan (camelCase)
백엔드 → 전화 발신
```

핵심 원칙은 그대로다. **LLM 은 숫자를 만들지 않는다.** `recommendedShelter` 는 LLM 응답을
버리고 TMAP 원본으로 덮어쓴다 (`llm_client.normalize_shelter`). LLM 은 그 사실을 문장으로
설명만 한다.

---

## 1. 설치와 실행

```bash
cd anshimon-rag
pip install -r requirements.txt

python ingest.py              # 최초 1회 (out/chunks.jsonl 생성)
python test_integration.py    # 통합 테스트 (외부 API 없이 24개 통과 + 2개 SKIP 이 정상)
python alan_check.py          # Alan API 가 붙는지 진단
uvicorn server:app --reload   # 백엔드 연결용 서버 → http://localhost:8000/docs
```

`.env` 에 추가할 항목은 `ENV_ADDITIONS.txt` 참고.

---

## 2. Alan API 확인 (`alan_check.py`)

기존 `llm_client._call_real_api()` 는 "Bearer 인증 + POST JSON" 한 가지를 찍어서 하드코딩해
둔 상태였다. 문서가 없는 상태에서 하나를 단정하면 틀렸을 때 원인이 안 보인다. 그래서
호출 규격을 **어댑터 3종**(`alan_client.ADAPTERS`)으로 분리하고, 진단 스크립트가 실제로
찔러본 뒤 되는 것을 고르게 했다.

| 규격 | 형태 |
| --- | --- |
| `alan_query` | `GET ?content=<질문>&client_id=<키>` — 앨런 공개/교육용 API |
| `openai` | `POST /chat/completions`, `Authorization: Bearer` — OpenAI 호환 게이트웨이 |
| `json_post` | `POST {system, messages}` — 기존 llm_client 가 쓰던 추정 규격 |

```bash
python alan_check.py                    # 전체 진단
python alan_check.py --url=https://.../question   # 주최측 문서의 엔드포인트 지정
python alan_check.py --json             # 백엔드 헬스체크용
```

출력 4단계:

1. 키를 읽었는가 (값은 가려서 표시)
2. 네트워크가 닿는가
3. **어떤 규격이 응답하는가** ← 통과한 이름을 `.env` 의 `ALAN_API_MODE` 에 넣으면 고정된다
4. 안심온이 쓰는 JSON 출력 지시를 따르는가 (설명문 섞임 / `evidenceChunkIds` 채움 여부)

4번이 특히 중요하다. 앨런은 검색형 모델이라 JSON 앞뒤에 설명을 붙이는 일이 잦은데,
`alan_client.extract_json()` 이 코드펜스와 앞뒤 설명을 걷어내고 중괄호 균형을 세어
객체만 잘라낸다. 그래도 `evidenceChunkIds` 를 안 채우면 근거검증에서 전부 막히므로,
그때는 프롬프트를 조이거나 `LLM_FALLBACK_TO_MOCK=1` 로 두고 시연한다.

전부 실패해도 파이프라인은 mock 생성기로 계속 돈다. **데모가 죽지는 않는다.**

---

## 3. 쉼터 모듈 (`shelter_client.py`)

원본 `recommend.py` 를 이식하면서 고친 것:

| # | 내용 |
| --- | --- |
| 1 | **문법오류 수정** — 원본 33행 `DEMO_LATLON = (37.5301 127.1236)` 쉼표 누락. 현재 원본은 import·실행 자체가 불가능하다 |
| 2 | `sys.exit()` → `ShelterLookupError` — 서버 안에서 프로세스가 죽으면 안 된다 |
| 3 | README·schemas 가 약속했는데 코드에 없던 `crossings` / `route` / `alternatives` 구현 |
| 4 | TMAP `searchOption=30`(최단거리+계단제외) 적용 — README 가 "고령자를 계단으로 보내지 않는 게 핵심"이라 써놓고 코드엔 없었다 |
| 5 | 운영시간 컬럼이 있으면 `open_status` 를 OPEN/CLOSED 로 계산 |
| 6 | 동기 진입점 `recommend_shelter()` — FastAPI/Spring 에서 바로 호출 |

정렬은 **도보시간 → 횡단보도 수** 순. 시간이 같으면 길을 덜 건너는 쪽이 고령자에게 안전하다.
직선거리는 후보를 5곳으로 줄이는 데만 쓴다.

실패 처리는 워크플로우 §11 그대로:

| 상황 | 동작 |
| --- | --- |
| TMAP 전부 실패 | **직선거리로 가장 가까운 쉼터를 추천하고 그 사실을 명시** (아래 3-1) |
| TMAP 일부 실패 | 그 쉼터만 후보에서 빼고 진행 |
| 도보 20분 초과 | 추천은 하되 `needs_review: true` → 4-1 정책에 따라 보류 또는 표시 |
| 쉼터 API 실패 | 안내 문장은 만들고 `warnings` 에 사유를 남긴다 (쉼터 하나 때문에 전화 전체를 막지 않는다) |

---

## 3-1. TMAP 실패 시 직선거리 폴백

지도 API 가 흔들린다고 어르신이 갈 곳을 하나도 못 듣는 건 서비스 목적에 어긋난다.
그래서 TMAP 이 전부 실패하면 **직선거리로 가장 가까운 쉼터를 추천한다.** 단, 그게
추정이라는 사실이 안내에서 절대 빠지지 않도록 3중으로 묶어놨다.

**1) 데이터에서 구분** — 추정치를 TMAP 값 자리에 채우지 않는다.

| 필드 | TMAP 성공 | 직선거리 폴백 |
| --- | --- | --- |
| `routeSource` | `"TMAP"` | `"STRAIGHT_LINE_FALLBACK"` |
| `walkMinutes` / `walkMeters` | 실제 보행경로 값 | **`null`** |
| `crossings` / `route` | 값 있음 | `null` / `[]` |
| `distanceM` | 직선거리(참고) | 직선거리 |
| `estimatedWalkMinutes` | `null` | 추정 분 |

추정은 직선거리 × 우회보정 1.3 ÷ 50m/분(0.83m/s, 폭염에 천천히 걷는 고령자 기준).
추정으로도 20분을 넘으면 `needsReview: true`.

**2) 안내 문구를 코드가 강제** — `schemas.STRAIGHT_LINE_NOTICE` 고정 문구가
`guidanceSentences` **맨 뒤**(쉼터 안내 직전)에 반드시 들어간다.

> "지금은 길안내를 받을 수 없어서 직선거리로 가장 가까운 쉼터를 알려드렸습니다.
> 실제로 걷는 길과 걸리는 시간은 이보다 길 수 있으니, 나가시기 전에 보호자나
> 담당 복지사에게 한 번 확인해 주세요."

프롬프트로 Alan 에게 규칙 4로 지시하되, 거기에 기대지 않는다.
`llm_client.ensure_straight_line_notice()` 가 결정론적으로 넣는다. Alan 이 이미 넣었으면
중복시키지 않고, **TMAP 경로가 멀쩡한데 붙어 있으면 제거한다.**

**3) 근거검증이 감시** — 양방향 모두 ERROR 로 잡는다.

| code | 언제 |
| --- | --- |
| `STRAIGHT_LINE_NOTICE_MISSING` | 폴백인데 고지문이 없음 |
| `STRAIGHT_LINE_NOTICE_UNEXPECTED` | TMAP 경로인데 고지문이 붙음 |

이 고지문만 `evidenceChunkIds` 가 비어 있어도 `MISSING_EVIDENCE` 를 면제받는다.
매뉴얼에서 나온 사실이 아니라 시스템 상태 고지이기 때문이고, **문구가 고정 템플릿과
정확히 일치할 때만** 면제되므로 이걸 빌미로 근거 없는 문장을 끼워 넣을 수는 없다.

---

## 4. 백엔드 연결

`uvicorn server:app --host 0.0.0.0 --port 8000`

| 메서드 | 경로 | 용도 |
| --- | --- | --- |
| GET | `/health` | 살아있는지 |
| GET | `/v1/diagnostics` | 키·Alan 규격·RAG 준비 상태 한 화면 |
| POST | `/v1/shelter/recommend` | LLM 없이 쉼터만 (프론트 지도용) |
| POST | `/v1/intervention-plans` | **쉼터 + 안내문 + 근거검증 전체** |

### 요청 — 위경도만 주는 방식 (권장)

```json
POST /v1/intervention-plans
{
  "elderlyId": 101,
  "riskSnapshotId": 812,
  "elderlyProfile": {
    "targetAudience": ["ELDERLY"], "age": 82, "livesAlone": true,
    "latitude": 37.5665, "longitude": 126.9780
  },
  "riskSnapshot": {"riskLevel": "HIGH", "riskScore": 0.83, "riskFactors": ["독거", "고령"]},
  "weather": {"temperatureC": 36.2, "heatWarning": "폭염경보"}
}
```

`shelter` 를 안 보내면 서버가 TMAP 으로 직접 고른다. 이미 다른 곳에서 골랐다면
`shelter` 로 넘기면 조회를 건너뛴다 (snake_case/camelCase 둘 다 받는다).

### 응답 200

```json
{
  "elderlyId": 101, "riskLevel": "HIGH",
  "guidanceSentences": [{"text": "...", "evidenceChunkIds": ["heat_illness_manual_v1__0014"]}],
  "recommendedShelter": {
    "name": "종로노인종합복지관 경로당", "address": "서울특별시 종로구 삼봉로 71",
    "walkMinutes": 3, "walkMeters": 162, "crossings": 1,
    "openStatus": "OPEN", "openHoursRaw": "09:00~18:00",
    "route": ["삼봉로를 따라 80m 이동", "횡단보도 후 직진", "도착"],
    "alternatives": [{"name": "을지로경로당", "walkMinutes": 7, "crossings": 0}],
    "needsReview": false, "source": "SEOUL_OPENAPI"
  },
  "emergencyFlag": false,
  "modelUsed": "alan",
  "warnings": []
}
```

`warnings` 는 이번에 추가된 필드다(기존 계약에 더하기만 함). 자동전화를 막을 정도는
아니지만 사회복지사가 알아야 하는 것들이 들어간다 — 쉼터 조회 실패, 숫자 불일치 등.

`modelUsed` 가 `mock-deterministic-v1` 이면 Alan 이 아니라 폴백으로 만들어진 것이다.
시연 전에 이 값을 꼭 확인할 것.

### 응답 422 — 자동전화 보류

```json
{"detail": {"error": "GUIDANCE_GENERATION_BLOCKED",
            "issues": [{"level": "ERROR", "code": "SHELTER_ROUTE_NEEDS_REVIEW", "message": "..."}]}}
```

백엔드는 **422 를 받으면 전화를 걸지 않고** `issues` 를 사회복지사 화면에 노출해야 한다.

| code | 뜻 |
| --- | --- |
| `MISSING_EVIDENCE` | 안내 문장에 근거 chunk_id 가 없다 |
| `FABRICATED_CHUNK_ID` | 검색되지 않은 chunk_id 를 인용했다 (환각) |
| `EMERGENCY_TEMPLATE_MISMATCH` | 응급문구가 승인된 고정 템플릿과 다르다 |
| `SHELTER_NOT_FOUND` | 원천 데이터에 없는 시설 |
| `SHELTER_ROUTE_NEEDS_REVIEW` | 도보 20분 초과 또는 TMAP 실패 — 사람이 먼저 확인 |

### Spring 에서 부르는 경우

이 서버를 내부망에 띄우고 `RestTemplate`/`WebClient` 로 `/v1/intervention-plans` 를 호출하면 된다.
필드명이 전부 camelCase 라 DTO 를 그대로 매핑할 수 있다. FastAPI 단일 서비스로 간다면
`pipeline.generate_intervention_plan()` 을 직접 import 해서 부르면 HTTP 왕복이 없다.

---

## 4-1. needs_review 정책 스위치

쉼터 도보경로를 못 믿는 상황(TMAP 실패 또는 도보 20분 초과)에서 **전화 자체를 막을지**
`.env` 의 `SHELTER_REVIEW_BLOCKS_CALL` 로 정한다.

| 값 | 동작 |
| --- | --- |
| `1` (기본) | `422 SHELTER_ROUTE_NEEDS_REVIEW` — 자동전화 보류. 기존 동작 그대로 |
| `0` | `200` + `recommendedShelter.needsReview: true` + warnings. 전화는 나간다 |

`0` 을 권한다. 폭염 피크에 TMAP 이 쿼터/장애로 흔들리면 `1` 에서는 그날 대상자 **전원의
전화가 조용히 사라진다.** 게다가 쉼터 조회 '실패'는 이미 전화를 막지 않는데(경고만)
경로 '검증 미완료'만 막는 건 앞뒤가 안 맞는다. `0` 으로 두면 전화 모듈이 쉼터 안내만
빼고 "물 드세요 · 낮 시간 외출 마세요" 는 그대로 전달하고, 사회복지사에게는
`needsReview` 로 후속 확인 과제가 남는다.

바꾸기 전에 팀 합의는 받으세요 — 원래 `1` 로 설계한 사람의 의도가 있습니다.

---

## 5. 테스트 (`test_integration.py`)

```bash
python test_integration.py          # 오프라인 — 외부 API 를 하나도 안 부른다 (기본)
python test_integration.py --live   # 실제 서울시/TMAP/Alan 까지
```

**오프라인 24개 통과 + 2개 SKIP(--live 전용)이 정상이다.**

테스트 격리 3원칙 — 여기를 어기면 오진이 난다:

1. `.env` 는 테스트 파일이 **맨 처음** 직접 로드한다. (예전엔 안 했다가, `import server`
   가 [5]단계에서 load_dotenv 를 부르는 바람에 [1]~[4] 는 키 없이 돌고 [5] 부터 실 API 를
   부르는 상태가 됐다.)
2. 가짜 TMAP 은 `offline_shelter()` 컨텍스트 매니저로만 설치하고 반드시 되돌린다.
   `t_fake_tmap_is_restored` 가 이 원칙 자체를 검증한다.
3. 픽스처 의존 단정(쉼터 이름 == "종로노인종합복지관 경로당")은 오프라인에서만.
   `--live` 에서는 구조만 본다.

오프라인 모드에서는 TMAP 만 가짜로 갈아끼우고, 쉼터 목록은 `fixtures/sample_shelters_geo.csv`,
Alan 은 키를 지워 mock 경로로 보낸다. **파이프라인 배선은 진짜 그대로 흐르고 바깥 세상만
바뀐다.** 해커톤 당일 포털이 죽어도 "우리 코드가 깨진 건지"를 즉시 구분할 수 있다.

검증 항목: 도보 최단 선택 / 20분 초과 보류 / TMAP 실패 시 직선거리 대체 금지 /
운영시간 파싱 / 앨런 응답 JSON 추출 4종 / snake·camel 정규화 / 위경도→안내계획 E2E /
쉼터 실패해도 안내 생성 / CRITICAL 고정 응급문구 / 가짜 쉼터 차단 / needs_review 두 정책 /
가짜 TMAP 복구 확인 / HTTP 4개 엔드포인트.

---

## 6. 통합 중에 발견해서 고친 기존 버그

1. **`recommend.py` 문법오류** — 33행 튜플에 쉼표가 빠져 파일 전체가 `SyntaxError`.
   지금 원본을 실행하면 `--demo` 조차 안 돈다.

2. **CRITICAL 위험도가 항상 보류됐다** — `llm_client._find_emergency_template_chunk()` 가
   검색 결과에 없으면 전체 청크에서 응급문구를 찾아 그 `chunk_id` 를 인용했다.
   그런데 그 id 는 이번 검색 결과에 없으므로 `evidence_verifier` 가
   `FABRICATED_CHUNK_ID`(ERROR)로 잡는다. 즉 **가장 위험한 등급의 전화가 매번 막혔다.**
   → `pipeline._ensure_emergency_chunk()` 로 CRITICAL 일 때 응급문구 청크를 검색 결과에
   먼저 포함시켜 해결.

3. **쉼터 실존 검증이 새고 있었다** — `ShelterReferenceIndex.exists()` 가 "이름 + 주소"를
   한 덩어리로 이어붙여 유사도를 쟀다. 질의가 짧으면 아무 레코드와도 0.35 를 넘긴다.
   실제로 `"가상의쉼터12345 서울특별시 어딘가 999"` 가 `"가산동 마을회관"` 에 매칭돼
   **존재하지 않는 쉼터가 검증을 통과했다.** → `exists()` 를 시설명끼리만 비교하도록
   바꾸고 기준을 0.6 으로 올렸다. (`find_by_name_or_address` 는 사람이 찾아보는 용도라 그대로)

4. **README 와 코드 불일치** — README 는 `crossings` / `route` / `alternatives` / `searchOption=30`
   을 출력한다고 써 있었지만 코드에는 없었다. 이번에 구현.
