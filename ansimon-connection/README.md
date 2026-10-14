# 안심온 (ANSIMON) — 예측형 폭염 돌봄 전화

폭염 위험 **시각**을 예측해 더워지기 **전에** 어르신께 한국어 AI 전화를 걸고,
안내한 행동을 실제로 하실 수 있는지 확인해 **사회복지사 후속 업무로 연결**한다.
직접 사용자 = 사회복지사, 최종 수혜자 = 65세 이상 고령자.

```
백엔드                이 저장소                                        외부
  │
  │ POST /v1/care-runs  ┌───────────────────────────────────┐
  ├────────────────────▶│ contracts  동의·위험도·지역 검증     │
  │                     │     ↓                             │
  │                     │ rag/    :8000 ──────────────────▶ │ 서울열린데이터 · TMAP · LLM
  │                     │     ↓  쉼터 + 안내문 + 근거검증      │
  │                     │ questions  물을 항목=코드, 문장=LLM  │
  │                     │     ↓                             │
  │                     │ voice/  :9000 ──────────────────▶ │ ClawOps 070 · OpenAI Realtime
  │                     │     ↓  통화 → 요약                  │
  │ POST /internal/v1/  │ contracts.build_result            │
  │◀── contact/results ─┴───────────────────────────────────┘
```

---

## 백엔드 연동 — 이것만 보면 된다

### 우리가 백엔드에 보내는 것 (전부)

`POST {ANSIMON_BACKEND_BASE_URL}/internal/v1/contact/results` · 헤더 `Idempotency-Key: {elderlyId}:{riskSnapshotId}:HEAT_PREVENTION_CALL:{attempt}`

```json
{
  "elderlyId": 1,
  "externalCallId": "CA_e2e_9",
  "plan": {
    "actionGuidance": "오늘 낮 두 시부터 네 시까지 더위가 가장 심합니다. 시원한 실내에 머물러 주세요. 물을 조금씩 자주 드세요.",
    "shelterRecommendationText": "가까운 무더위쉼터는 종로노인종합복지관 경로당 입니다. 걸어서 약 8분 거리입니다.",
    "callQuestionOrder": ["쉼터에 가실 의향이 있으신가요?", "혼자서 걸어서 가실 수 있으신가요?", "이동이나 다른 도움이 필요하신가요?"],
    "evidenceDocumentIds": ["heat_illness_manual_v1"]
  },
  "call": {
    "answered": true,
    "summary": "쉼터에 가실 의향은 있으나 무릎 통증으로 혼자 이동이 어려워 동행 지원이 필요합니다.",
    "shelterIntent": "YES", "canMoveAlone": "NO",
    "helpNeeded": "YES", "symptomMentioned": "UNKNOWN",
    "confidence": 0.92,
    "transcriptRef": "clawops/2026/08/19/CA_e2e_9",
    "endedAt": "2026-08-19T02:30:00Z"
  }
}
```

| 필드 | 규칙 |
| --- | --- |
| `elderlyId` | 백엔드가 준 값 그대로. **없으면 400** — 결과를 어느 대상자에 붙일지 알 수 없다 |
| `shelterRecommendationText` | 쉼터가 없으면 `null`. 문장을 지어내지 않는다 |
| `callQuestionOrder` | 실제로 여쭌 순서. `call.*` 네 값과 1:1 로 맞물린다 |
| `evidenceDocumentIds` | 청크 id 가 아니라 **문서** id (`heat_manual_v1__0013` → `heat_manual_v1`), 중복 제거 |
| `answered` | 받으셨는가. 중간에 끊으셔도 `true` — 무슨 일이었는지는 `summary` 앞머리에 남는다 |
| `shelterIntent` 등 | `YES` / `NO` / `UNKNOWN`. 명확히 답하지 않으신 항목은 절대 추측하지 않는다 |
| `confidence` | 0.0~1.0 (소수 4자리) |
| `transcriptRef` | 전사 원문이 아니라 **참조값만** |
| `endedAt` | UTC ISO-8601 + `Z` |

### 백엔드가 우리를 부르는 것

`POST http://localhost:7000/v1/care-runs`

```json
{
  "elderly": {"id": 1, "phone": "010-1234-5678", "age": 78,
              "healthNote": "고혈압, 거동 다소 불편",
              "regionCode": "1114000000", "consentStatus": "AGREED"},
  "location": {"latitude": 37.5665, "longitude": 126.9780},
  "risk": {"id": 7, "score": 0.825, "level": "HIGH",
           "targetStartAt": "2026-08-19T13:00:00", "targetEndAt": "2026-08-19T17:00:00",
           "peakStartAt": "2026-08-19T14:00:00", "peakEndAt": "2026-08-19T16:00:00",
           "topFactors": ["독거"], "modelVersion": "xgb-heat-v1"},
  "weather": {"temperatureC": 36.2, "heatWarning": "폭염경보"}
}
```

응답 `{success, data, error}`. `data.result` 가 위에서 보낸 본문과 **같은 객체**다
(백엔드 주소가 비어 있으면 전송하지 않고 이 응답으로만 돌려준다).
통화가 60~90초라 응답이 그만큼 걸린다.

| 실패 | 뜻 |
| --- | --- |
| `403 CONSENT_REQUIRED` | 동의 상태가 아님 → **전화 안 감** |
| `400 CONTRACT_VIOLATION` | 필수값·범위·시각 순서 위반 |
| `422 GUIDANCE_GENERATION_BLOCKED` | 근거검증 실패 → **전화 안 감**. `issues` 확인 |
| `502 RAG_UNAVAILABLE` / `PHONE_UNAVAILABLE` | 하위 서비스 미기동 |

그 외: `GET /v1/diagnostics` (세 계층·키·백엔드 주소 상태), `GET /health`,
`POST /internal/v1/contact-jobs/{id}/observation` (전화 모듈 전용 콜백 — 백엔드는 쓰지 않는다).

---

## 지역 규칙

공공 무더위쉼터 데이터는 **서울(법정동코드 `11…`)에만** 있다.
그 외 지역은 쉼터를 **조회하지 않고**, 통화 질문에서도 뺀다.

| `regionCode` | 쉼터 조회 | `shelterRecommendationText` | 질문 |
| --- | --- | --- | --- |
| `1114000000` (서울) | O | 문장 | 쉼터 의향 · 혼자 이동 · 도움 필요 (3개) |
| `2600000000` (부산) | X | `null` | 도움 필요 (1개) |
| 없음 | X | `null` | 도움 필요 (1개) + warning |

조회하면 목록이 서울 것뿐이라 수백 km 떨어진 시설이 "가장 가까운 쉼터"로 나온다.
다른 시도 데이터가 들어오면 `.env` 의 `SHELTER_REGION_PREFIX` 만 늘리면 된다.

---

## 실행

```bash
pip install -r requirements.txt
cp .env.example .env          # Windows: copy .env.example .env
python run_all.py             # 세 서비스 동시 실행 (:8000 :9000 :7000)
```

개별 실행 (터미널 3개)

```bash
cd rag   && python -m uvicorn server:app --port 8000
cd voice && python server.py
python server.py
```

점검

```bash
python test_connection.py              # 연결 계층 39개 (외부 API 불필요)
cd rag && python test_integration.py   # RAG 24개 통과 / 2 SKIP 이 정상
python run_demo.py --check             # 세 계층이 살아있는지
python run_demo.py --list              # 샘플 목록
```

데모 — `samples/` 시나리오 5종. 시각은 `"TODAY 13:00"` 표기라 언제 돌려도 오늘 기준이 된다.

```bash
python run_demo.py --file 01_high_shelter.json --dry-run   # 전화 없이 보낼 문장만
python run_demo.py --file 01_high_shelter.json             # 실제 발신 → 요약 → 전송
```

| 샘플 | 보는 것 |
| --- | --- |
| `01_high_shelter.json` | 서울 · HIGH · 쉼터 있음 → 질문 3개 |
| `02_critical.json` | CRITICAL → 응급 안내가 맨 앞, 증상 질문 추가 |
| `03_no_shelter.json` | 부산 → 쉼터 조회 안 함, 질문 1개 |
| `04_minimal.json` | 최소 입력 → 시간 문구·쉼터 문장이 통째로 빠짐 |
| `05_no_consent.json` | 동의 없음 → 403 |

---

## 구성

| | |
| --- | --- |
| `contracts.py` | **계약 단일 지점.** 입력 검증 · 지역 판정 · 최종 payload 생성 |
| `orchestrator.py` | 엔드투엔드 흐름. 콜백 대기 |
| `rag_client.py` · `phone_client.py` · `backend_client.py` | 세 방향 HTTP |
| `questions.py` | 물을 항목은 코드, 문장은 LLM |
| `server.py` | 연결 계층 API (:7000) |
| `rag/` | RAG + 쉼터 (:8000). 자체 테스트 `rag/test_integration.py` |
| `voice/` | ClawOps 발신 + 통화 요약 (:9000) |
| `scripts/` · `docs/` | 키 점검·번호 발급, 통화 워크플로우 문서 |

---

## 설계에서 물러서지 않은 것들

**동의 없으면 전화를 만들지 않는다.** `consentStatus` 가 없거나 모르는 값이면 fail-closed.

**`risk.score` 는 0~1 로 환산한다.** 82.5 같은 백분율이 실제로 들어온다. 환산했다는 사실을
warning 으로 남긴다. ML 이 0~1 로 바꾼 뒤에도 안전망으로 남긴다.

**추정 도보시간을 확정값처럼 말하지 않는다.** TMAP 실측(`routeSource=="TMAP"`)일 때만
"걸어서 N분"을 말한다. 직선거리 폴백이면 대신 고정 고지문이 안내 문장에 들어간다.
어르신이 3분인 줄 알고 나섰다가 15분을 걷는 일을 막는다.

**질문 문장은 LLM 이, 물을 항목은 코드가.** 통화 결과는 네 값으로만 저장된다. 질문이
어긋나면 요약이 전부 `UNKNOWN` 이 되고 통화를 하고도 복지사에게 아무것도 안 남는다.
숫자가 섞인 질문은 슬롯 단위로 템플릿 복귀 — 안내하지 않은 값을 말하게 되니까.

**같은 말을 두 번 하게 하지 않는다.** 답을 들으면 되읽지 않고 바로 다음 질문으로 간다.
확인은 마지막에 한 문장으로 한 번만. 안내 문장도 `guidance` 한 곳에서만 만든다.

**근거 검증 실패(422)는 재시도하지 않는다.** 쉼터를 지어냈거나 응급 문구가 변형됐다는 뜻이라
사람이 봐야 한다.

**결과를 못 받으면 지어내지 않는다.** 콜백이 안 오면 `answered=false` + 전부 `UNKNOWN` +
무슨 일인지 적힌 summary.

**전화번호는 발신 job 에만.** RAG 에도, 결과 payload 에도, 로그에도 없다(뒤 4자리만).
전사 원문 대신 참조값만 보낸다.

**PDF·계약에 없는 값은 만들지 않는다.** 입력의 `age`/`healthNote` 는 결과에 넣지 않고
RAG 컨텍스트로만 보낸다. 대신 건강 메모에서 대상군을 **규칙 기반**으로 뽑고
("고혈압" → `BLOOD_PRESSURE`) 선정 사유를 warning 에 남긴다.

---

## 알아둘 것

**`SHELTER_API_BASE_URL` 은 URL 이 아니라 서울 열린데이터광장 인증키(hex)다.**
`rag/shelter_client.py` 가 이 값을 키로 쓴다. 실제 URL 로 바꾸면 쉼터 조회가 깨진다.

**`SHELTER_SERVICE` 가 무더위쉼터 데이터셋인지 확인할 것.** 기본값 `TbGtnHwcwP` 로
조회했을 때 "휴서울이동노동자…쉼터"(배달·대리운전 종사자용)가 나온 적이 있다. 포털 >
데이터셋 > Open API 탭의 서비스명을 대조하고, 필요하면 `SHELTER_FILE` 로 CSV 를 쓰면 된다.

**앨런 공개 API 는 GET 쿼리스트링이다.** 한글은 URL 인코딩에서 글자당 9바이트가 되어 원래
프롬프트(2,654자)가 11KB 였고 상한 4KB 를 넘겨 매번 mock 으로 폴백했다.
`rag/prompt_builder.py` 를 3.3~3.7KB 로 압축해 해결했다. 한도는 `ALAN_QUERY_MAX_BYTES`.
주최측 POST 엔드포인트를 받으면 `ALAN_API_URL` 에 넣고 `ALAN_API_MODE=openai` 로 바꾼다.
`modelUsed` 가 `mock-deterministic-v1` 이면 폴백된 것이고, 이유가 warning 에 한 줄로 찍힌다.

**`PENDING` 은 프로세스 메모리다.** 서버를 두 대 이상으로 늘리면 Redis 로 올려야 한다.

**데모는 가상 대상자 + 팀원 번호만.** 실제 어르신 정보로 시연하지 않는다.
