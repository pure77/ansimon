# -*- coding: utf-8 -*-
"""est_hackathon/voice(:9000) HTTP 클라이언트.

저쪽은 POST /internal/v1/calls 를 받으면 **202 만 돌려주고 통화는 백그라운드**로 돈다.
결과는 report.py 가 ANSIMON_BACKEND_BASE_URL 로 되쏘는 콜백으로 온다.
그래서 이 모듈은 "던지기"만 하고, 받는 쪽은 orchestrator.deliver() 다.

est_hackathon/.env 에 반드시 있어야 하는 한 줄:
    ANSIMON_BACKEND_BASE_URL=http://localhost:7000
이게 없으면 report.py 가 결과를 콘솔에만 찍고 끝나서 여기로 아무것도 돌아오지 않는다.

est_hackathon 실행:  python voice/server.py
"""
from __future__ import annotations

import os

import aiohttp

BASE = (os.getenv("PHONE_API_BASE_URL") or "http://localhost:9000").rstrip("/")
TIMEOUT = int(os.getenv("PHONE_DISPATCH_TIMEOUT_SEC", "20"))


class PhoneDispatchError(RuntimeError):
    """발신 접수 자체가 실패. 통화 실패와는 다르다 — 이건 재시도할 값어치가 있다."""


def mask(number: str) -> str:
    """로그에는 뒤 4자리만. 워크플로우 §6."""
    return "*" * max(len(number) - 4, 0) + number[-4:]


async def dispatch(job: dict) -> dict:
    """contact_job 한 건을 발신 큐에 넣는다. 반환은 {"contact_job_id", "accepted", ...}."""
    async with aiohttp.ClientSession() as s:
        async with s.post(f"{BASE}/internal/v1/calls", json=job,
                          timeout=aiohttp.ClientTimeout(total=TIMEOUT)) as r:
            body = await r.json(content_type=None)
            if r.status not in (200, 202):
                raise PhoneDispatchError(f"전화 모듈 {r.status}: {body}")
            data = (body or {}).get("data") or {}
            if not data.get("accepted", True):
                # 같은 job 이 이미 통화 중. 두 번 걸지 않는 게 정답이라 예외로 올리지 않는다.
                raise PhoneDispatchError(f"발신 거부: {data.get('reason')}")
            return data


async def health() -> dict:
    async with aiohttp.ClientSession() as s:
        async with s.get(f"{BASE}/health", timeout=aiohttp.ClientTimeout(total=10)) as r:
            return await r.json(content_type=None)
