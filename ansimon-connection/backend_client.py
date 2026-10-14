# -*- coding: utf-8 -*-
"""백엔드(Spring)로 결과 전송 — `POST /internal/v1/contact/results`.

백엔드가 받는 건 이 한 번의 호출이 전부다 (ContactController.java).
`ANSIMON_BACKEND_BASE_URL` 이 없으면 보내지 않고 본문만 출력한다 — 백엔드 없이도
전 구간을 돌려볼 수 있어야 하기 때문이다.
"""
from __future__ import annotations

import json
import os
from typing import Optional

import aiohttp

PATH = "/internal/v1/contact/results"
TIMEOUT = int(os.getenv("BACKEND_TIMEOUT_SEC", "15"))


def base_url() -> str:
    return (os.getenv("ANSIMON_BACKEND_BASE_URL") or "").split("#")[0].strip().rstrip("/")


async def post_result(payload: dict, idempotency_key: Optional[str] = None) -> Optional[dict]:
    """전송 성공 시 백엔드 응답, 미설정이면 None. 실패는 예외로 올린다 — 삼키면 결과가 증발한다."""
    base = base_url()
    if not base:
        print(f"\n=== 백엔드 전송 예정 payload (ANSIMON_BACKEND_BASE_URL 미설정) ==="
              f"\n{json.dumps(payload, ensure_ascii=False, indent=2)}", flush=True)
        return None

    headers = {"Content-Type": "application/json"}
    if idempotency_key:
        # 재시도는 같은 contact_job 의 attempt 만 올리므로 회차를 붙여야 2차 결과가 안 버려진다.
        headers["Idempotency-Key"] = idempotency_key
    if token := (os.getenv("ANSIMON_BACKEND_TOKEN") or "").strip():
        headers["Authorization"] = f"Bearer {token}"

    async with aiohttp.ClientSession() as s:
        async with s.post(f"{base}{PATH}", json=payload, headers=headers,
                          timeout=aiohttp.ClientTimeout(total=TIMEOUT)) as r:
            body = await r.json(content_type=None)
            print(f"백엔드 전송 {r.status} {base}{PATH}", flush=True)
            if r.status >= 400:
                raise RuntimeError(f"백엔드 {r.status}: {str(body)[:300]}")
            return body
