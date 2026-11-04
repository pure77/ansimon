# Phase A — 하위 서비스(전화 모듈·RAG) 인증 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 연결 서버만 전화 모듈(`:9000`)과 RAG(`:8000`)를 부를 수 있게 만든다. 또 전화 모듈이 모르는 주소로 콜백 토큰을 내보내지 않게 한다.

**Architecture:**
- 1차에서 연결 서버에 넣은 Bearer 미들웨어 패턴을 그대로 쓴다.
- 홉마다 키를 따로 둔다: 연결→전화 `PHONE_API_KEY`, 연결→RAG `RAG_API_KEY`.
- 받는 쪽은 서버 미들웨어(aiohttp)나 의존성(FastAPI)으로 검사한다.
- 보내는 쪽 클라이언트는 키가 없으면 네트워크에 나가기 전에 예외를 낸다.
- 전화 모듈은 `callback_url`의 출처(origin)를 허용 목록과 대조한다.

**Tech Stack:** Python 3.12, aiohttp 3, FastAPI, `hmac.compare_digest`

**Spec:** `docs/superpowers/plans/2026-11-04-security-roadmap.md` §Phase A, §실행 순서와 이유

## Global Constraints

- 키 최소 길이 `32`자. 짧거나 비어 있으면 "설정 안 됨"과 똑같이 취급한다: 서버는 503 `AUTH_NOT_CONFIGURED`, 클라이언트는 전송 전 예외.
- 응답 포맷은 `{success, data, error:{code, message}}`. 코드 문자열: `UNAUTHORIZED`(401), `AUTH_NOT_CONFIGURED`(503), `CALLBACK_NOT_ALLOWED`(400).
- RAG만 기존 FastAPI 관례대로 `HTTPException(detail={"code","message"})`를 쓴다.
- 키 비교는 반드시 `hmac.compare_digest`를 쓴다. 헤더는 `Authorization: Bearer <key>`이고, 스킴은 대소문자를 구분한다(1차와 동일).
- 키는 요청마다 `os.getenv`로 읽는다. 재시작 없이 키를 교체할 수 있게 하려는 것이다.
- `/health`는 모든 서버에서 인증 없이 열어 둔다.
- 전화 모듈·RAG·연결 서버는 실행 디렉터리가 달라 모듈을 공유하지 않는다(`server.py` 이름 충돌). 인증 함수는 서버마다 각자 둔다. 이 중복은 의도된 것이다.
- 테스트 하네스:
  - 연결 서버(전화 모듈 테스트 포함): `cd ansimon-connection && PYTHONIOENCODING=utf-8 python test_connection.py`. 기준선은 44 통과.
  - RAG: `cd ansimon-connection/rag && PYTHONIOENCODING=utf-8 python test_integration.py`.
- 테스트는 실제 전화를 절대 걸면 안 된다. 전화 모듈 테스트는 `run`을 가짜로 바꾼다.

---

## File Structure

| 파일 | 책임 | 변경 |
|---|---|---|
| `ansimon-connection/server.py` | 연결 서버 인증 | 32자 미만 키를 미설정으로 취급 |
| `ansimon-connection/voice/server.py` | 전화 모듈 HTTP 입구 | `require_bearer`(`PHONE_API_KEY`), `callback_url` 허용 목록 |
| `ansimon-connection/phone_client.py` | 연결→전화 클라이언트 | Bearer 헤더, 키 없으면 `PhoneDispatchError` |
| `ansimon-connection/rag/server.py` | RAG HTTP 입구 | `require_api_key` 의존성(`RAG_API_KEY`), 와일드카드 CORS 제거 |
| `ansimon-connection/rag_client.py` | 연결→RAG 클라이언트 | Bearer 헤더, 키 없으면 `RagError` |
| `ansimon-connection/test_connection.py` | 오프라인 통합 테스트 | 전화 모듈 로더와 인증 테스트 추가 |
| `ansimon-connection/rag/test_integration.py` | RAG 테스트 | 인증 테스트, 기존 HTTP 테스트에 키 추가 |
| `.env.example`, `README.md`, `run_all.py`, `docs/RAG_README.md`, `rag/INTEGRATION.md` | 문서 | 새 키 세 개, curl 예시 |

---

### Task 1: 연결 서버 — 32자 미만 키를 미설정으로 취급 (1차 리뷰 F6)

**Files:**
- Modify: `ansimon-connection/server.py` (`_expected_token`)
- Test: `ansimon-connection/test_connection.py`

**Interfaces:**
- Produces: `server.MIN_KEY_LENGTH = 32`

- [ ] **Step 1: Write the failing test**

`test_connection.py`에서 `@at("연결 서버: 키가 설정되지 않으면 열어두지 않고 503 으로 막는다")` 블록 바로 아래에 추가:

```python
@at("연결 서버: 32자 미만 키는 설정 안 된 것으로 보고 503 으로 막는다")
async def _():
    with env(CONNECTION_API_KEY="short-key", ANSIMON_BACKEND_TOKEN="callback-key-000000000000000000000000"):
        async with await _auth_client() as c:
            r = await c.post("/v1/care-runs", data="x", headers=bearer("short-key"))
            assert r.status == 503, r.status
            assert (await r.json())["error"]["code"] == "AUTH_NOT_CONFIGURED"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ansimon-connection && PYTHONIOENCODING=utf-8 python test_connection.py`
Expected: `실패  연결 서버: 32자 미만 키는 ... AssertionError: 400` (짧은 키로도 인증이 통과해 본문 검증까지 간다), `44 통과 / 1 실패`

- [ ] **Step 3: Write minimal implementation**

`server.py`에서 `PUBLIC_PATHS` 아래에 상수를 추가하고 `_expected_token`의 마지막 줄을 바꾼다:

```python
# 이보다 짧은 키는 추측 가능하다. 백엔드 InternalApiProperties 와 같은 기준.
MIN_KEY_LENGTH = 32
```

```python
    name = "ANSIMON_BACKEND_TOKEN" if path.startswith("/internal/") else "CONNECTION_API_KEY"
    token = (os.getenv(name) or "").strip()
    # 짧은 키는 안 넣은 것과 같게 본다 — 문을 열어두지 않는다
    return token if len(token) >= MIN_KEY_LENGTH else ""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ansimon-connection && PYTHONIOENCODING=utf-8 python test_connection.py`
Expected: `45 통과 / 0 실패`

- [ ] **Step 5: Commit**

```bash
git add ansimon-connection/server.py ansimon-connection/test_connection.py
git commit -m "fix(connection): treat keys shorter than 32 chars as unconfigured"
```

---

### Task 2: 연결→전화 모듈 홉에 `PHONE_API_KEY` 인증

**Files:**
- Modify: `ansimon-connection/voice/server.py`
- Modify: `ansimon-connection/phone_client.py`
- Test: `ansimon-connection/test_connection.py`

**Interfaces:**
- Consumes: `test_connection.py`의 `env(**values)`, `bearer(token)`, `at(name)`
- Produces:
  - `voice/server.py`: `PUBLIC_PATHS`, `MIN_KEY_LENGTH`, `fail(code, message, status) -> web.Response`, `require_bearer` 미들웨어
  - `phone_client.py`: `_auth_header() -> dict` (키 없으면 `PhoneDispatchError`)
  - `test_connection.py`: `PHONE_KEY`, `_voice_server()`, `_voice_client(started=None)`. Task 3이 이 셋을 쓴다.

- [ ] **Step 1: Write the failing tests**

`test_connection.py`에서 `if __name__ == "__main__":` 바로 위에 추가:

```python
PHONE_KEY = "phone-key-0000000000000000000000000000"


def _voice_server():
    """voice/server.py 를 'voice_server' 이름으로 한 번만 읽는다 — 연결 서버 server.py 와 이름이 겹친다."""
    import importlib.util
    if "voice_server" in sys.modules:
        return sys.modules["voice_server"]
    voice_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "voice")
    if voice_dir not in sys.path:
        sys.path.append(voice_dir)   # 맨 뒤에 둔다. 앞에 두면 `import server` 가 전화 모듈을 집는다
    spec = importlib.util.spec_from_file_location("voice_server", os.path.join(voice_dir, "server.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["voice_server"] = mod
    spec.loader.exec_module(mod)
    return mod


async def _voice_client(started=None):
    """전화 모듈 테스트 클라이언트. 실제 발신(run)은 기록만 하는 가짜로 바꾼다."""
    from aiohttp.test_utils import TestClient, TestServer
    vs = _voice_server()

    async def fake_run(job, to):
        if started is not None:
            started.append((job["contact_job_id"], to))
        vs.INFLIGHT.discard(job["contact_job_id"])

    vs.run = fake_run
    return TestClient(TestServer(vs.app()))


@at("전화 모듈: /internal/v1/calls 는 PHONE_API_KEY 가 맞아야만 통과하고, 아니면 전화를 걸지 않는다")
async def _():
    started = []
    with env(PHONE_API_KEY=PHONE_KEY):
        async with await _voice_client(started) as c:
            assert (await c.get("/health")).status == 200
            r = await c.post("/internal/v1/calls", json={"contact_job_id": 1})
            assert r.status == 401, r.status
            assert (await r.json())["error"]["code"] == "UNAUTHORIZED"
            r = await c.post("/internal/v1/calls", json={},
                             headers=bearer("wrong-key-000000000000000000000000000"))
            assert r.status == 401
            r = await c.post("/internal/v1/calls", json={},
                             headers={"Authorization": f"Basic {PHONE_KEY}"})
            assert r.status == 401
            # 키가 맞으면 인증은 통과하고 본문 검증(check)에서 400 으로 막힌다
            r = await c.post("/internal/v1/calls", json={}, headers=bearer(PHONE_KEY))
            assert r.status == 400, r.status
    assert not started, "인증 실패/본문 오류인데 전화를 걸었다"


@at("전화 모듈: PHONE_API_KEY 가 없거나 32자 미만이면 503 으로 닫는다")
async def _():
    for value in (None, "short-key"):
        with env(PHONE_API_KEY=value):
            async with await _voice_client() as c:
                if value is None:
                    os.environ.pop("PHONE_API_KEY", None)   # import 시 load_dotenv 가 되살렸을 수 있다
                r = await c.post("/internal/v1/calls", json={}, headers=bearer("short-key"))
                assert r.status == 503, (value, r.status)
                assert (await r.json())["error"]["code"] == "AUTH_NOT_CONFIGURED"
                assert (await c.get("/health")).status == 200


@at("phone_client: PHONE_API_KEY 가 없으면 보내지 않고 PhoneDispatchError")
async def _():
    with env(PHONE_API_KEY=None):
        try:
            await phone_client.dispatch({"contact_job_id": 1})
        except phone_client.PhoneDispatchError as e:
            assert "PHONE_API_KEY" in str(e), e
        else:
            raise AssertionError("키 없이 발신 요청을 보냈다")


@at("phone_client: 발신 요청에 Bearer PHONE_API_KEY 를 붙인다")
async def _():
    from aiohttp import web
    from aiohttp.test_utils import TestServer
    seen = {}

    async def calls(request):
        seen["auth"] = request.headers.get("Authorization")
        return web.json_response({"success": True, "data": {"contact_job_id": 1, "accepted": True},
                                  "error": None}, status=202)

    fake = web.Application()
    fake.add_routes([web.post("/internal/v1/calls", calls)])
    real_base = phone_client.BASE
    async with TestServer(fake) as srv:
        phone_client.BASE = str(srv.make_url("")).rstrip("/")
        try:
            with env(PHONE_API_KEY=PHONE_KEY):
                await phone_client.dispatch({"contact_job_id": 1})
        finally:
            phone_client.BASE = real_base
    assert seen["auth"] == f"Bearer {PHONE_KEY}", seen
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ansimon-connection && PYTHONIOENCODING=utf-8 python test_connection.py`
Expected: 새 테스트 4개 모두 실패.
- 첫째는 `AssertionError: 400`이다. 인증이 없어 본문 검증까지 간다.
- 둘째는 `400`을 받는다.
- 셋째는 연결 거부(`ClientConnectorError`)로 실패한다.
- 넷째는 `seen["auth"]`가 `None`이다.

`45 통과 / 4 실패`

- [ ] **Step 3: Implement the server middleware**

`voice/server.py`:

1. 모듈 docstring의 엔드포인트 목록 아래에 한 줄 추가:
```
인증: /health 외에는 Authorization: Bearer $PHONE_API_KEY 필수 (연결 서버만 발신을 지시한다).
```
2. import에 `import hmac`을 추가한다(`import asyncio` 아래).
3. `INFLIGHT` 정의 아래에 추가:

```python
# 인증 없이 열어 두는 경로. 나머지는 연결 서버의 키가 맞아야 한다.
PUBLIC_PATHS = {"/health"}
# 이보다 짧은 키는 추측 가능하다. 연결 서버·백엔드와 같은 기준.
MIN_KEY_LENGTH = 32
```

4. `ok()` 아래에 추가:

```python
def fail(code: str, message: str, status: int) -> web.Response:
    return web.json_response(
        {"success": False, "data": None, "error": {"code": code, "message": message}}, status=status)


@web.middleware
async def require_bearer(request: web.Request, handler):
    """발신은 실제 전화 요금이 나가고, 결과에는 콜백 토큰이 실린다. 연결 서버만 부를 수 있다."""
    if request.path in PUBLIC_PATHS:
        return await handler(request)
    expected = (os.getenv("PHONE_API_KEY") or "").strip()
    if len(expected) < MIN_KEY_LENGTH:
        # 키를 안 넣었다고 문을 열어두지 않는다
        return fail("AUTH_NOT_CONFIGURED", "서버 인증 키가 설정되지 않았습니다.", 503)
    header = request.headers.get("Authorization", "")
    presented = header[len("Bearer "):].strip() if header.startswith("Bearer ") else ""
    # compare_digest: 응답 시간으로 키를 한 글자씩 맞혀보는 공격을 막는다
    if not presented or not hmac.compare_digest(presented.encode(), expected.encode()):
        return fail("UNAUTHORIZED", "인증이 필요합니다.", 401)
    return await handler(request)
```

5. `app()` 첫 줄을 `a = web.Application(middlewares=[require_bearer])`로 바꾼다.

- [ ] **Step 4: Implement the client header**

`phone_client.py`:

1. docstring의 `est_hackathon/.env 에 반드시 있어야 하는 한 줄:` 블록 아래에 추가:
```
발신 요청에는 Authorization: Bearer $PHONE_API_KEY 를 붙인다. 전화 모듈과 같은 값.
```
2. `TIMEOUT` 아래:

```python
MIN_KEY_LENGTH = 32
```

3. `mask()` 아래:

```python
def _auth_header() -> dict:
    key = (os.getenv("PHONE_API_KEY") or "").strip()
    if len(key) < MIN_KEY_LENGTH:
        # 보내봐야 401 이다. 원인을 여기서 분명히 하고, 전화도 걸리지 않는다.
        raise PhoneDispatchError("PHONE_API_KEY 가 없거나 32자 미만입니다.")
    return {"Authorization": f"Bearer {key}"}
```

4. `dispatch()`의 본문 첫 줄을 `headers = _auth_header()`로 하고, `s.post(...)`에 `headers=headers,`를 추가한다:

```python
async def dispatch(job: dict) -> dict:
    """contact_job 한 건을 발신 큐에 넣는다. 반환은 {"contact_job_id", "accepted", ...}."""
    headers = _auth_header()
    async with aiohttp.ClientSession() as s:
        async with s.post(f"{BASE}/internal/v1/calls", json=job, headers=headers,
                          timeout=aiohttp.ClientTimeout(total=TIMEOUT)) as r:
```

(이하 기존 코드 그대로. `health()`는 `/health`가 공개라 그대로 둔다.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd ansimon-connection && PYTHONIOENCODING=utf-8 python test_connection.py`
Expected: `49 통과 / 0 실패`

- [ ] **Step 6: Commit**

```bash
git add ansimon-connection/voice/server.py ansimon-connection/phone_client.py ansimon-connection/test_connection.py
git commit -m "feat(voice): require PHONE_API_KEY bearer on /internal/v1/calls"
```

---

### Task 3: 전화 모듈 — `callback_url` 출처 허용 목록

`voice/report.py:213`은 결과를 `job["callback_url"]`로 보내면서 `ANSIMON_BACKEND_TOKEN`을 붙인다. 출처를 검사하지 않으면, 키를 아는 쪽이라도 실수나 오설정으로 토큰을 엉뚱한 곳에 보낼 수 있다. Task 2 이전에는 누구나 그럴 수 있었다.

**Files:**
- Modify: `ansimon-connection/voice/server.py` (`calls`, 새 함수 2개)
- Test: `ansimon-connection/test_connection.py`

**Interfaces:**
- Consumes: Task 2의 `PHONE_KEY`, `_voice_client(started)`, `_voice_server()`, `fail()`
- Produces: `voice_server._origin(url) -> str`, `voice_server.allowed_callback_origins() -> set[str]`

- [ ] **Step 1: Write the failing tests**

`test_connection.py`에서 Task 2 테스트들 아래(`if __name__` 위)에 추가:

```python
@at("전화 모듈: 허용 목록에 없는 callback_url 이면 전화를 걸지 않고 400 CALLBACK_NOT_ALLOWED")
async def _():
    started = []
    with env(PHONE_API_KEY=PHONE_KEY, CONNECTION_CALLBACK_URL="http://localhost:7000",
             ANSIMON_BACKEND_BASE_URL=None, PHONE_CALLBACK_ALLOWED_ORIGINS=None):
        async with await _voice_client(started) as c:
            os.environ.pop("ANSIMON_BACKEND_BASE_URL", None)
            os.environ.pop("PHONE_CALLBACK_ALLOWED_ORIGINS", None)
            for evil in ("https://evil.example/steal",
                         "http://localhost:7000.evil.example",   # 접미사 붙이기
                         "http://localhost:7000@evil.example",   # userinfo 위장
                         "http://localhost:7001"):               # 포트 다름
                r = await c.post("/internal/v1/calls", headers=bearer(PHONE_KEY),
                                 json={"contact_job_id": 1, "callback_url": evil})
                assert r.status == 400, (evil, r.status)
                assert (await r.json())["error"]["code"] == "CALLBACK_NOT_ALLOWED", evil
    assert not started


@at("전화 모듈: 허용된 출처(경로·대소문자 무관)면 발신을 접수한다")
async def _():
    import copy
    started = []
    with env(PHONE_API_KEY=PHONE_KEY, CONNECTION_CALLBACK_URL="http://localhost:7000",
             ANSIMON_BACKEND_BASE_URL="https://api.ansimon.example/",
             PHONE_CALLBACK_ALLOWED_ORIGINS="http://conn.railway.internal:7000, "):
        async with await _voice_client(started) as c:
            job = copy.deepcopy(sys.modules["job"].DEMO_JOB)
            job["to_number"] = "01000000000"
            for i, cb in enumerate(("http://localhost:7000/", "HTTPS://API.ansimon.example",
                                    "http://conn.railway.internal:7000/x", None), start=1):
                job["contact_job_id"] = 9000 + i
                if cb is None:
                    job.pop("callback_url", None)   # 없으면 report 가 env 로 떨어진다 → 허용
                else:
                    job["callback_url"] = cb
                r = await c.post("/internal/v1/calls", headers=bearer(PHONE_KEY), json=job)
                assert r.status == 202, (cb, r.status, await r.text())
            await asyncio.sleep(0)   # create_task 로 띄운 가짜 run 이 돌 시간
    assert [jid for jid, _ in started] == [9001, 9002, 9003, 9004], started
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ansimon-connection && PYTHONIOENCODING=utf-8 python test_connection.py`
Expected:
- 첫 테스트는 `ContentTypeError`로 실패한다. 지금은 출처를 검사하지 않아 `check()`의 text/plain 400이 돌아오고, 그래서 `r.json()`이 실패한다.
- 둘째 테스트는 지금 코드로도 통과한다. 허용 출처만 보내므로, 동작이 바뀌지 않았음을 확인하는 회귀 테스트다.

`50 통과 / 1 실패`

- [ ] **Step 3: Write minimal implementation**

`voice/server.py`:

1. import에 `from urllib.parse import urlsplit`을 추가한다.
2. `require_bearer` 아래에 추가:

```python
def _clean(value: str | None) -> str:
    """.env 값에 인라인 주석·공백이 섞여도 비교가 깨지지 않게 한다 (orchestrator._env 와 같은 규칙)."""
    return (value or "").split("#")[0].strip()


def _origin(url: str) -> str:
    """scheme://host:port 만 남긴다. userinfo(@) 가 섞인 주소는 netloc 이 달라져 일치하지 않는다."""
    parts = urlsplit(url.strip())
    return f"{parts.scheme}://{parts.netloc}".lower()


def allowed_callback_origins() -> set[str]:
    """결과(+콜백 토큰)를 보내도 되는 곳. 요청마다 읽어 .env 변경이 재시작 없이 반영된다.

    연결 서버가 job 에 싣는 기본 주소(CONNECTION_CALLBACK_URL, 없으면 localhost:CONNECTION_PORT)와
    report.py 의 폴백(ANSIMON_BACKEND_BASE_URL)은 자동으로 들어간다.
    """
    urls = [u for u in _clean(os.getenv("PHONE_CALLBACK_ALLOWED_ORIGINS")).split(",")]
    urls.append(_clean(os.getenv("CONNECTION_CALLBACK_URL"))
                or f"http://localhost:{_clean(os.getenv('CONNECTION_PORT')) or '7000'}")
    urls.append(_clean(os.getenv("ANSIMON_BACKEND_BASE_URL")))
    return {_origin(u) for u in urls if u.strip()}
```

3. `calls()`의 앞부분을 다음으로 바꾼다. 기존 `try: job = check(await request.json()) ...` 블록을 대체하고, 그 아래(`to = job.get("to_number")`부터)는 그대로 둔다:

```python
async def calls(request: web.Request) -> web.Response:
    try:
        body = await request.json()
    except ValueError as e:
        raise web.HTTPBadRequest(reason=str(e))

    callback = body.get("callback_url") if isinstance(body, dict) else None
    if callback and _origin(callback) not in allowed_callback_origins():
        # 결과와 함께 콜백 토큰이 그 주소로 나간다. 모르는 곳이면 전화도 걸지 않는다.
        return fail("CALLBACK_NOT_ALLOWED", "허용되지 않은 callback_url 입니다.", 400)

    try:
        job = check(body)
        facts(job)          # 안내할 내용이 없으면 전화를 걸기 전에 되돌린다
    except (ValueError, TypeError, AttributeError) as e:
        raise web.HTTPBadRequest(reason=str(e))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ansimon-connection && PYTHONIOENCODING=utf-8 python test_connection.py`
Expected: `51 통과 / 0 실패`

- [ ] **Step 5: Commit**

```bash
git add ansimon-connection/voice/server.py ansimon-connection/test_connection.py
git commit -m "feat(voice): refuse callback_url outside the allowed origins before dialing"
```

---

### Task 4: 연결→RAG 홉에 `RAG_API_KEY` 인증, 와일드카드 CORS 제거

**Files:**
- Modify: `ansimon-connection/rag/server.py`
- Modify: `ansimon-connection/rag_client.py`
- Test: `ansimon-connection/rag/test_integration.py`, `ansimon-connection/test_connection.py`

**Interfaces:**
- Produces:
  - `rag/server.py`: `MIN_KEY_LENGTH`, `require_api_key(authorization: Optional[str] = Header(default=None)) -> None`
  - `rag_client.py`: `_auth_header() -> dict` (키 없으면 `RagError`)

- [ ] **Step 1: Write the failing RAG server tests**

`rag/test_integration.py`:

1. `t_http_endpoints()` 안의 `client = TestClient(server.app)` 바로 아래에 두 줄을 넣는다. 기존 호출 세 곳(`/v1/diagnostics`, `/v1/shelter/recommend`, `/v1/intervention-plans`)에는 `headers=AUTH`를 추가한다:

```python
    os.environ["RAG_API_KEY"] = RAG_KEY
    AUTH = {"Authorization": f"Bearer {RAG_KEY}"}
```

예: `diag = client.get("/v1/diagnostics", headers=AUTH).json()`, `client.post("/v1/shelter/recommend", json=..., headers=AUTH)`, `client.post("/v1/intervention-plans", json=body, headers=AUTH)`. LIVE 분기 안에 있는 호출들도 같은 방식으로 바꾼다. 이 함수에서 `/v1/`로 시작하는 `client.get`·`client.post` 호출에는 모두 `headers=AUTH`를 붙인다.

2. `t_http_endpoints` 정의 바로 위에 추가:

```python
RAG_KEY = "rag-key-00000000000000000000000000000000"


def t_http_requires_api_key():
    from fastapi.testclient import TestClient
    import server

    client = TestClient(server.app)
    os.environ["RAG_API_KEY"] = RAG_KEY
    assert client.get("/health").status_code == 200, "헬스체크는 공개"
    for method, path in (("get", "/v1/diagnostics"), ("post", "/v1/shelter/recommend"),
                         ("post", "/v1/intervention-plans")):
        r = getattr(client, method)(path, json={} if method == "post" else None)
        assert r.status_code == 401, (path, r.status_code)
        assert r.json()["detail"]["code"] == "UNAUTHORIZED", r.text
        r = getattr(client, method)(path, json={} if method == "post" else None,
                                    headers={"Authorization": "Bearer wrong-key-0000000000000000000000000"})
        assert r.status_code == 401, (path, r.status_code)

    for value in ("", "short-key"):
        os.environ["RAG_API_KEY"] = value
        r = client.get("/v1/diagnostics", headers={"Authorization": f"Bearer {value}"})
        assert r.status_code == 503, (value, r.status_code)
        assert r.json()["detail"]["code"] == "AUTH_NOT_CONFIGURED"
    os.environ["RAG_API_KEY"] = RAG_KEY

    r = client.options("/v1/intervention-plans", headers={
        "Origin": "http://evil.example", "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in {k.lower() for k in r.headers}, "브라우저 CORS 를 열지 않는다"
```

3. `main()`의 `check("/health /diagnostics /shelter /intervention-plans", t_http_endpoints)` 바로 위에 추가:

```python
    check("인증 없으면 401, 키 미설정·짧으면 503, CORS 없음", t_http_requires_api_key)
```

- [ ] **Step 2: Write the failing client tests**

`test_connection.py`에서 Task 3 테스트들 아래에 추가:

```python
RAG_KEY = "rag-key-00000000000000000000000000000000"


@at("rag_client: RAG_API_KEY 가 없으면 보내지 않고 RagError")
async def _():
    with env(RAG_API_KEY=None):
        try:
            await rag_client.create_intervention_plan(1, 1, {}, {})
        except rag_client.RagError as e:
            assert "RAG_API_KEY" in str(e), e
        else:
            raise AssertionError("키 없이 RAG 를 불렀다")


@at("rag_client: 안내계획 요청에 Bearer RAG_API_KEY 를 붙인다")
async def _():
    from aiohttp import web
    from aiohttp.test_utils import TestServer
    seen = {}

    async def plans(request):
        seen["auth"] = request.headers.get("Authorization")
        return web.json_response({"guidanceSentences": []})

    fake = web.Application()
    fake.add_routes([web.post("/v1/intervention-plans", plans)])
    real_base = rag_client.BASE
    async with TestServer(fake) as srv:
        rag_client.BASE = str(srv.make_url("")).rstrip("/")
        try:
            with env(RAG_API_KEY=RAG_KEY):
                await rag_client.create_intervention_plan(1, 1, {}, {})
        finally:
            rag_client.BASE = real_base
    assert seen["auth"] == f"Bearer {RAG_KEY}", seen
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd ansimon-connection/rag && PYTHONIOENCODING=utf-8 python test_integration.py`
Expected: `FAIL  인증 없으면 401 ...`. 지금은 인증이 없어 200 또는 422가 나온다.

Run: `cd ansimon-connection && PYTHONIOENCODING=utf-8 python test_connection.py`
Expected: `51 통과 / 2 실패`

- [ ] **Step 4: Implement the RAG server dependency**

`rag/server.py`:

1. docstring의 엔드포인트 목록 아래에 한 줄 추가:
```
인증: /health 외에는 Authorization: Bearer $RAG_API_KEY 필수 (연결 서버만 부른다).
```
2. import를 바꾼다:
   - `import hmac`을 추가한다.
   - `from fastapi import FastAPI, HTTPException`을 `from fastapi import Depends, FastAPI, Header, HTTPException`으로 바꾼다.
   - `from fastapi.middleware.cors import CORSMiddleware` 줄은 지운다.
3. `app.add_middleware(CORSMiddleware, ...)` 블록과 그 위 주석 두 줄을 지운다. 그 자리에 추가:

```python
# 이보다 짧은 키는 추측 가능하다. 연결 서버·백엔드와 같은 기준.
MIN_KEY_LENGTH = 32


def require_api_key(authorization: Optional[str] = Header(default=None)) -> None:
    """연결 서버만 부른다. 호출마다 유료 LLM·TMAP 이 돌아서 키 없이 열어두지 않는다.

    브라우저가 직접 부르는 화면이 없으므로 CORS 도 열지 않는다.
    """
    expected = (os.getenv("RAG_API_KEY") or "").strip()
    if len(expected) < MIN_KEY_LENGTH:
        raise HTTPException(status_code=503, detail={
            "code": "AUTH_NOT_CONFIGURED", "message": "서버 인증 키가 설정되지 않았습니다."})
    presented = ""
    if authorization and authorization.startswith("Bearer "):
        presented = authorization[len("Bearer "):].strip()
    if not presented or not hmac.compare_digest(presented.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED", "message": "인증이 필요합니다."})
```

4. 세 라우트 데코레이터에 의존성을 붙인다(`/health`는 그대로):

```python
@app.get("/v1/diagnostics", dependencies=[Depends(require_api_key)])
@app.post("/v1/shelter/recommend", dependencies=[Depends(require_api_key)])
@app.post("/v1/intervention-plans", dependencies=[Depends(require_api_key)])
```

(기존 데코레이터에 `response_model` 같은 인자가 있으면 그대로 두고 `dependencies=`만 덧붙인다.)

- [ ] **Step 5: Implement the client header**

`rag_client.py`:

1. docstring 마지막 줄 아래에 추가:
```
요청에는 Authorization: Bearer $RAG_API_KEY 를 붙인다. RAG 서버와 같은 값.
```
2. `TIMEOUT` 아래:

```python
MIN_KEY_LENGTH = 32


def _auth_header() -> dict:
    key = (os.getenv("RAG_API_KEY") or "").strip()
    if len(key) < MIN_KEY_LENGTH:
        # 보내봐야 401 이다. 원인을 여기서 분명히 한다 → orchestrator 가 502 RAG_UNAVAILABLE 로 올린다.
        raise RagError("RAG_API_KEY 가 없거나 32자 미만입니다.")
    return {"Authorization": f"Bearer {key}"}
```

(`RagError` 클래스 정의보다 아래에 있어야 한다. 클래스 정의들 바로 아래, `_post` 위에 둔다.)

3. `_post`의 `session.post(...)`에 `headers=_auth_header(),`를 추가한다:

```python
    async with session.post(f"{BASE}{path}", json=body, headers=_auth_header(),
                            timeout=aiohttp.ClientTimeout(total=TIMEOUT)) as r:
```

4. `diagnostics()`의 `s.get(...)`에도 `headers=_auth_header(),`를 추가한다.

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd ansimon-connection/rag && PYTHONIOENCODING=utf-8 python test_integration.py`
Expected: `FAIL` 0개. 새 항목 `PASS  인증 없으면 401, ...`

Run: `cd ansimon-connection && PYTHONIOENCODING=utf-8 python test_connection.py`
Expected: `53 통과 / 0 실패`

- [ ] **Step 7: Commit**

```bash
git add ansimon-connection/rag/server.py ansimon-connection/rag_client.py ansimon-connection/rag/test_integration.py ansimon-connection/test_connection.py
git commit -m "feat(rag): require RAG_API_KEY bearer and drop wildcard CORS"
```

---

### Task 5: 설정 예시와 문서

**Files:**
- Modify: `ansimon-connection/.env.example`
- Modify: `ansimon-connection/README.md`
- Modify: `ansimon-connection/run_all.py`
- Modify: `ansimon-connection/docs/RAG_README.md`
- Modify: `ansimon-connection/rag/INTEGRATION.md`

- [ ] **Step 1: `.env.example`**

`CONNECTION_API_KEY=` 줄 바로 아래에 추가:

```
# 연결 서버 → 하위 서비스 키. 홉마다 다른 값, 각 32자 이상 (openssl rand -hex 32).
# 하나가 새도 다른 홉은 열리지 않는다. 같은 .env 를 세 서비스가 함께 읽으므로 양쪽이 자동으로 같다.
# 연결 서버 → 전화 모듈 POST /internal/v1/calls
PHONE_API_KEY=
# 연결 서버 → RAG /v1/**
RAG_API_KEY=
# 전화 모듈이 통화 결과(+ANSIMON_BACKEND_TOKEN)를 보내도 되는 출처, 쉼표 구분.
# CONNECTION_CALLBACK_URL(없으면 http://localhost:CONNECTION_PORT)과 ANSIMON_BACKEND_BASE_URL 은 자동 포함.
PHONE_CALLBACK_ALLOWED_ORIGINS=
```

- [ ] **Step 2: `README.md`**

`README.md:94` 근처의 `그 외: GET /v1/diagnostics ...` 줄 아래에 인증 표를 추가한다:

```markdown
### 서비스 간 인증

| 호출 | 헤더 | 받는 쪽이 비교하는 값 |
|---|---|---|
| 백엔드 → 연결 `/v1/**` | `Bearer $CONNECTION_API_KEY` | `CONNECTION_API_KEY` |
| 전화 → 연결 `/internal/**` | `Bearer $ANSIMON_BACKEND_TOKEN` | `ANSIMON_BACKEND_TOKEN` |
| 연결 → 전화 `/internal/v1/calls` | `Bearer $PHONE_API_KEY` | `PHONE_API_KEY` |
| 연결 → RAG `/v1/**` | `Bearer $RAG_API_KEY` | `RAG_API_KEY` |

키가 없거나 32자 미만이면 받는 쪽은 503 `AUTH_NOT_CONFIGURED`로 닫히고, 보내는 쪽은 요청을 보내지 않는다.
`/health`는 어디서나 공개다. 전화 모듈은 `callback_url`이 허용 출처(`PHONE_CALLBACK_ALLOWED_ORIGINS` 외)가 아니면
전화를 걸지 않고 400 `CALLBACK_NOT_ALLOWED`를 돌려준다.
```

- [ ] **Step 3: `run_all.py` 안내 문구**

`print(f"\n  RAG   http://localhost:{RAG_PORT}/docs\n"` 블록에서 다음과 같이 바꾼다:
- RAG 줄: `f"  RAG   http://localhost:{RAG_PORT}/docs   (API 호출은 Authorization: Bearer $RAG_API_KEY 필요)\n"`
- 전화 줄: `f"  전화  http://localhost:{PHONE_PORT}/health   (발신은 Authorization: Bearer $PHONE_API_KEY 필요)\n"`

- [ ] **Step 4: RAG 문서의 curl 예시**

`docs/RAG_README.md:224`의 `curl -X POST http://localhost:8000/v1/intervention-plans \` 다음 줄에 다음 줄을 추가한다:

```
  -H "Authorization: Bearer $RAG_API_KEY" \
```

`rag/INTEGRATION.md:220`의 문장 끝에 다음을 덧붙인다: ` 요청마다 `Authorization: Bearer $RAG_API_KEY` 헤더가 필요하다(`/health` 제외).`

- [ ] **Step 5: 문서에 남은 무인증 호출 예시가 없는지 확인**

Run: `cd ansimon-connection && grep -rn "localhost:8000/v1\|localhost:9000/internal" --include=*.md --include=*.py . | grep -v "Authorization"`
Expected: 출력된 각 줄이 curl 예시가 아니거나, 같은 블록 다음 줄에 `Authorization` 헤더가 있다. 헤더가 빠진 curl 예시가 있으면 Step 4와 같은 방식으로 고친다.

- [ ] **Step 6: 전체 회귀**

Run: `cd ansimon-connection && PYTHONIOENCODING=utf-8 python test_connection.py`
Expected: `53 통과 / 0 실패`

Run: `cd ansimon-connection/rag && PYTHONIOENCODING=utf-8 python test_integration.py`
Expected: `실패 0`

- [ ] **Step 7: Commit**

```bash
git add ansimon-connection/.env.example ansimon-connection/README.md ansimon-connection/run_all.py ansimon-connection/docs/RAG_README.md ansimon-connection/rag/INTEGRATION.md
git commit -m "docs(connection): document per-hop keys for phone and RAG services"
```

---

## 배포 체크리스트 (Phase A 머지 후)

1. Railway(또는 실행 환경)에 `PHONE_API_KEY`와 `RAG_API_KEY`를 등록한다. 각각 `openssl rand -hex 32`로 만든 서로 다른 값이다. 연결·전화·RAG 세 서비스가 같은 값을 읽어야 한다.
2. 연결 서버와 전화 모듈이 다른 호스트에 있으면, 전화 모듈에 `PHONE_CALLBACK_ALLOWED_ORIGINS`로 연결 서버의 실제 출처를 넣는다.
3. 배포 순서: 키 등록 → RAG·전화 모듈 → 연결 서버. 연결 서버를 먼저 올리면 키가 없는 하위 서비스에 보내게 되는데, 이때는 하위 서비스가 503을 돌려줄 뿐 전화가 걸리지는 않는다.
4. 확인: 키 없이 `curl -X POST <전화>/internal/v1/calls`를 보내 401(키 미등록이면 503)이 오는지, `GET <연결>/v1/diagnostics`의 `rag.up`·`phone.up`이 모두 `true`인지 본다.
