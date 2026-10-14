#!/usr/bin/env python3
"""세 서비스를 한 번에 띄운다.

    python run_all.py

  :8000  rag/    RAG + 쉼터 추천 (uvicorn)
  :9000  voice/  전화 발신
  :7000  ./      연결 계층 — 백엔드가 붙는 곳

Ctrl+C 로 전부 내린다. 터미널을 나눠 띄우고 싶으면 README 의 '개별 실행' 참고.
로그는 자식 프로세스가 그대로 이 터미널에 쓴다 — 통화 내용도 여기 흐른다.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent

try:
    from dotenv import load_dotenv
    load_dotenv(HERE / ".env")        # 자식들이 os.environ 을 물려받는다
except ImportError:
    sys.exit("pip install -r requirements.txt 먼저 실행하세요.")

RAG_PORT = os.getenv("RAG_PORT", "8000")
PHONE_PORT = os.getenv("PHONE_API_PORT", "9000")
CONN_PORT = os.getenv("CONNECTION_PORT", "7000")

SERVICES = [
    ("rag  ", [sys.executable, "-m", "uvicorn", "server:app", "--port", RAG_PORT], HERE / "rag"),
    ("voice", [sys.executable, "server.py"], HERE / "voice"),
    ("conn ", [sys.executable, "server.py"], HERE),
]


def main() -> int:
    if not (HERE / ".env").exists():
        print("! .env 가 없습니다. .env.example 을 복사해서 키를 채우세요.\n"
              "  copy .env.example .env      (Windows)\n"
              "  cp .env.example .env        (macOS/Linux)")
        return 1
    if not (HERE / "rag" / "out" / "chunks.jsonl").exists():
        print("! rag/out/chunks.jsonl 이 없습니다 → cd rag && python ingest.py")
        return 1

    procs: list[tuple[str, subprocess.Popen]] = []
    try:
        for name, cmd, cwd in SERVICES:
            print(f"[{name}] {' '.join(cmd)}  (cwd={cwd.name or '.'})", flush=True)
            procs.append((name, subprocess.Popen(cmd, cwd=cwd)))
            time.sleep(1.5)          # 포트가 열릴 시간. 뒤 서비스가 앞을 헬스체크하지 않으므로 이걸로 충분하다

        print(f"\n  RAG   http://localhost:{RAG_PORT}/docs\n"
              f"  전화  http://localhost:{PHONE_PORT}/health\n"
              f"  연결  http://localhost:{CONN_PORT}/v1/diagnostics   ← 백엔드는 여기로\n"
              f"\nCtrl+C 로 전부 종료. 데모: python run_demo.py --file 01_high_shelter.json\n",
              flush=True)

        while True:                  # 하나라도 죽으면 전부 내린다 — 반쯤 살아있는 상태가 제일 헷갈린다
            for name, p in procs:
                if p.poll() is not None:
                    print(f"\n! [{name}] 이 종료됐습니다 (코드 {p.returncode}). 전부 내립니다.")
                    return p.returncode or 1
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n종료합니다…")
        return 0
    finally:
        for _, p in procs:
            if p.poll() is None:
                p.terminate()          # 윈도우·유닉스 모두 이거면 된다
        for _, p in procs:
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()


if __name__ == "__main__":
    sys.exit(main())
