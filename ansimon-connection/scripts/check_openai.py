#!/usr/bin/env python3
"""OpenAI 키가 Realtime 통화에 쓸 수 있는 상태인지 확인한다.

    python scripts/check_openai.py
"""

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

MODEL = os.getenv("REALTIME_MODEL", "gpt-realtime-2")


async def main() -> None:
    if not (key := os.getenv("OPENAI_API_KEY")):
        sys.exit("OPENAI_API_KEY 미설정")
    print(f"키: {key[:12]}…{key[-4:]}  ({len(key)}자)")

    from openai import AsyncOpenAI

    client = AsyncOpenAI()
    try:
        m = await client.models.retrieve(MODEL)
        print(f"[1] 모델 접근 OK: {m.id}")
    except Exception as e:
        sys.exit(f"[1] 모델 접근 실패: {type(e).__name__}: {e}\n"
                 "     키 폐기 / 프로젝트 권한 / Realtime 미허용 중 하나입니다.")

    # 실제 통화와 같은 경로: Realtime WebSocket 을 열어본다.
    try:
        async with client.realtime.connect(model=MODEL) as conn:
            await conn.session.update(session={"type": "realtime",
                                               "output_modalities": ["audio"]})
            print("[2] Realtime WebSocket 연결 OK — 통화 가능 상태입니다.")
    except Exception as e:
        sys.exit(f"[2] Realtime 연결 실패: {type(e).__name__}: {e}\n"
                 "     결제 수단 미등록 또는 크레딧 소진일 가능성이 큽니다.\n"
                 "     https://platform.openai.com/settings/organization/billing")


if __name__ == "__main__":
    asyncio.run(main())
