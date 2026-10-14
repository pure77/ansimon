#!/usr/bin/env python3
"""안심온 — 입력된 번호로 ClawOps 예방 안내전화 1건 발신.

    pip install "clawops[agent,openai]"
    python voice/call.py 01012345678

범위: 발신까지. 결과 구조화/Spring 콜백/재시도는 CLAWOPS_PHONE_WORKFLOW Phase 4~5.
"""
import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from clawops import ClawOps
from clawops.agent import BuiltinTool, ClawOpsAgent
from clawops.agent.plugins.openai_realtime import OpenAIRealtime

from job import load
from report import CALLS, CLOSING, FAREWELL, ending, report

MAX_CALL_SEC = 300   # 목표 60~90초. 넘으면 우리가 끊는다.

# 목소리: alloy ash ballad coral echo sage shimmer verse marin cedar
# STT/TTS를 따로 교체하는 분리형(PipelineSession)은 CLAWOPS_PHONE_WORKFLOW.txt §10 참고.
VOICE = "marin"


def facts(job: dict) -> str:
    """[사실] 블록. guidance 가 말할 내용을 **전부** 들고 온다.

    예전에는 guidance 와 shelter 를 따로 받아 각각 한 줄씩 만들었는데, 연결 계층이
    이미 plan.actionGuidance / plan.shelterRecommendationText 로 문장을 완성해서 준다.
    여기서 또 조립하면 같은 사실이 두 문장으로 나뉘어 어르신이 두 번 듣게 된다.
    """
    lines = [f"- {k}: {v}" for k, v in (job.get("guidance") or {}).items()
             if isinstance(v, str) and v.strip()]
    if not lines:
        raise ValueError("guidance 에 안내할 내용이 없다 — 발신 중단")
    return "\n".join(lines)


def prompt(job: dict) -> str:
    """job 마다 새로 만든다. 한 프로세스가 여러 건을 처리하므로 전역이면 안 된다."""
    return f"""너는 '안심온' AI 안부확인 상담원이다. 상대는 고령의 어르신이다.

첫 문장: "안녕하세요. 안심온 AI 안부확인 서비스입니다.
현재 폭염 위험이 높아 안전 확인과 예방 안내를 위해 연락드렸습니다."

말하기 규칙
- 짧고 느린 한국어. 한 번에 질문 하나만.
- 아래 [사실] 밖의 숫자·주소·시간을 절대 만들지 않는다.
- 의료 진단을 하지 않는다. 긴급 증상을 말씀하시면 남은 질문을 건너뛰고
  아래 [마무리] 의 2) 부터 그대로 진행한다.

반복 금지 (매우 중요)
- 답을 들으면 **되읽지 말고 바로 다음 질문으로 넘어간다.** 확인은 마지막에 한 번만 한다.
  같은 말을 두 번 들으시면 통화가 길어지고 헷갈리신다.
- 안내와 질문은 각각 한 번씩만 말한다. 어르신이 다시 여쭤보실 때만 반복한다.
- "잠시만요", "정리해서 말씀드릴게요" 같은 예고를 하지 않는다. 할 말은 바로 한다.
- 못 알아들으시면 한 번만 쉬운 말로 다시 여쭙고, 두 번째도 불명확하면 넘어간다.

답 해석
- 어르신의 답을 반대로 바꾸지 않는다. "네 있어요" 는 가능하다는 뜻이다.
- 정정하시면 정정한 내용을 최종 답으로 삼는다.

[마무리]
- 통화를 끝내는 유일한 방법은 end_call 함수를 호출하는 것이다.
- 아래를 모두 마친 뒤에만 호출한다 (긴급 상황이면 1) 을 생략한다).
    1) 아래 질문의 답을 모두 듣는다
    2) 들은 답을 **한 문장으로** 정리해 확인한다 (이때가 유일한 확인이다)
    3) 다음 문구를 토씨 하나 틀리지 않고 그대로 말한다: "{CLOSING}"
- 3) 을 말하기 전에 부르면 거부된다. 거부되면 끊지 말고 3) 을 말한 뒤 다시 호출한다.

[사실]  ← 이 값들만 말한다. 연결 계층이 확정한 내용이다.
{facts(job)}

순서: 통화 가능한지 여쭙기(되읽지 않는다) → 위 사실을 한 번에 안내 → 아래 질문을 하나씩
""" + "\n".join(f"{i}. {q}" for i, q in enumerate(job["questions"], 1)) + """
→ 들은 답을 한 문장으로 정리해 확인 → 마무리 인사 → end_call 호출.
"""


def mask(number: str) -> str:
    """로그용 마스킹 — 뒤 4자리만 남긴다 (워크플로우 §6)."""
    return "*" * max(len(number) - 4, 0) + number[-4:]


def from_number() -> str:
    # .env 의 이름과 맞춘다 (CLAWOPS_API_KEY / CLAWOPS_ACCOUNT_ID / CLAWOPS_NUMBER).
    # 예전 이름 CLAWOPS_FROM_NUMBER 를 읽던 탓에 값이 있어도 못 찾고
    # numbers.list()[0] 로 조용히 넘어가, 의도하지 않은 번호로 나갈 수 있었다.
    if n := os.getenv("CLAWOPS_NUMBER"):
        return n
    owned = list(ClawOps().numbers.list())
    if not owned:
        sys.exit("보유한 070 번호가 없습니다: python scripts/provision_number.py --create")
    return owned[0].number


async def main(job: dict, to: str) -> dict:
    agent = ClawOpsAgent(
        from_=from_number(),
        session=OpenAIRealtime(system_prompt=prompt(
            job), language="ko", voice=VOICE),
        machine_detection="Enable",  # 자동응답기 → NO_ANSWER
        recording=False,             # 워크플로우 §6: 녹취 미저장
        # SDK 기본 hang_up 은 설명이 "대화가 끝나면 끊어라" 라 제약이 안 걸린다.
        # 대신 아래 end_call 을 직접 등록하고 통과 조건을 코드로 검사한다.
        builtin_tools=BuiltinTool.NONE,
    )
    turns: list[dict] = []
    end_reason: str | None = None
    call = None          # end_call 이 연결 직후(prewarm 중)에 불릴 수 있다
    refused = False

    # agent 레벨에 등록해야 한다. CallSession은 agent.call() 안에서 만들어지면서
    # 곧바로 prewarm이 시작되므로, 반환값에 거는 방식은 초반 발화를 놓친다.
    @agent.on("transcript")
    async def _(_session, role: str, text: str) -> None:
        """STT — Realtime이 양쪽 발화를 실시간으로 준다. 녹음 불필요."""
        print(f"  {'어르신' if role == 'user' else 'AI    '} │ {text}", flush=True)
        turns.append({"role": role, "text": text})

    def said_farewell() -> bool:
        """공백을 무시하고 대조한다. TTS 전사가 '안녕히계세요' 로 붙여 오면
        글자 그대로 비교하는 순간 영원히 통과하지 못한다."""
        spoken = "".join(t["text"] for t in turns if t["role"] == "assistant")
        return FAREWELL.replace(" ", "") in spoken.replace(" ", "")

    @agent.tool
    async def end_call() -> str:
        """통화를 종료한다. 마무리 인사를 마친 뒤에만 호출할 것."""
        nonlocal refused
        # 게이트는 프롬프트가 아니라 실제 전사로 판정한다. 다만 전사는 비동기로 도착해서
        # 모델이 인사와 **동시에** 이 함수를 부르면 아직 turns 에 없다.
        # 그때마다 거부하면 인사만 반복하다 MAX_CALL_SEC 까지 안 끊긴다(실제로 그랬다).
        # 그래서 한 번 기다려 보고, 그래도 없으면 거부는 딱 한 번까지만 한다.
        if not said_farewell():
            await asyncio.sleep(1.2)
        if not said_farewell() and not refused:
            refused = True
            print("  · end_call 거부 1회 (마무리 인사 전사 미확인)", flush=True)
            return (f"아직 마무리 인사를 하지 않았습니다. 들은 답을 정리해 확인하고 "
                    f"'{CLOSING}' 라고 말한 뒤 다시 호출하세요.")
        if call is None:
            return "아직 통화가 연결되지 않았습니다. 잠시 뒤 다시 호출하세요."
        print("  · end_call 승인", flush=True)
        await call.hangup()
        return "통화를 종료했습니다."

    print(f"발신 → {mask(to)}\n──── 통화 내용 ────", flush=True)
    try:
        call = await agent.call(to, timeout=60)  # connect()는 내부에서 자동 수행
        try:
            await asyncio.wait_for(call.wait(), timeout=MAX_CALL_SEC)
        except asyncio.TimeoutError:
            print(f"  ! {MAX_CALL_SEC}초 초과 — 이쪽에서 종료", flush=True)
            await call.hangup()
        m = call.metrics  # duration·metrics는 메서드가 아니라 property
        end_reason = m.end_reason
        print(f"──────────────────\n종료 · {call.duration:.0f}초 · 사유 {m.end_reason}"
              f" · 첫 응답 {m.first_response_ms}ms · 끼어들기 {m.barge_in_count}회")
    finally:
        await agent.disconnect()
        if not turns:
            print("\n말이 하나도 오가지 않았습니다. 위 로그에서 다음을 확인하세요:\n"
                  "  · 'OpenAI Realtime connected' 가 있는가 → 없으면 OpenAI 연결 실패\n"
                  "  · 'PREWARM-T failed' / 'invalid_api_key' → 키·크레딧 문제\n"
                  "  진단: python scripts/check_openai.py", flush=True)
        if turns:  # ponytail: PoC용 로컬 저장. DB 에는 전사를 넣지 않는다
            CALLS.mkdir(exist_ok=True)
            out = CALLS / f"{to}_{datetime.now():%Y%m%d_%H%M%S}.json"
            out.write_text(json.dumps(turns, ensure_ascii=False,
                           indent=2), encoding="utf-8")
            print(f"대화 {len(turns)}턴 → {out.name}")

    r = await report(turns, job, provider_call_id=call.call_id, end_reason=end_reason)
    print(f"\n판정 · 쉼터의향 {r['shelter_intent']} · 혼자이동 {r['can_move_alone']}"
          f" · 도움필요 {r['help_needed']} · 증상언급 {r['symptom_mentioned']}")
    print(f"종료유형 · {ending(turns, end_reason)}")
    print(f"요약 · {r['summary']}")
    return r


def setup() -> None:
    """SDK 내부 로그를 보이게 한다. 이게 없으면 OpenAI Realtime 연결 실패가
    조용히 넘어가서 '전화는 되는데 말을 안 한다' 로만 보인다."""
    logging.basicConfig(level=logging.WARNING,
                        format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("clawops").setLevel(logging.INFO)
    load_dotenv()


if __name__ == "__main__":
    assert mask("01012345678") == "*******5678"
    # 공백만 다른 전사도 인사로 인정돼야 한다 (안 그러면 end_call 이 영원히 거부된다)
    _t = [{"role": "assistant", "text": "담당 사회복지사에게 전달하겠습니다. 안녕히계세요"}]
    assert FAREWELL.replace(" ", "") in "".join(
        x["text"] for x in _t).replace(" ", ""), "공백 무시 대조가 깨졌다"
    # 게이트(FAREWELL)와 지시 문구(CLOSING)가 어긋나면 end_call 이 영원히 거부된다.
    # 한쪽만 고치는 사고를 여기서 잡는다.
    assert FAREWELL in CLOSING, f"{FAREWELL!r} 가 {CLOSING!r} 안에 없다"
    assert CLOSING in prompt(load()), "프롬프트에 CLOSING 이 안 들어갔다"
    setup()
    JOB = load()
    # 번호는 인자 우선, 없으면 job 의 to_number (DB 가 아닌 별도 보관소 값)
    to = sys.argv[1] if len(sys.argv) > 1 else JOB.get("to_number")
    if not to:
        sys.exit("사용법: python voice/call.py 01012345678")
    asyncio.run(main(JOB, to))
