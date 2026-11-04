#!/usr/bin/env python3
"""Spring 이 호출하는 발신 엔드포인트.

백엔드 .env.example 의 PHONE_API_BASE_URL=http://localhost:9000 이 여기를 가리킨다.
경로는 백엔드 AGENTS.md 규약대로 내부용 /internal/v1/**.

    python voice/server.py

    POST /internal/v1/calls   body = contact_job 한 건 (voice/job.py 모양)
         → 202 즉시 반환. 통화는 백그라운드, 결과는 report.py 가 Spring 으로 콜백.
    GET  /health

인증: /health 외에는 Authorization: Bearer $PHONE_API_KEY 필수 (연결 서버만 발신을 지시한다).
"""

from __future__ import annotations

import asyncio
import hmac
import os

from aiohttp import web

from call import facts, main, setup
from job import check
from report import report

# 같은 job 이 두 번 들어와 어르신께 전화가 두 번 가는 것을 막는다.
# ponytail: 프로세스 메모리. 서버를 여러 대로 늘리면 Redis 나 DB 락으로 올려야 한다.
INFLIGHT: set[int] = set()

# 인증 없이 열어 두는 경로. 나머지는 연결 서버의 키가 맞아야 한다.
PUBLIC_PATHS = {"/health"}
# 이보다 짧은 키는 추측 가능하다. 연결 서버·백엔드와 같은 기준.
MIN_KEY_LENGTH = 32


def ok(data: dict, status: int = 200) -> web.Response:
    """백엔드 공통 응답 포맷 {success, data, error}."""
    return web.json_response({"success": True, "data": data, "error": None}, status=status)


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


async def run(job: dict, to: str) -> None:
    try:
        await main(job, to)
    except Exception as e:                     # 통화 실패를 Spring 이 모르면 안 된다
        print(f"! 발신 실패 {type(e).__name__}: {e}", flush=True)
        await report([], job, end_reason="error")
    finally:
        INFLIGHT.discard(job["contact_job_id"])


async def calls(request: web.Request) -> web.Response:
    try:
        job = check(await request.json())
        facts(job)          # 안내할 내용이 없으면 전화를 걸기 전에 되돌린다
    except (ValueError, TypeError, AttributeError) as e:
        raise web.HTTPBadRequest(reason=str(e))

    to = job.get("to_number")                  # 원본 번호는 DB 아닌 별도 보관소 값
    if not to:
        raise web.HTTPBadRequest(reason="to_number 없음")

    jid = job["contact_job_id"]
    if jid in INFLIGHT:
        return ok({"contact_job_id": jid, "accepted": False, "reason": "already_calling"})
    INFLIGHT.add(jid)

    asyncio.create_task(run(job, to))          # 통화는 60~90초. 응답을 붙잡아두지 않는다
    return ok({"contact_job_id": jid, "accepted": True}, status=202)


def app() -> web.Application:
    a = web.Application(middlewares=[require_bearer])
    a.add_routes([
        web.post("/internal/v1/calls", calls),
        web.get("/health", lambda _: ok({"status": "UP"})),
    ])
    return a


if __name__ == "__main__":
    setup()
    web.run_app(app(), port=int(os.getenv("PHONE_API_PORT", "9000")))
