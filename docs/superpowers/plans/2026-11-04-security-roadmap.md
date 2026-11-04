# 안심온 보안 2차 로드맵 (Phase A–D)

> 1차(`2026-11-03-internal-api-authentication.md`, PR pure77/ansimon#1)에서 백엔드 `/internal/**`와
> 연결 서버에 Bearer 키 인증을 붙였다. 이 문서는 그 뒤에 남은 네 가지 구멍을 어떤 순서로, 어떤
> 설계로 막을지 정한다. Phase A·B는 바로 실행 가능한 상세 계획이 따로 있다.

| Phase | 내용 | 상세 계획 | 상태 |
|---|---|---|---|
| A | 연결 서버의 하위 서비스(전화 모듈 `:9000`, RAG `:8000`) 인증 | `2026-11-04-phase-a-downstream-service-auth.md` | 실행 가능 |
| B | 관리자 로그인 + JWT (`/api/**` 보호) | `2026-11-04-phase-b-admin-jwt.md` | 실행 가능 |
| D | Railway 사설 네트워크로 내부 서비스 격리 | 이 문서 §D (실행 직전에 상세화) | 사전 확인 필요 |
| C | 서비스 간 요청 서명(HMAC) + 재전송 방지 | 이 문서 §C (실행 직전에 상세화) | 설계만 |

## 실행 순서와 이유: A → B → D → C

실제 피해 크기와 노출 정도 순으로 정했다.

1. **A가 가장 급하다.** 전화 모듈 `POST /internal/v1/calls`에는 인증이 전혀 없고, 다음 두 가지가 동시에 가능하다.
   - 본문 `to_number`에 아무 번호나 넣으면 ClawOps 070으로 **실제 전화가 나간다** (요금 남용).
   - 본문 `callback_url`을 공격자 주소로 넣으면, `voice/report.py:213`이 그 주소로
     `Authorization: Bearer $ANSIMON_BACKEND_TOKEN`을 실어 보낸다. 1차에서 만든 백엔드 내부 키가
     **그대로 유출된다.**

   RAG `:8000`도 인증 없이 열려 있고 CORS가 `*`라서, 누구나 유료 LLM·TMAP 호출을 일으킬 수 있다.
   변경량은 작은데(파이썬 파일 4개) 막는 위험은 가장 크다.
2. **B.** `/api/v1/elderly`가 인증 없이 어르신 이름·전화번호·주소·건강 정보를 돌려준다(개인정보).
   `/api/v1/guidance/care-runs/{id}`는 누구나 실제 전화를 걸게 한다. 1차에서 "관리자 JWT 전까지
   열려 있음"으로 남겨 둔 항목이다.
3. **D.** A·B로 "키 없이는 못 부른다"를 만든 뒤, 내부 서비스를 인터넷에서 아예 안 보이게 한다.
   키가 새더라도 외부에서는 못 쓴다(심층 방어). Railway에 지금 무엇이 어떻게 배포돼 있는지
   저장소만으로는 확인할 수 없어서, 실행 직전에 현황을 확인하고 상세화한다.
4. **C는 마지막이다.** TLS와 사설망이 있으면 HMAC이 추가로 주는 것은 다음 세 가지다.
   - 키가 전송 경로에 실리지 않는다.
   - 본문을 바꿀 수 없다.
   - 같은 요청을 다시 보내는 공격(재전송)을 막는다.

   위험 대비 효과는 가장 작다. 다만 "통화 결과 위·변조 방지"라는 설명거리가 생긴다.

ML 서버(`heatwave_ml_model-main`, `:8100`)는 범위에서 뺐다. 지역 단위 폭염 예측이라 개인정보도
과금도 없고, D에서 사설망으로 들어가면 충분하다.

---

## Phase A — 하위 서비스 인증 (요약)

상세: `2026-11-04-phase-a-downstream-service-auth.md`

- 홉마다 키를 따로 둔다(최소 권한). 한 키가 새도 다른 홉은 안전하다.
  - 연결 → 전화 모듈 `/internal/v1/calls`: `PHONE_API_KEY`
  - 연결 → RAG `/v1/**`: `RAG_API_KEY`
- 전화 모듈은 `callback_url`의 출처(origin)를 허용 목록과 대조한다. 목록에 없으면 **전화를 걸기 전에** 400을 돌려준다.
- RAG의 와일드카드 CORS는 지운다. 브라우저가 RAG를 직접 부르는 화면이 없다.
- 모든 파이썬 서버에서 키가 32자 미만이면 "설정 안 됨"으로 보고 503을 돌려준다(1차 리뷰 지적 F6).
- 1차에서 띄운 후속 작업 카드(task_39bbf9b1)는 이 Phase가 대체한다.

## Phase B — 관리자 JWT (요약)

상세: `2026-11-04-phase-b-admin-jwt.md`

- `admin_account` 테이블(V4)을 만든다. 회원가입 API는 없다. 첫 관리자는 환경변수
  `ADMIN_BOOTSTRAP_LOGIN_ID`·`ADMIN_BOOTSTRAP_PASSWORD`로, 테이블이 비어 있을 때 한 번만 만든다.
- `POST /api/v1/auth/login` → HS256 JWT(기본 1시간)를 발급한다. 리프레시 토큰은 두지 않는다(YAGNI).
  돌봄 실행 한 건이 최대 2분이라 1시간이면 충분하다.
- Spring Security OAuth2 Resource Server로 `/api/**`를 보호한다. 로그인과 CORS preflight만 예외다.
- 비밀번호는 `DelegatingPasswordEncoder`(bcrypt)로 저장한다. 없는 아이디로 로그인해도 해시 비교를
  수행해, 응답 시간으로 계정 존재 여부를 알 수 없게 한다.
- 프론트엔드 변경:
  - `login.html`을 추가한다.
  - `assets/api.js`가 `sessionStorage`의 토큰을 모든 요청에 붙이고, 401을 받으면 로그인 화면으로 보낸다.
  - 직접 `fetch`하는 두 곳(`index.html`, `elderly-detail.html`)에도 같은 헤더를 붙인다.
- 범위 밖: 로그인 시도 제한, 역할 구분, 리프레시 토큰. 남은 과제로 기록한다.

---

## Phase D — 네트워크 격리 (설계)

**목표:** 인터넷에서 닿는 서비스는 백엔드(관리자 API)뿐이고, 나머지는 Railway 사설망
(`*.railway.internal`)으로만 서로 부른다.

**사전 확인 (실행 전에 사용자와 함께):**
1. Railway 프로젝트에 현재 어떤 서비스가 있는가: 백엔드는 CI로 배포된다. 연결·전화·RAG·ML은 미확인이다.
2. 각 서비스에 Public Domain이 붙어 있는가.
3. 전화 모듈의 ClawOps SDK가 바깥에서 들어오는 연결(웹훅, 미디어 스트림)을 받는가.
   `voice/call.py`는 `ClawOps`·`ClawOpsAgent`로 나가는 연결만 쓰는 것으로 보이지만, 실제 통화로 확인해야 한다.
   들어오는 연결이 필요하면 전화 모듈만 공개 도메인을 유지하고, `/internal/v1/calls`는 A의 키로 보호한다.
4. 관리자 프론트 정적 파일을 어디서 서빙하는가. 백엔드와 같은 출처가 되면 CORS를 좁힐 수 있다.

**변경 (예상):**

| 대상 | 변경 |
|---|---|
| 연결 서버 `server.py` | `web.run_app(..., host="::")`. Railway 사설망은 IPv6라 `0.0.0.0`만 바인드하면 안 닿는다. |
| 전화 모듈 `voice/server.py` | 위와 동일 |
| RAG | `uvicorn server:app --host :: --port $PORT` |
| ML | `uvicorn api:app --host :: --port $PORT` |
| 백엔드 env | `CONNECTION_BASE_URL=http://<connection>.railway.internal:7000`, `ML_API_BASE_URL=http://<ml>.railway.internal:8100` |
| 연결 env | `RAG_BASE_URL`, `PHONE_API_BASE_URL`, `ANSIMON_BACKEND_BASE_URL`(백엔드도 사설 주소로), `CONNECTION_CALLBACK_URL` |
| Railway 콘솔 | 백엔드를 뺀 서비스의 Public Domain 삭제 |

**검증:**
- 각 공개 도메인에 대한 `curl`이 실패한다.
- 백엔드 컨테이너 셸에서 `curl http://<connection>.railway.internal:7000/health`가 200을 돌려준다.
- 돌봄 실행이 처음부터 끝까지 한 번 성공한다.

**남겨 두는 것:** A·B의 키 인증은 지우지 않는다. 사설망은 "닿지 않음"이고 키는 "닿아도 못 씀"이라
둘은 서로 다른 층이다.

## Phase C — 요청 서명 HMAC (설계)

**대상 홉:** 결과 데이터가 오가는 콜백 두 곳부터 적용한다.
- 연결 → 백엔드 `/internal/v1/contact/results`
- 전화 → 연결 `/internal/v1/contact-jobs/{id}/observation`

`/v1/care-runs` 같은 명령 호출은 그다음이다.

**서명 형식 (v1):**
```
X-Ansimon-Key-Id:    k1                       # 키 교체용 식별자
X-Ansimon-Timestamp: 1767225600               # 유닉스 초
X-Ansimon-Signature: v1=<hex HMAC-SHA256(secret, canonical)>
canonical = timestamp + "\n" + METHOD + "\n" + path(쿼리 포함) + "\n" + hex(SHA-256(raw body))
```

**검증 규칙:**
- 시각 차이가 ±300초를 넘으면 401.
- 서명은 상수 시간으로 비교한다.
- `Idempotency-Key`를 TTL 10분 캐시에 넣어 같은 요청이 다시 오면 막는다. 이미 처리한 키는 지금처럼
  200을 돌려준다. 4xx를 주면 전화 모듈이 재전송을 반복한다(`server.py` 주석).

**백엔드 구현 포인트:**
- 서명 검증에 원문 본문이 필요하다. 그래서 본문을 미리 읽어 두는 `HttpServletRequestWrapper`를
  필터에 둔다. `ContentCachingRequestWrapper`는 컨트롤러가 읽은 뒤에야 내용을 채우므로 이 용도에 맞지 않는다.
- 전환 기간에는 Bearer와 HMAC을 둘 다 받는다. 송신 측을 모두 바꾼 뒤 Bearer를 끈다(`ansimon.internal.require-signature=true`).

**파이썬 구현 포인트:** 서명 함수 하나와 검증 미들웨어 하나다. 연결·전화 모듈은 실행 경로가 달라
모듈을 공유하지 않으므로 같은 코드를 각자 둔다(Phase A와 같은 이유).

## 열린 질문 (실행 전에 정할 것)

- B: 관리자 계정을 여러 명 둘지, 역할(조회 전용 / 실행 가능)을 나눌지. 지금 계획은 단일 역할이다.
- D: 위 "사전 확인" 네 가지.
- C: 실제로 할지. 시간이 빠듯하면 D에서 멈춰도 보안 서술은 충분히 성립한다.
