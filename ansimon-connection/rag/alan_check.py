# -*- coding: utf-8 -*-
"""Alan API 작동 확인 스크립트

    python alan_check.py                      # 전체 진단
    python alan_check.py --mode=alan_query    # 특정 규격만
    python alan_check.py --url=https://.../question   # 엔드포인트 직접 지정
    python alan_check.py --json               # 결과를 JSON 으로 (CI/백엔드 헬스체크용)

무엇을 확인하나:
  1) .env 에서 키를 읽어오는가 (값은 가려서 표시)
  2) 엔드포인트에 네트워크가 닿는가
  3) 어떤 호출 규격이 실제로 응답하는가  <- 이게 핵심. 문서 없이도 여기서 확정된다
  4) 안심온이 실제로 쓰는 JSON 출력 지시를 따르는가 (형식 준수 여부)

3단계에서 통과한 규격 이름을 .env 의 ALAN_API_MODE 에 넣으면 이후 호출이 고정된다.
전부 실패해도 파이프라인은 mock 생성기로 계속 돈다 — 데모가 죽지는 않는다.
"""
from __future__ import annotations

import json
import os
import socket
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

import alan_client  # noqa: E402

PING = "1 더하기 1은 얼마인가요? 숫자만 답하세요."

# 안심온이 실제로 보내는 것과 같은 형태의 최소 프롬프트.
# 규격이 뚫려도 이걸 못 따르면 evidence_verifier 가 전부 막으므로 미리 확인한다.
JSON_SYSTEM = """너는 JSON 만 출력하는 API 다. 설명·인사말·코드블록 표시를 붙이지 마라.
아래 스키마 그대로 반환하라.
{"guidanceSentences": [{"text": "<문장>", "evidenceChunkIds": ["<id>"]}], "emergencyFlag": false, "emergencyMessage": null, "recommendedShelter": null}"""
JSON_USER = """[RAG 근거 청크]
- chunk_id=test__0001 | text="더운 날에는 갈증을 느끼지 않아도 물을 자주 마신다."

위 근거 청크의 내용만 사용해 안내 문장 1개를 만들어 JSON 으로 답하라."""


def _mask(value: str) -> str:
    if not value:
        return "(없음)"
    return f"{value[:6]}…{value[-2:]} (len={len(value)})"


def _load_env() -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv(BASE_DIR / ".env")
    except ImportError:
        # python-dotenv 없이도 돌게 최소 파서를 둔다 (팀원 환경 편차 흡수)
        env_path = BASE_DIR / ".env"
        if not env_path.exists():
            return
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def check_reachable(url: str) -> tuple[bool, str]:
    host = urlparse(url).hostname
    if not host:
        return False, "URL 파싱 실패"
    try:
        t0 = time.perf_counter()
        socket.getaddrinfo(host, None)
        return True, f"DNS OK ({(time.perf_counter() - t0) * 1000:.0f}ms) {host}"
    except socket.gaierror as e:
        return False, f"DNS 실패 {host}: {e}"


def probe(mode: str, url: str, key: str) -> dict:
    """어댑터 하나를 실제로 호출해 본다."""
    result: dict = {"mode": mode, "describe": alan_client.ADAPTERS[mode].describe}
    t0 = time.perf_counter()
    try:
        text = alan_client.call_raw(mode, "너는 계산기다.", [{"role": "user", "content": PING}],
                                    key=key, url=url)
        result |= {"ok": True, "ms": round((time.perf_counter() - t0) * 1000),
                   "sample": text.strip()[:120]}
    except requests.HTTPError as e:
        body = e.response.text[:200] if e.response is not None else ""
        result |= {"ok": False, "ms": round((time.perf_counter() - t0) * 1000),
                   "error": f"HTTP {e.response.status_code if e.response is not None else '?'}",
                   "detail": body}
    except Exception as e:
        result |= {"ok": False, "ms": round((time.perf_counter() - t0) * 1000),
                   "error": type(e).__name__, "detail": str(e)[:200]}
    return result


def probe_json_format(mode: str, url: str, key: str) -> dict:
    """JSON 출력 지시를 따르는지 확인한다."""
    try:
        text = alan_client.call_raw(mode, JSON_SYSTEM, [{"role": "user", "content": JSON_USER}],
                                    key=key, url=url)
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"[:200]}

    try:
        parsed = alan_client.extract_json(text)
    except ValueError as e:
        return {"ok": False, "error": str(e)[:200], "raw": text[:200]}

    sentences = parsed.get("guidanceSentences") or []
    has_ids = bool(sentences) and all(s.get("evidenceChunkIds") for s in sentences)
    return {
        "ok": True,
        "clean_json": text.strip().startswith("{"),   # 설명 없이 JSON 만 왔는가
        "sentences": len(sentences),
        "evidence_ids_filled": has_ids,
        "parsed": parsed,
    }


def main() -> int:
    _load_env()
    as_json = "--json" in sys.argv
    only = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--mode=")), None)
    url = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--url=")),
               (os.getenv("ALAN_API_URL") or "").strip())
    key = (os.getenv("ALAN_API_KEY") or "").strip()

    report: dict = {"key": _mask(key), "url": url or "(미지정 — 어댑터 기본값 사용)", "probes": []}

    if not as_json:
        print("=" * 62)
        print(" Alan API 진단")
        print("=" * 62)
        print(f"  ALAN_API_KEY : {report['key']}")
        print(f"  ALAN_API_URL : {report['url']}")
        print(f"  ALAN_API_MODE: {os.getenv('ALAN_API_MODE') or '(미지정 -> auto)'}")

    if not key:
        report["fatal"] = "ALAN_API_KEY 가 .env 에 없습니다."
        print(json.dumps(report, ensure_ascii=False, indent=2) if as_json
              else f"\n  X {report['fatal']}\n    -> .env 에 ALAN_API_KEY=... 를 넣고 다시 실행하세요.")
        return 2

    target = url or alan_client.ALAN_QUERY_URL
    reachable, msg = check_reachable(target)
    report["reachable"] = {"ok": reachable, "message": msg}
    if not as_json:
        print(f"\n[1] 네트워크: {'OK' if reachable else 'FAIL'} — {msg}")

    modes = [only] if only else list(alan_client.AUTO_ORDER)
    if not as_json:
        print("\n[2] 호출 규격 탐색")
    for mode in modes:
        if mode not in alan_client.ADAPTERS:
            continue
        if mode in ("openai", "json_post") and not (url or os.getenv("LLM_BASE_URL")):
            skipped = {"mode": mode, "ok": False, "error": "SKIP",
                       "detail": "이 규격은 엔드포인트가 필요합니다 (--url= 또는 .env 의 ALAN_API_URL/LLM_BASE_URL)"}
            report["probes"].append(skipped)
            if not as_json:
                print(f"  - {mode:<11} SKIP  ({skipped['detail']})")
            continue

        r = probe(mode, url, key)
        report["probes"].append(r)
        if not as_json:
            if r["ok"]:
                print(f"  O {r['mode']:<11} {r['ms']:>5}ms  {r['describe']}")
                print(f"      응답: {r['sample']}")
            else:
                print(f"  X {r['mode']:<11} {r['ms']:>5}ms  {r['error']} — {r.get('detail', '')[:120]}")

    winner = next((p["mode"] for p in report["probes"] if p.get("ok")), None)
    report["working_mode"] = winner

    if winner:
        fmt = probe_json_format(winner, url, key)
        report["json_format"] = fmt
        if not as_json:
            print(f"\n[3] JSON 출력 형식 준수 ({winner})")
            if fmt["ok"]:
                print(f"  - JSON 파싱      : OK ({'설명 없이 JSON 만' if fmt['clean_json'] else '앞뒤 설명 있음 — extract_json 이 걷어냄'})")
                print(f"  - 안내 문장 수   : {fmt['sentences']}")
                print(f"  - 근거 ID 채움   : {'OK' if fmt['evidence_ids_filled'] else 'X — 근거검증에서 막힙니다'}")
                if not fmt["evidence_ids_filled"]:
                    print("    -> prompt_builder 의 규칙 2를 더 강하게 하거나, LLM_FALLBACK_TO_MOCK=1 로 두세요.")
            else:
                print(f"  X {fmt['error']}")

        if not as_json:
            print("\n" + "=" * 62)
            print(f"  결론: Alan API 작동함 (규격 = {winner})")
            print("  .env 에 아래를 넣으면 이후 호출이 이 규격으로 고정됩니다:")
            print(f"    ALAN_API_MODE={winner}")
            if url:
                print(f"    ALAN_API_URL={url}")
            print("=" * 62)
    elif not as_json:
        print("\n" + "=" * 62)
        print("  결론: 어떤 규격으로도 응답을 못 받았습니다.")
        print("  확인 순서:")
        print("   1) 주최측(ESTsoft) 문서의 엔드포인트를 --url= 로 직접 넣어 재시도")
        print("   2) 키가 client_id(UUID)인지 Bearer 토큰인지 확인")
        print("   3) 사내망/방화벽에서 해당 도메인이 막혀있지 않은지 확인")
        print("  * 그동안에도 파이프라인은 mock 생성기로 돌아갑니다 (데모 가능).")
        print("=" * 62)

    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if winner else 1


if __name__ == "__main__":
    raise SystemExit(main())
