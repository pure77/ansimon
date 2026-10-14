# -*- coding: utf-8 -*-
"""원커맨드 데모 — 입력 한 건을 넣고 최종 (contact_job, call_observation) 까지 본다.

    python run_demo.py --dry-run            전화 없이 발신 직전까지 (RAG·질문·계약 검증)
    python run_demo.py                      실제 발신 (.env 의 DEMO_PHONE 으로)
    python run_demo.py --phone 01012345678
    python run_demo.py --file payload.json

먼저 띄워둘 것:
    anshimon-rag$      uvicorn server:app --port 8000
    est_hackathon$     python voice/server.py
그리고 est_hackathon/.env 에  ANSIMON_BACKEND_BASE_URL=http://localhost:7000

이 스크립트는 콜백을 받기 위해 같은 서버를 프로세스 안에서 잠깐 띄운다.
따로 server.py 를 실행할 필요가 없다.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

from aiohttp import web

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass

import contracts
import orchestrator
import phone_client
import rag_client
import server

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
SAMPLES = HERE / "samples"


def resolve_times(payload: dict) -> dict:
    """샘플 파일이 시간이 지나도 그대로 쓰이게 한다.

    "TODAY 13:00" / "TOMORROW 09:00" / "NOW" 를 실제 시각으로 바꾼다.
    날짜를 박아두면 며칠 뒤엔 '8월 18일 낮 한 시부터' 같은 지난 시각을 읽어준다.
    """
    base = datetime.now(contracts.KST)

    def one(v):
        if not isinstance(v, str):
            return v
        if v == "NOW":
            return base.isoformat()
        for word, days in (("TODAY ", 0), ("TOMORROW ", 1)):
            if v.startswith(word):
                h, m = v[len(word):].split(":")
                return (base + timedelta(days=days)).replace(
                    hour=int(h), minute=int(m), second=0, microsecond=0).isoformat()
        return v

    if isinstance(payload.get("risk"), dict):
        payload["risk"] = {k: one(v) for k, v in payload["risk"].items()}
    return payload


async def preflight() -> bool:
    """전화를 걸기 전에 세 계층을 확인한다. 잘못된 설정으로 통화를 태우지 않는다."""
    print("사전 점검")
    ok = True
    try:
        d = await rag_client.diagnostics()
        note = "  ← Alan 미연결, 안내문이 mock 으로 나옵니다" if d.get("willUseMock") else ""
        print(f"  [OK] RAG   {rag_client.BASE}{note}")
        missing = [k for k, v in (d.get("keys") or {}).items() if not v]
        if missing:
            print(f"       키 미설정: {', '.join(missing)}")
        if not (d.get("rag") or {}).get("chunksReady", True):
            print("       out/chunks.jsonl 없음 → anshimon-rag 에서 python ingest.py")
            ok = False
    except Exception as e:
        print(f"  [--] RAG   {rag_client.BASE} 응답 없음 ({type(e).__name__})\n"
              f"       anshimon-rag$ uvicorn server:app --port 8000")
        ok = False
    try:
        await phone_client.health()
        print(f"  [OK] 전화  {phone_client.BASE}")
    except Exception as e:
        print(f"  [--] 전화  {phone_client.BASE} 응답 없음 ({type(e).__name__})\n"
              f"       est_hackathon$ python voice/server.py")
        ok = False
    print(f"  [OK] 콜백  {orchestrator.CALLBACK_BASE}  (job 에 실어 보내므로 "
          f"전화 모듈 .env 설정이 필요 없습니다)")
    return ok


def demo_payload(phone: str) -> dict:
    """문서의 예시 입력 그대로. 시각만 '오늘' 기준으로 채운다.

    consent_status 가 없으면 contracts 가 발신을 거부한다(운영 유의사항 1번).
    데모 대상자는 가상 인물 + 팀원 번호다 — 실제 어르신 정보를 넣지 않는다.
    """
    base = datetime.now(contracts.KST).replace(minute=0, second=0, microsecond=0)
    start = base.replace(hour=13)
    return {
        "elderly": {
            "id": 1,                      # 백엔드 elderly_profile PK. 결과가 붙을 대상자.
            "name": "김안심",
            "phone": phone,
            "age": 78,
            "healthNote": "고혈압, 거동 다소 불편",
            "address": "서울특별시 중구 세종대로 110",
            "regionCode": "1114000000",
            "consentStatus": "AGREED",
        },
        "location": {"latitude": 37.5665, "longitude": 126.9780},
        "risk": {
            "score": 82.5,                    # 0~100 스케일 → contracts 가 0.825 로 환산
            "level": "HIGH",
            "generatedAt": datetime.now(contracts.KST).isoformat(),
            "targetStartAt": start.isoformat(),
            "targetEndAt": (start + timedelta(hours=4)).isoformat(),
            "peakStartAt": (start + timedelta(hours=1)).isoformat(),
            "peakEndAt": (start + timedelta(hours=3)).isoformat(),
            "topFactors": ["독거", "고령", "체감온도 36도"],
            "modelVersion": "xgb-heat-v1",
        },
        "weather": {"temperatureC": 36.2, "heatWarning": "폭염경보"},
        "approvedBy": "demo-social-worker",
    }


async def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--phone", default=os.getenv("DEMO_PHONE") or os.getenv("TEST_RECIPIENT_PHONE"))
    p.add_argument("--file", help="요청 JSON 파일 (없으면 내장 데모 입력)")
    p.add_argument("--dry-run", action="store_true", help="발신 직전까지만")
    p.add_argument("--check", action="store_true", help="사전 점검만 하고 끝")
    p.add_argument("--force", action="store_true", help="사전 점검이 실패해도 발신")
    p.add_argument("--list", action="store_true", help="샘플 입력 목록")
    args = p.parse_args()

    if args.list:
        for f in sorted(SAMPLES.glob("*.json")):
            d = json.loads(f.read_text(encoding="utf-8"))
            print(f"  samples/{f.name:26} {d.get('_설명', '')}")
        return 0

    if args.check:
        return 0 if await preflight() else 1

    if args.file:
        path = Path(args.file)
        if not path.exists() and (SAMPLES / args.file).exists():
            path = SAMPLES / args.file          # 파일명만 줘도 samples/ 에서 찾는다
        payload = resolve_times(json.loads(path.read_text(encoding="utf-8")))
        payload.pop("_설명", None)
        if args.phone or not payload.get("elderly", {}).get("phone"):
            payload.setdefault("elderly", {})["phone"] = args.phone or ""
        print(f"입력: {path.name}")
    else:
        if not args.phone:
            sys.exit("전화번호가 없습니다: --phone 01012345678 또는 .env 의 DEMO_PHONE")
        payload = demo_payload(args.phone)
    payload["dryRun"] = args.dry_run

    if not args.dry_run and not await preflight() and not args.force:
        print("\n사전 점검 실패 — 전화를 걸지 않았습니다. 무시하려면 --force")
        return 1

    # 콜백 수신용 서버를 프로세스 안에서 띄운다 (dry-run 이면 필요 없다)
    runner = None
    if not args.dry_run:
        runner = web.AppRunner(server.app())
        await runner.setup()
        try:
            await web.TCPSite(runner, port=server.PORT).start()
        except OSError as e:
            # 대개 server.py 를 따로 띄워둔 채로 run_demo 를 또 돌린 경우다.
            print(f"콜백 포트 {server.PORT} 를 열 수 없습니다 ({e}).\n"
                  f"  이미 python server.py 가 떠 있다면 그걸 끄거나, "
                  f".env 의 CONNECTION_PORT 를 다른 값으로 바꾸세요.")
            return 4
        print(f"콜백 대기 :{server.PORT}", flush=True)

    if not args.dry_run:
        print(f"\n발신합니다 → {phone_client.mask(payload['elderly']['phone'])} "
              f"(통화 60~90초, 결과 콜백까지 기다립니다)\n")

    try:
        result = await orchestrator.run(payload)
    except contracts.ConsentError as e:
        print(f"동의 없음 — 전화를 만들지 않았습니다.\n  {e}"); return 2
    except contracts.ContractError as e:
        print(f"입력이 계약을 어깁니다.\n  {e}"); return 2
    except orchestrator.Blocked as e:
        result = e.result
        print(f"\n전화 보류 [{result['code']}]\n  {result['reason']}")
        for i in result.get("issues") or []:
            print(f"  · [{i.get('level')}] {i.get('code')}: {i.get('message')}")
    except rag_client.RagError as e:
        print(f"RAG 계층에 닿지 못했습니다 ({rag_client.BASE}).\n  {e}\n"
              f"  anshimon-rag 에서: uvicorn server:app --port 8000"); return 3
    finally:
        if runner:
            await runner.cleanup()

    OUT.mkdir(exist_ok=True)
    path = OUT / f"care_run_{datetime.now(contracts.KST):%Y%m%d_%H%M%S}.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n" + "─" * 60)
    if result.get("result"):
        print("\n■ 백엔드로 보내는 본문  POST /internal/v1/contact/results")
        print(json.dumps(result["result"], ensure_ascii=False, indent=2))
    elif result.get("call_job_preview"):
        j = result["call_job_preview"]
        print("\n■ 전화에 넘어갈 내용 (dryRun — 실제로 걸지 않음)")
        for k, v in j["guidance"].items():
            print(f"  {k}: {v}")
        for i, q in enumerate(j["questions"], 1):
            print(f"  질문{i}: {q}")
    if result.get("warnings"):
        print("\n■ warnings")
        for w in result["warnings"]:
            print(f"  · {w}")
    print(f"\n상태 {result.get('status')}   전체 결과 → {path}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
