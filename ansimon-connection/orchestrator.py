# -*- coding: utf-8 -*-
"""안심온 엔드투엔드 오케스트레이터.

    (elderly, location, risk)
        │
        ├─ contracts.parse_request     동의 확인 · 위험도 0~1 · 지역별 쉼터 가용 판정
        │
        ├─ rag_client  ──▶ rag(:8000)  쉼터(TMAP) → 안내문(LLM) → 근거검증
        │
        ├─ questions                   물을 항목은 코드가, 문장은 LLM 이
        │
        ├─ phone_client ──▶ voice(:9000)   발신 (202 즉시 반환)
        ◀── deliver()                  통화 결과 콜백 + 요약
        │
        └─ contracts.build_result ──▶ 백엔드 POST /internal/v1/contact/results

전화번호는 여기서 두 번만 쓰인다: 발신 job 에 넣을 때, 마스킹해서 로그에 찍을 때.
결과 payload 에는 들어가지 않는다.
"""
from __future__ import annotations

import asyncio
import os
from typing import Optional

import backend_client
import contracts
import phone_client
import questions as questions_mod
import rag_client


def _env(name: str, default: str = "") -> str:
    """.env 값에 앞뒤 공백이나 인라인 주석이 섞여도 URL 이 깨지지 않게 한 번 씻는다."""
    return (os.getenv(name) or default).split("#")[0].strip()


# 통화 결과를 받을 주소. **job 에 실어서 보낸다** — 발신을 지시한 쪽이 받을 곳도 안다.
CALLBACK_BASE = (_env("CONNECTION_CALLBACK_URL")
                 or f"http://localhost:{_env('CONNECTION_PORT', '7000')}").rstrip("/")
CALL_RESULT_TIMEOUT = int(_env("CALL_RESULT_TIMEOUT_SEC", "300"))

# contact_job_id -> 통화 결과를 기다리는 Future. 콜백이 여기에 결과를 꽂는다.
# ponytail: 프로세스 메모리. 서버를 여러 대로 늘리면 Redis 로 올려야 한다.
PENDING: dict[int, asyncio.Future] = {}


class Blocked(RuntimeError):
    """전화를 걸지 않았다. result 에 사유가 담겨 있다."""

    def __init__(self, result: dict):
        self.result = result
        super().__init__(result.get("reason") or "blocked")


def deliver(contact_job_id: int, observation: dict, meta: dict) -> bool:
    """voice/report.py 가 보낸 통화 결과를 기다리던 실행에 꽂는다."""
    fut = PENDING.pop(contact_job_id, None)
    if fut and not fut.done():
        fut.set_result((observation, meta))
        return True
    return False


def _blocked(reason: str, code: str, **extra) -> dict:
    return {"status": "BLOCKED", "code": code, "reason": reason, "result": None, **extra}


async def run(payload: dict) -> dict:
    """입력 한 건 → 백엔드 payload. 반환 dict 의 `result` 가 실제로 보내는 본문이다."""
    req = contracts.parse_request(payload)          # ConsentError / ContractError
    warnings: list[str] = req.pop("warnings")
    elderly_id = req["elderly_id"]
    if req["selection_reasons"]:
        warnings.append("규칙 기반 선정 사유: " + " / ".join(req["selection_reasons"]))

    # --- 1. RAG: 쉼터 + 안내문 + 근거검증 -------------------------------------
    # 이름·전화·주소는 보내지 않는다. LLM 이 알 필요가 없고, 알면 새어나갈 수 있다.
    profile = {"targetAudience": req["target_audience"], "age": req["age"],
               "healthNote": req["health_note"],
               "latitude": req["latitude"], "longitude": req["longitude"]}
    risk = {"riskLevel": req["risk_level"], "riskScore": req["risk_score"],
            "riskFactors": req["top_factors"]}
    # 쉼터 데이터가 없는 지역이면 조회 자체를 건너뛴다 (contracts.has_shelter_data).
    use_shelter = req["shelter_available"] and req["latitude"] is not None
    try:
        plan = await rag_client.create_intervention_plan(
            elderly_id, req["risk_snapshot_id"] or 0, profile, risk,
            latitude=req["latitude"] if use_shelter else None,
            longitude=req["longitude"] if use_shelter else None,
            weather=req["weather"], auto_shelter=use_shelter)
    except rag_client.GuidanceBlocked as e:
        # 근거 검증 실패는 재시도 대상이 아니다. 사람이 봐야 한다.
        raise Blocked(_blocked(str(e), "GUIDANCE_GENERATION_BLOCKED",
                               issues=e.issues, warnings=warnings))
    warnings += list(plan.get("warnings") or [])
    if plan.get("modelUsed") == "mock-deterministic-v1":
        warnings.append("안내문이 mock 생성기로 만들어졌습니다(LLM 미연결). 시연 전 확인하세요.")

    shelter_rec = plan.get("recommendedShelter") if use_shelter else None

    # --- 2. 통화에 넣을 문장 ------------------------------------------------
    window = contracts.korean_window(req["peak_start_at"] or req["target_start_at"],
                                     req["peak_end_at"] or req["target_end_at"])
    guidance = contracts.action_guidance(
        window, [s.get("text", "") for s in plan.get("guidanceSentences") or []],
        plan.get("emergencyMessage") if plan.get("emergencyFlag") else None)
    shelter_text = contracts.shelter_recommendation_text(shelter_rec)
    docs = contracts.document_ids(
        [c for s in plan.get("guidanceSentences") or [] for c in s.get("evidenceChunkIds") or []])

    slots = questions_mod.choose_slots(shelter_rec, req["risk_level"])
    qs, qw = await questions_mod.generate(
        slots, req["risk_level"], shelter_rec.get("name") if shelter_rec else None)
    warnings += qw
    question_texts = [q["text"] for q in qs]

    # --- 3. 발신 job -------------------------------------------------------
    key = f"{elderly_id}:{req['risk_snapshot_id'] or stable_key(req)}:HEAT_PREVENTION_CALL"[:160]
    job_id = contracts.stable_id("job", key)
    facts = {"안내": guidance}
    if shelter_text:
        facts["쉼터"] = shelter_text
    call_job = {
        "contact_job_id": job_id,
        "elderly_id": elderly_id,
        "attempt_count": 1,
        "idempotency_key": key,
        "to_number": req["phone"],            # 결과 payload 로 가지 않는다
        "callback_url": CALLBACK_BASE,
        "guidance": facts,
        "questions": question_texts,
    }

    if req["dry_run"]:
        warnings.append("dryRun — 실제로 전화를 걸지 않았습니다.")
        return {"status": "DRY_RUN", "result": None, "warnings": warnings,
                "call_job_preview": {**call_job,
                                     "to_number": phone_client.mask(req["phone"])}}

    # --- 4. 발신 + 결과 대기 ------------------------------------------------
    loop = asyncio.get_running_loop()
    fut: asyncio.Future = loop.create_future()
    PENDING[job_id] = fut
    try:
        await phone_client.dispatch(call_job)
        print(f"[connection] 발신 접수 job={job_id} → {phone_client.mask(req['phone'])}", flush=True)
        observation, meta = await asyncio.wait_for(fut, timeout=CALL_RESULT_TIMEOUT)
    except phone_client.PhoneDispatchError as e:
        PENDING.pop(job_id, None)
        raise Blocked(_blocked(str(e), "PHONE_DISPATCH_FAILED", warnings=warnings))
    except asyncio.TimeoutError:
        PENDING.pop(job_id, None)
        warnings.append(f"{CALL_RESULT_TIMEOUT}초 안에 통화 결과 콜백이 오지 않았습니다 "
                        f"(기다린 주소: {CALLBACK_BASE}).")
        observation = {"summary": "[통화 결과를 전달받지 못했습니다] 전화 모듈의 콜백이 "
                                  "도착하지 않아 결과를 확인할 수 없습니다."}
        meta = {"provider": "CLAWOPS", "call_ending": "NO_CALLBACK"}

    # --- 5. 백엔드 payload --------------------------------------------------
    result = contracts.build_result(elderly_id, meta.get("provider_call_id"), guidance,
                                    shelter_text, question_texts, docs, observation, meta)
    sent = await backend_client.post_result(result, f"{key}:{call_job['attempt_count']}")
    return {"status": "COMPLETED" if result["call"]["answered"] else "NOT_ANSWERED",
            "result": result, "backendResponse": sent,
            "callEnding": meta.get("call_ending"), "warnings": warnings}


def stable_key(req: dict) -> int:
    """risk_snapshot_id 가 없을 때 위험시간대로 대신 만든다 (같은 시간대면 같은 값)."""
    return contracts.stable_id("risk", req["region_code"], req["risk_level"],
                               req["target_start_at"], req["target_end_at"])
