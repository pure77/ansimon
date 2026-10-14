# -*- coding: utf-8 -*-
"""안심온 연결 서버 (:7000).

    python server.py

    POST /v1/care-runs
         body = {"elderly": {...}, "location": {...}, "risk": {...}}
         → RAG → 전화 → 요약까지 끝낸 뒤, 백엔드 계약 그대로의 payload 를 반환하고
           ANSIMON_BACKEND_BASE_URL 이 있으면 POST /internal/v1/contact/results 로 보낸다.
           통화가 60~90초라 응답이 그만큼 걸린다.

    POST /internal/v1/contact-jobs/{id}/observation      ← est_hackathon/report.py 콜백
    GET  /v1/diagnostics                                 세 계층이 다 살아 있는지
    GET  /health

응답은 세 저장소 공통 포맷 {success, data, error} 를 따른다.
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

from aiohttp import web

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass

import backend_client
import contracts
import orchestrator
import phone_client
import rag_client

PORT = int(os.getenv("CONNECTION_PORT", "7000"))


def ok(data, status: int = 200) -> web.Response:
    return web.json_response({"success": True, "data": data, "error": None}, status=status)


def fail(code: str, message: str, status: int, **extra) -> web.Response:
    return web.json_response(
        {"success": False, "data": extra or None, "error": {"code": code, "message": message}},
        status=status)


async def care_runs(request: web.Request) -> web.Response:
    try:
        payload = await request.json()
    except Exception:
        return fail("BAD_REQUEST", "JSON 본문이 아닙니다.", 400)

    try:
        return ok(await orchestrator.run(payload))
    except contracts.ConsentError as e:
        return fail("CONSENT_REQUIRED", str(e), 403)
    except contracts.ContractError as e:
        return fail("CONTRACT_VIOLATION", str(e), 400)
    except orchestrator.Blocked as e:
        # 전화를 걸지 않았다는 뜻이지 서버 오류가 아니다. 422 로 구분한다.
        return web.json_response({"success": False, "data": e.result,
                                  "error": {"code": e.result["code"],
                                            "message": e.result["reason"]}}, status=422)
    except rag_client.RagError as e:
        return fail("RAG_UNAVAILABLE", str(e), 502)
    except phone_client.PhoneDispatchError as e:
        return fail("PHONE_UNAVAILABLE", str(e), 502)


async def observation(request: web.Request) -> web.Response:
    """est_hackathon/voice/report.py 의 send() 가 때리는 곳.

    body = {"observation": {...}, "meta": {...}}
    헤더 Idempotency-Key = "{idempotency_key}:{attempt_count}"
    """
    try:
        body = await request.json()
    except Exception:
        return fail("BAD_REQUEST", "JSON 본문이 아닙니다.", 400)

    obs, meta = body.get("observation") or {}, body.get("meta") or {}
    try:
        job_id = int(request.match_info["contact_job_id"])
    except (KeyError, ValueError):
        return fail("BAD_REQUEST", "contact_job_id 가 정수가 아닙니다.", 400)

    matched = orchestrator.deliver(job_id, obs, meta)
    # 기다리는 사람이 없어도 200 이다. 여기서 4xx 를 주면 전화 모듈이 재전송을 반복한다.
    return ok({"contact_job_id": job_id, "matched": matched,
               "idempotency_key": request.headers.get("Idempotency-Key")})


async def diagnostics(_: web.Request) -> web.Response:
    """시연 전에 이 한 번으로 세 계층을 다 본다."""
    async def probe(coro):
        try:
            return {"up": True, "detail": await coro}
        except Exception as e:
            return {"up": False, "detail": f"{type(e).__name__}: {str(e)[:200]}"}

    rag, phone = await asyncio.gather(probe(rag_client.diagnostics()),
                                      probe(phone_client.health()))
    return ok({
        "connection": {"up": True, "port": PORT},
        "rag": {**rag, "baseUrl": rag_client.BASE},
        "phone": {**phone, "baseUrl": phone_client.BASE},
        "keys": {k: bool((os.getenv(k) or "").strip())
                 for k in ("ALAN_API_KEY", "TMAP_APP_KEY", "SHELTER_API_BASE_URL",
                           "CLAWOPS_API_KEY", "OPENAI_API_KEY")},
        "consentAccepts": sorted(contracts.CONSENT_OK),
        "backend": {"baseUrl": backend_client.base_url() or None,
                    "path": backend_client.PATH},
        "shelterRegionPrefix": contracts.SHELTER_REGION_PREFIX,
        "hint": "전화 모듈(est_hackathon)의 .env 에 "
                f"ANSIMON_BACKEND_BASE_URL=http://localhost:{PORT} 이 있어야 결과가 돌아옵니다.",
    })


def app() -> web.Application:
    a = web.Application()
    a.add_routes([
        web.post("/v1/care-runs", care_runs),
        web.post("/internal/v1/contact-jobs/{contact_job_id}/observation", observation),
        web.get("/v1/diagnostics", diagnostics),
        web.get("/health", lambda _: ok({"status": "UP"})),
    ])
    return a


if __name__ == "__main__":
    print(f"안심온 연결 서버 :{PORT}\n"
          f"  RAG   → {rag_client.BASE}\n"
          f"  전화  → {phone_client.BASE}\n"
          f"  콜백  ← POST /internal/v1/contact-jobs/{{id}}/observation", flush=True)
    web.run_app(app(), port=PORT)
