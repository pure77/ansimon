# -*- coding: utf-8 -*-
"""오프라인 통합 테스트 — 외부 API 없이 전 구간을 돈다.

    python test_connection.py

RAG(:8000)·전화(:9000)·백엔드·LLM 을 전부 가짜로 갈아끼우고 파이프라인을 실제로 한 바퀴
돌린다. 네트워크가 없어도, 키가 없어도 전부 통과해야 한다.
가짜는 반드시 원복한다 — 안 하면 이후 테스트가 가짜를 쓰면서 통과해 오진이 난다.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import os
import sys
from datetime import datetime, timedelta

os.environ.setdefault("ALAN_API_KEY", "")          # 질문 생성은 템플릿 경로로
os.environ.setdefault("CALL_RESULT_TIMEOUT_SEC", "3")
os.environ.pop("ANSIMON_BACKEND_BASE_URL", None)   # 백엔드 전송은 출력만

import backend_client
import contracts
import orchestrator
import phone_client
import questions as Q
import rag_client

PASS, FAIL = [], []


def t(name):
    def deco(fn):
        try:
            fn(); PASS.append(name)
        except Exception as e:
            FAIL.append(f"{name}: {type(e).__name__}: {e}")
        return fn
    return deco


def at(name):
    def deco(fn):
        try:
            asyncio.run(fn()); PASS.append(name)
        except Exception as e:
            FAIL.append(f"{name}: {type(e).__name__}: {e}")
        return fn
    return deco


KST = contracts.KST
BASE = datetime.now(KST).replace(minute=0, second=0, microsecond=0)


def payload(**over) -> dict:
    start = BASE.replace(hour=13)
    p = {
        "elderly": {"id": 1, "name": "김안심", "phone": "010-1234-5678", "age": 78,
                    "healthNote": "고혈압, 거동 다소 불편", "regionCode": "1114000000",
                    "consentStatus": "AGREED"},
        "location": {"latitude": 37.5665, "longitude": 126.9780},
        "risk": {"id": 7, "score": 82.5, "level": "HIGH",
                 "targetStartAt": start.isoformat(),
                 "targetEndAt": (start + timedelta(hours=4)).isoformat(),
                 "peakStartAt": (start + timedelta(hours=1)).isoformat(),
                 "peakEndAt": (start + timedelta(hours=3)).isoformat(),
                 "topFactors": ["독거"]},
    }
    for k, v in over.items():
        p[k] = {**p[k], **v} if isinstance(v, dict) and isinstance(p.get(k), dict) else v
    return p


SHELTER = {"name": "종로노인종합복지관 경로당", "address": "서울 종로구 삼봉로 71",
           "lat": 37.5701, "lon": 126.9820, "source": "SEOUL_OPENAPI",
           "walkMinutes": 8, "routeSource": "TMAP", "openStatus": "OPEN",
           "needsReview": False, "route": [], "distanceM": 480.0}

PLAN = {"riskLevel": "HIGH", "guidanceSentences": [
            {"text": "시원한 실내에 머물러 주세요.", "evidenceChunkIds": ["heat_manual_v1__0006"]},
            {"text": "물을 조금씩 자주 드세요.", "evidenceChunkIds": ["heat_manual_v1__0013"]}],
        "recommendedShelter": SHELTER, "emergencyFlag": False, "emergencyMessage": None,
        "modelUsed": "alan-v1", "warnings": []}

ANSWERED = {"contact_status": "ANSWERED", "shelter_intent": "YES", "can_move_alone": "NO",
            "help_needed": "YES", "symptom_mentioned": "UNKNOWN", "confidence": 0.91,
            "summary": "쉼터에 가실 의향은 있으나 혼자 이동이 어렵다고 하십니다.",
            "ended_at": "2026-08-19T11:30:00.000000"}
META = {"provider": "CLAWOPS", "call_ending": "COMPLETED", "provider_call_id": "CA_test_1"}


@contextlib.contextmanager
def fake_backends(plan=None, dispatch_ok=True, observation=None, meta=None, spy=None):
    real_rag, real_dispatch = rag_client.create_intervention_plan, phone_client.dispatch
    seen = {}

    async def _rag(*a, **k):
        seen["rag"] = k
        return json.loads(json.dumps(plan if plan is not None else PLAN))

    async def _dispatch(job):
        seen["job"] = job
        if spy is not None:
            spy.update(job)
        if not dispatch_ok:
            raise phone_client.PhoneDispatchError("발신 거부: already_calling")
        if observation is not None:
            asyncio.get_running_loop().create_task(_cb(job))
        return {"contact_job_id": job["contact_job_id"], "accepted": True}

    async def _cb(job):
        await asyncio.sleep(0)
        orchestrator.deliver(job["contact_job_id"], observation, meta or META)

    rag_client.create_intervention_plan, phone_client.dispatch = _rag, _dispatch
    try:
        yield seen
    finally:
        rag_client.create_intervention_plan = real_rag
        phone_client.dispatch = real_dispatch


# ── 입력 검증 ────────────────────────────────────────────────────────────────

@t("risk score 82.5 를 0.825 로 환산한다")
def _():
    r = contracts.parse_request(payload())
    assert r["risk_score"] == 0.825 and any("환산" in w for w in r["warnings"])


@t("이미 0~1 인 값은 건드리지 않고, 100 초과는 1.0 으로 자른다")
def _():
    assert contracts.parse_request(payload(risk={"score": 0.83}))["risk_score"] == 0.83
    assert contracts.parse_request(payload(risk={"score": 250}))["risk_score"] == 1.0


@t("elderly.id 가 없으면 막는다 (결과를 어느 대상자에 붙일지 모른다)")
def _():
    p = payload(); p["elderly"].pop("id")
    try:
        contracts.parse_request(p); raise AssertionError("ContractError 가 나야 한다")
    except contracts.ContractError as e:
        assert "elderly.id" in str(e)


@t("동의 상태가 아니면 전화를 만들지 않는다")
def _():
    for v in (None, "REVOKED"):
        try:
            contracts.parse_request(payload(elderly={"consentStatus": v}))
            raise AssertionError("ConsentError 가 나야 한다")
        except contracts.ConsentError:
            pass


@t("peak 은 한쪽만 올 수 없고, start >= end 는 막는다")
def _():
    p = payload(); p["risk"].pop("peakEndAt")
    for bad in (p, payload(risk={"targetEndAt": BASE.replace(hour=13).isoformat()})):
        try:
            contracts.parse_request(bad); raise AssertionError("ContractError 가 나야 한다")
        except contracts.ContractError:
            pass


@t("위경도 범위·risk.level enum·전화번호 유무를 막는다")
def _():
    for bad in (payload(location={"latitude": 91.0, "longitude": 126.9}),
                payload(risk={"level": "VERY_HIGH"}),
                payload(elderly={"phone": ""})):
        try:
            contracts.parse_request(bad); raise AssertionError("ContractError 가 나야 한다")
        except contracts.ContractError:
            pass


@t("건강 메모에서 규칙 기반으로 대상군을 뽑는다")
def _():
    tags, reasons = contracts.audience_from_note("고혈압, 거동 다소 불편")
    assert tags == ["ELDERLY", "BLOOD_PRESSURE", "DISABLED"] and len(reasons) == 2


# ── 지역별 쉼터 데이터 ────────────────────────────────────────────────────────

@t("서울(11…) 만 공공 쉼터 데이터가 있다")
def _():
    assert contracts.has_shelter_data("1114000000")
    assert not contracts.has_shelter_data("2600000000")   # 부산
    assert not contracts.has_shelter_data(None)


@t("쉼터 데이터가 없는 지역이면 경고를 남긴다")
def _():
    r = contracts.parse_request(payload(elderly={"regionCode": "2600000000"}))
    assert r["shelter_available"] is False
    assert any("쉼터" in w and "제외" in w for w in r["warnings"])


@at("서울 밖이면 쉼터를 조회하지도, 통화에서 묻지도 않는다")
async def _():
    with fake_backends(observation=ANSWERED) as seen:
        r = await orchestrator.run(payload(elderly={"regionCode": "2600000000"}))
    assert seen["rag"]["auto_shelter"] is False and seen["rag"]["latitude"] is None
    plan = r["result"]["plan"]
    assert plan["shelterRecommendationText"] is None
    assert not any("쉼터" in q for q in plan["callQuestionOrder"]), plan["callQuestionOrder"]


@at("서울이면 쉼터를 조회하고 통화에 넣는다")
async def _():
    with fake_backends(observation=ANSWERED) as seen:
        r = await orchestrator.run(payload())
    assert seen["rag"]["auto_shelter"] is True
    assert "종로노인종합복지관 경로당" in r["result"]["plan"]["shelterRecommendationText"]


# ── 백엔드 계약 ──────────────────────────────────────────────────────────────

@at("결과가 POST /internal/v1/contact/results 계약과 정확히 같다")
async def _():
    with fake_backends(observation=ANSWERED) as seen:
        r = await orchestrator.run(payload())
    res = r["result"]
    assert set(res) == {"elderlyId", "externalCallId", "plan", "call"}, set(res)
    assert set(res["plan"]) == {"actionGuidance", "shelterRecommendationText",
                                "callQuestionOrder", "evidenceDocumentIds"}
    assert set(res["call"]) == {"answered", "summary", "shelterIntent", "canMoveAlone",
                                "helpNeeded", "symptomMentioned", "confidence",
                                "transcriptRef", "endedAt"}
    assert res["elderlyId"] == 1 and res["externalCallId"] == "CA_test_1"
    assert res["call"]["answered"] is True and res["call"]["confidence"] == 0.91
    assert res["call"]["shelterIntent"] == "YES" and res["call"]["canMoveAlone"] == "NO"


@t("evidenceDocumentIds 는 청크 id 가 아니라 문서 id 다 (중복 제거)")
def _():
    got = contracts.document_ids(["heat_manual_v1__0006", "heat_manual_v1__0013",
                                  "kma_guide_2024__0001"])
    assert got == ["heat_manual_v1", "kma_guide_2024"], got


@t("endedAt 은 UTC ISO + Z 다")
def _():
    d = contracts.dt("2026-08-19T11:30:00", "x")            # KST 로 해석
    assert contracts.utc_iso(d) == "2026-08-19T02:30:00Z", contracts.utc_iso(d)


@t("transcriptRef 는 참조값만. 전사 원문을 담지 않는다")
def _():
    ref = contracts.transcript_ref("CLAWOPS", "CA_9", contracts.dt("2026-08-19T11:00:00", "x"))
    assert ref == "clawops/2026/08/19/CA_9", ref
    assert contracts.transcript_ref("CLAWOPS", None) is None


@t("answered 는 받으셨는가다 — 중간에 끊으셔도 받으신 것")
def _():
    mk = lambda ending: contracts.build_result(
        1, "c", "g", None, [], [], {"summary": "s"}, {"call_ending": ending})["call"]["answered"]
    assert mk("COMPLETED") is True and mk("USER_HUNG_UP_EARLY") is True
    assert mk("TIMEOUT") is True
    assert mk("NO_ANSWER") is False and mk("ERROR") is False and mk("NO_CALLBACK") is False


@t("summary 는 1000자로 자르고, 모르는 답은 UNKNOWN 으로 둔다")
def _():
    c = contracts.build_result(1, "c", "g", None, [], [],
                               {"summary": "가" * 1500, "shelter_intent": "maybe"},
                               {"call_ending": "COMPLETED"})["call"]
    assert len(c["summary"]) == 1000 and c["shelterIntent"] == "UNKNOWN"


@at("결과 payload 어디에도 전화번호가 없다")
async def _():
    with fake_backends(observation=ANSWERED) as seen:
        r = await orchestrator.run(payload())
    assert "01012345678" not in json.dumps(r["result"], ensure_ascii=False)
    assert seen["job"]["to_number"] == "01012345678"        # 발신 job 에만 있다


@at("RAG 로 이름·전화·주소를 보내지 않는다")
async def _():
    with fake_backends(observation=ANSWERED) as seen:
        await orchestrator.run(payload())
    blob = json.dumps(seen["rag"], ensure_ascii=False)
    assert "01012345678" not in blob and "김안심" not in blob


# ── 통화 문장 ────────────────────────────────────────────────────────────────

@t("actionGuidance 는 위험시간대 + 안내문장 한 덩어리다")
def _():
    g = contracts.action_guidance("오늘 낮 한 시부터 세 시까지",
                                  ["물을 자주 드세요.", "실내에 머무르세요."])
    assert g.startswith("오늘 낮 한 시부터 세 시까지 더위가 가장 심합니다.")
    assert "물을 자주 드세요." in g and "실내에 머무르세요." in g


@t("응급 안내가 있으면 맨 앞에 온다")
def _():
    g = contracts.action_guidance("오늘 낮 한 시부터 세 시까지", ["물을 드세요."], "즉시 119에 신고하세요.")
    assert g.startswith("즉시 119에 신고하세요.")


@t("시간창이 없으면 시간 문구를 지어내지 않는다")
def _():
    assert contracts.korean_window(None, None) is None
    assert contracts.action_guidance(None, ["물을 드세요."]) == "물을 드세요."


@t("한국어 시각은 '오늘 낮 한 시부터 세 시까지' 형태다")
def _():
    got = contracts.korean_window(BASE.replace(hour=13), BASE.replace(hour=15))
    assert got == "오늘 낮 한 시부터 세 시까지", got


@t("직선거리 폴백이면 도보 시간을 말하지 않는다")
def _():
    fb = {**SHELTER, "routeSource": "STRAIGHT_LINE_FALLBACK", "walkMinutes": None,
          "estimatedWalkMinutes": 12}
    text = contracts.shelter_recommendation_text(fb)
    assert "분" not in text and "종로노인종합복지관 경로당" in text, text
    assert "8분" in contracts.shelter_recommendation_text(SHELTER)


@t("쉼터가 없으면 쉼터 문장을 만들지 않는다")
def _():
    assert contracts.shelter_recommendation_text(None) is None
    assert contracts.shelter_recommendation_text({"name": ""}) is None


@t("쉼터 유무·위험등급에 따라 물을 항목이 달라진다")
def _():
    assert Q.choose_slots(None, "HIGH") == ["help_needed"]
    assert Q.choose_slots(SHELTER, "HIGH") == ["shelter_intent", "can_move_alone", "help_needed"]
    assert "symptom_mentioned" in Q.choose_slots(SHELTER, "CRITICAL")


@t("숫자가 섞인 LLM 질문은 거부한다 (안내하지 않은 값을 말하게 된다)")
def _():
    assert Q._valid("쉼터에 가실 의향이 있으신가요?")
    assert not Q._valid("3분 거리 쉼터에 가실 수 있으신가요?")
    assert not Q._valid("쉼터 가세요") and not Q._valid("")


@at("LLM 키가 없으면 템플릿으로 만들고 그 사실을 경고한다")
async def _():
    qs, w = await Q.generate(["shelter_intent", "help_needed"], "HIGH", "OO쉼터")
    assert [q["slot"] for q in qs] == ["shelter_intent", "help_needed"]
    assert all(q["text"] for q in qs) and any("ALAN_API_KEY" in x for x in w)


@at("전화에 넘기는 job 이 voice/job.py 의 필수 항목을 다 갖춘다")
async def _():
    # voice/ 는 필요한 순간에만 경로에 넣는다. 전역에 넣으면 `import server` 가
    # voice/server.py 로 잡혀 clawops 까지 끌려온다 (양쪽에 server.py 가 있다).
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent / "voice"))
    try:
        from job import REQUIRED, check
    finally:
        sys.path.pop(0)
    spy = {}
    with fake_backends(observation=ANSWERED, spy=spy):
        await orchestrator.run(payload())
    check(spy)                                   # 진짜 검증기
    assert not [k for k in REQUIRED if k not in spy]
    assert spy["callback_url"] == orchestrator.CALLBACK_BASE
    assert all(isinstance(v, str) and v for v in spy["guidance"].values())
    assert all(isinstance(q, str) for q in spy["questions"])
    # 안내와 쉼터 문장이 각각 한 번씩만 있어야 한다 (어르신이 두 번 듣지 않게)
    assert list(spy["guidance"]) == ["안내", "쉼터"], spy["guidance"].keys()


# ── 흐름 ────────────────────────────────────────────────────────────────────

@at("근거 검증에서 막히면 전화를 걸지 않는다")
async def _():
    real = rag_client.create_intervention_plan
    called = []

    async def boom(*a, **k):
        raise rag_client.GuidanceBlocked("쉼터 실존 확인 실패", [{"level": "ERROR", "code": "X"}])

    with fake_backends():
        rag_client.create_intervention_plan = boom
        phone_client.dispatch = lambda j: called.append(j)
        try:
            await orchestrator.run(payload()); raise AssertionError("Blocked 가 나야 한다")
        except orchestrator.Blocked as e:
            assert e.result["code"] == "GUIDANCE_GENERATION_BLOCKED" and e.result["result"] is None
        finally:
            rag_client.create_intervention_plan = real
    assert not called, "전화를 걸면 안 된다"


@at("콜백이 오지 않으면 결과를 지어내지 않는다")
async def _():
    with fake_backends(observation=None):
        r = await orchestrator.run(payload())
    call = r["result"]["call"]
    assert call["answered"] is False and call["shelterIntent"] == "UNKNOWN"
    assert "전달받지 못했습니다" in call["summary"] and call["confidence"] == 0.0
    assert any("콜백이 오지 않았습니다" in w for w in r["warnings"])


@at("발신 접수가 거부되면 전화를 걸지 않고 사유를 올린다")
async def _():
    with fake_backends(dispatch_ok=False):
        try:
            await orchestrator.run(payload()); raise AssertionError("Blocked 가 나야 한다")
        except orchestrator.Blocked as e:
            assert e.result["code"] == "PHONE_DISPATCH_FAILED"


@at("dryRun 은 전화를 걸지 않고 보낼 내용만 보여준다")
async def _():
    called = []
    with fake_backends():
        phone_client.dispatch = lambda j: called.append(j)
        r = await orchestrator.run(payload(dryRun=True))
    assert not called and r["status"] == "DRY_RUN" and r["result"] is None
    assert r["call_job_preview"]["to_number"] == "*******5678"


@at("기다리는 사람이 없는 콜백은 조용히 False 를 준다")
async def _():
    assert orchestrator.deliver(99999, ANSWERED, META) is False


@at("mock 안내문이면 시연 전에 알아채도록 경고한다")
async def _():
    with fake_backends(plan={**PLAN, "modelUsed": "mock-deterministic-v1"}, observation=ANSWERED):
        r = await orchestrator.run(payload())
    assert any("mock" in w for w in r["warnings"])


@at("입력이 다르면 멱등키가 다르고, 같으면 같다")
async def _():
    with fake_backends(observation=ANSWERED) as s1:
        await orchestrator.run(payload())
        a = s1["job"]["idempotency_key"]
    with fake_backends(observation=ANSWERED) as s2:
        await orchestrator.run(payload(elderly={"id": 2, "phone": "010-9999-8888"}))
        b = s2["job"]["idempotency_key"]
    with fake_backends(observation=ANSWERED) as s3:
        await orchestrator.run(payload())
        c = s3["job"]["idempotency_key"]
    assert a != b and a == c


@at("백엔드 주소가 없으면 전송하지 않고 본문만 출력한다")
async def _():
    assert backend_client.base_url() == ""
    assert await backend_client.post_result({"x": 1}) is None


@t("샘플 입력 5종이 의도대로 동작한다 (05_no_consent 는 막혀야 정상)")
def _():
    import glob
    import run_demo
    found = sorted(glob.glob(str(run_demo.SAMPLES / "*.json")))
    assert len(found) >= 5, found
    for path in found:
        p = run_demo.resolve_times(json.loads(open(path, encoding="utf-8").read()))
        p.pop("_설명", None)
        p.setdefault("elderly", {})["phone"] = "01012345678"
        name = os.path.basename(path)
        try:
            r = contracts.parse_request(p)
            assert "no_consent" not in name, f"{name} 은 막혀야 한다"
            assert 0.0 <= r["risk_score"] <= 1.0 and r["risk_level"] in contracts.RISK_LEVELS
            assert r["shelter_available"] == ("11" in str(r["region_code"] or "")[:2]), name
        except contracts.ConsentError:
            assert "no_consent" in name, f"{name} 이 동의 오류로 막혔다"


@t("샘플의 TODAY/NOW 표기가 실제 시각으로 바뀐다")
def _():
    import run_demo
    p = run_demo.resolve_times(json.loads(
        (run_demo.SAMPLES / "01_high_shelter.json").read_text(encoding="utf-8")))
    assert p["risk"]["targetStartAt"].startswith(datetime.now(KST).date().isoformat())
    assert "TODAY" not in json.dumps(p, ensure_ascii=False)


@contextlib.contextmanager
def env(**values):
    saved = dict(os.environ)
    for k, v in values.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(saved)


async def _auth_client():
    from aiohttp.test_utils import TestClient, TestServer
    import server
    return TestClient(TestServer(server.app()))


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@at("연결 서버: 백엔드가 부르는 /v1/** 는 CONNECTION_API_KEY 로만 통과한다")
async def _():
    with env(CONNECTION_API_KEY="conn-key-0000000000000000000000000000",
             ANSIMON_BACKEND_TOKEN="callback-key-000000000000000000000000"):
        async with await _auth_client() as c:
            assert (await c.get("/health")).status == 200
            assert (await c.post("/v1/care-runs", data="x")).status == 401
            assert (await c.post("/v1/care-runs", data="x", headers=bearer("wrong"))).status == 401
            r = await c.post("/v1/care-runs", data="x",
                             headers={"Authorization": "Basic conn-key-0000000000000000000000000000"})
            assert r.status == 401
            r = await c.post("/v1/care-runs", data="x",
                             headers=bearer("callback-key-000000000000000000000000"))
            assert r.status == 401, "콜백 토큰으로는 /v1 을 못 부른다"
            # 인증은 통과하고 본문 검증에서 막힌다 → 전화를 걸지 않는다
            r = await c.post("/v1/care-runs", data="x",
                             headers=bearer("conn-key-0000000000000000000000000000"))
            assert r.status == 400, r.status
            assert (await r.json())["error"]["code"] == "BAD_REQUEST"


@at("연결 서버: 전화 모듈 콜백 /internal/** 은 ANSIMON_BACKEND_TOKEN 으로만 통과한다")
async def _():
    with env(CONNECTION_API_KEY="conn-key-0000000000000000000000000000",
             ANSIMON_BACKEND_TOKEN="callback-key-000000000000000000000000"):
        async with await _auth_client() as c:
            path = "/internal/v1/contact-jobs/1/observation"
            r = await c.post(path, data="x")
            assert r.status == 401
            assert (await r.json())["error"]["code"] == "UNAUTHORIZED"
            r = await c.post(path, data="x", headers=bearer("conn-key-0000000000000000000000000000"))
            assert r.status == 401
            r = await c.post(path, data="x", headers=bearer("callback-key-000000000000000000000000"))
            assert r.status == 400, r.status


@at("연결 서버: 키가 설정되지 않으면 열어두지 않고 503 으로 막는다")
async def _():
    with env(CONNECTION_API_KEY=None, ANSIMON_BACKEND_TOKEN=None):
        async with await _auth_client() as c:
            # server import 시 load_dotenv 가 키를 다시 채울 수 있으므로 import 후에 지운다
            os.environ.pop("CONNECTION_API_KEY", None)
            os.environ.pop("ANSIMON_BACKEND_TOKEN", None)
            r = await c.post("/v1/care-runs", data="x", headers=bearer("anything"))
            assert r.status == 503
            assert (await r.json())["error"]["code"] == "AUTH_NOT_CONFIGURED"
            assert (await c.get("/health")).status == 200


@at("연결 서버: 32자 미만 키는 설정 안 된 것으로 보고 503 으로 막는다")
async def _():
    with env(CONNECTION_API_KEY="short-key", ANSIMON_BACKEND_TOKEN="callback-key-000000000000000000000000"):
        async with await _auth_client() as c:
            r = await c.post("/v1/care-runs", data="x", headers=bearer("short-key"))
            assert r.status == 503, r.status
            assert (await r.json())["error"]["code"] == "AUTH_NOT_CONFIGURED"


@at("백엔드 주소는 있는데 토큰이 없으면 보내지 않고 예외를 올린다")
async def _():
    # 127.0.0.1:9 (discard) — 실수로 전송을 시도해도 즉시 연결 거부로 끝난다
    with env(ANSIMON_BACKEND_BASE_URL="http://127.0.0.1:9", ANSIMON_BACKEND_TOKEN=None):
        try:
            await backend_client.post_result({"x": 1})
        except RuntimeError as e:
            assert "ANSIMON_BACKEND_TOKEN" in str(e), e
        else:
            raise AssertionError("토큰 없이 전송을 시도했다")


@at("백엔드 주소는 있는데 토큰이 없으면 전화를 걸기 전에 막는다")
async def _():
    called = []
    with env(ANSIMON_BACKEND_BASE_URL="http://127.0.0.1:9", ANSIMON_BACKEND_TOKEN="  "):
        with fake_backends():
            phone_client.dispatch = lambda j: called.append(j)
            try:
                await orchestrator.run(payload()); raise AssertionError("Blocked 가 나야 한다")
            except orchestrator.Blocked as e:
                assert e.result["code"] == "BACKEND_TOKEN_MISSING" and e.result["result"] is None
    assert not called, "토큰이 없는데 전화를 걸었다"


PHONE_KEY = "phone-key-0000000000000000000000000000"


def _voice_server():
    """voice/server.py 를 'voice_server' 이름으로 한 번만 읽는다 — 연결 서버 server.py 와 이름이 겹친다."""
    import importlib.util
    if "voice_server" in sys.modules:
        return sys.modules["voice_server"]
    voice_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "voice")
    if voice_dir not in sys.path:
        sys.path.append(voice_dir)   # 맨 뒤에 둔다. 앞에 두면 `import server` 가 전화 모듈을 집는다
    spec = importlib.util.spec_from_file_location("voice_server", os.path.join(voice_dir, "server.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["voice_server"] = mod
    spec.loader.exec_module(mod)
    return mod


async def _voice_client(started=None):
    """전화 모듈 테스트 클라이언트. 실제 발신(run)은 기록만 하는 가짜로 바꾼다."""
    from aiohttp.test_utils import TestClient, TestServer
    vs = _voice_server()

    async def fake_run(job, to):
        if started is not None:
            started.append((job["contact_job_id"], to))
        vs.INFLIGHT.discard(job["contact_job_id"])

    vs.run = fake_run
    return TestClient(TestServer(vs.app()))


@at("전화 모듈: /internal/v1/calls 는 PHONE_API_KEY 가 맞아야만 통과하고, 아니면 전화를 걸지 않는다")
async def _():
    started = []
    with env(PHONE_API_KEY=PHONE_KEY):
        async with await _voice_client(started) as c:
            assert (await c.get("/health")).status == 200
            r = await c.post("/internal/v1/calls", json={"contact_job_id": 1})
            assert r.status == 401, r.status
            assert (await r.json())["error"]["code"] == "UNAUTHORIZED"
            r = await c.post("/internal/v1/calls", json={},
                             headers=bearer("wrong-key-000000000000000000000000000"))
            assert r.status == 401
            r = await c.post("/internal/v1/calls", json={},
                             headers={"Authorization": f"Basic {PHONE_KEY}"})
            assert r.status == 401
            # 키가 맞으면 인증은 통과하고 본문 검증(check)에서 400 으로 막힌다
            r = await c.post("/internal/v1/calls", json={}, headers=bearer(PHONE_KEY))
            assert r.status == 400, r.status
    assert not started, "인증 실패/본문 오류인데 전화를 걸었다"


@at("전화 모듈: PHONE_API_KEY 가 없거나 32자 미만이면 503 으로 닫는다")
async def _():
    for value in (None, "short-key"):
        with env(PHONE_API_KEY=value):
            async with await _voice_client() as c:
                if value is None:
                    os.environ.pop("PHONE_API_KEY", None)   # import 시 load_dotenv 가 되살렸을 수 있다
                r = await c.post("/internal/v1/calls", json={}, headers=bearer("short-key"))
                assert r.status == 503, (value, r.status)
                assert (await r.json())["error"]["code"] == "AUTH_NOT_CONFIGURED"
                assert (await c.get("/health")).status == 200


@at("phone_client: PHONE_API_KEY 가 없으면 보내지 않고 PhoneDispatchError")
async def _():
    with env(PHONE_API_KEY=None):
        try:
            await phone_client.dispatch({"contact_job_id": 1})
        except phone_client.PhoneDispatchError as e:
            assert "PHONE_API_KEY" in str(e), e
        else:
            raise AssertionError("키 없이 발신 요청을 보냈다")


@at("phone_client: 발신 요청에 Bearer PHONE_API_KEY 를 붙인다")
async def _():
    from aiohttp import web
    from aiohttp.test_utils import TestServer
    seen = {}

    async def calls(request):
        seen["auth"] = request.headers.get("Authorization")
        return web.json_response({"success": True, "data": {"contact_job_id": 1, "accepted": True},
                                  "error": None}, status=202)

    fake = web.Application()
    fake.add_routes([web.post("/internal/v1/calls", calls)])
    real_base = phone_client.BASE
    async with TestServer(fake) as srv:
        phone_client.BASE = str(srv.make_url("")).rstrip("/")
        try:
            with env(PHONE_API_KEY=PHONE_KEY):
                await phone_client.dispatch({"contact_job_id": 1})
        finally:
            phone_client.BASE = real_base
    assert seen["auth"] == f"Bearer {PHONE_KEY}", seen


@at("전화 모듈: 허용 목록에 없는 callback_url 이면 전화를 걸지 않고 400 CALLBACK_NOT_ALLOWED")
async def _():
    started = []
    with env(PHONE_API_KEY=PHONE_KEY, CONNECTION_CALLBACK_URL="http://localhost:7000",
             ANSIMON_BACKEND_BASE_URL=None, PHONE_CALLBACK_ALLOWED_ORIGINS=None):
        async with await _voice_client(started) as c:
            os.environ.pop("ANSIMON_BACKEND_BASE_URL", None)
            os.environ.pop("PHONE_CALLBACK_ALLOWED_ORIGINS", None)
            for evil in ("https://evil.example/steal",
                         "http://localhost:7000.evil.example",   # 접미사 붙이기
                         "http://localhost:7000@evil.example",   # userinfo 위장
                         "http://localhost:7001"):               # 포트 다름
                r = await c.post("/internal/v1/calls", headers=bearer(PHONE_KEY),
                                 json={"contact_job_id": 1, "callback_url": evil})
                assert r.status == 400, (evil, r.status)
                assert (await r.json())["error"]["code"] == "CALLBACK_NOT_ALLOWED", evil
    assert not started


@at("전화 모듈: 허용된 출처(경로·대소문자 무관)면 발신을 접수한다")
async def _():
    import copy
    started = []
    with env(PHONE_API_KEY=PHONE_KEY, CONNECTION_CALLBACK_URL="http://localhost:7000",
             ANSIMON_BACKEND_BASE_URL="https://api.ansimon.example/",
             PHONE_CALLBACK_ALLOWED_ORIGINS="http://conn.railway.internal:7000, "):
        async with await _voice_client(started) as c:
            job = copy.deepcopy(sys.modules["job"].DEMO_JOB)
            job["to_number"] = "01000000000"
            for i, cb in enumerate(("http://localhost:7000/", "HTTPS://API.ansimon.example",
                                    "http://conn.railway.internal:7000/x", None), start=1):
                job["contact_job_id"] = 9000 + i
                if cb is None:
                    job.pop("callback_url", None)   # 없으면 report 가 env 로 떨어진다 → 허용
                else:
                    job["callback_url"] = cb
                r = await c.post("/internal/v1/calls", headers=bearer(PHONE_KEY), json=job)
                assert r.status == 202, (cb, r.status, await r.text())
            await asyncio.sleep(0)   # create_task 로 띄운 가짜 run 이 돌 시간
    assert [jid for jid, _ in started] == [9001, 9002, 9003, 9004], started


RAG_KEY = "rag-key-00000000000000000000000000000000"


@at("rag_client: RAG_API_KEY 가 없으면 보내지 않고 RagError")
async def _():
    with env(RAG_API_KEY=None):
        try:
            await rag_client.create_intervention_plan(1, 1, {}, {})
        except rag_client.RagError as e:
            assert "RAG_API_KEY" in str(e), e
        else:
            raise AssertionError("키 없이 RAG 를 불렀다")


@at("rag_client: 안내계획 요청에 Bearer RAG_API_KEY 를 붙인다")
async def _():
    from aiohttp import web
    from aiohttp.test_utils import TestServer
    seen = {}

    async def plans(request):
        seen["auth"] = request.headers.get("Authorization")
        return web.json_response({"guidanceSentences": []})

    fake = web.Application()
    fake.add_routes([web.post("/v1/intervention-plans", plans)])
    real_base = rag_client.BASE
    async with TestServer(fake) as srv:
        rag_client.BASE = str(srv.make_url("")).rstrip("/")
        try:
            with env(RAG_API_KEY=RAG_KEY):
                await rag_client.create_intervention_plan(1, 1, {}, {})
        finally:
            rag_client.BASE = real_base
    assert seen["auth"] == f"Bearer {RAG_KEY}", seen


def _with_fake_rag(routes, run):
    from aiohttp import web
    from aiohttp.test_utils import TestServer

    async def go():
        fake = web.Application()
        fake.add_routes(routes)
        real_base = rag_client.BASE
        async with TestServer(fake) as srv:
            rag_client.BASE = str(srv.make_url("")).rstrip("/")
            try:
                with env(RAG_API_KEY=RAG_KEY):
                    return await run()
            finally:
                rag_client.BASE = real_base
    return go()


@at("rag_client: diagnostics 는 Bearer RAG_API_KEY 를 붙이고 200 이면 본문을 돌려준다")
async def _():
    from aiohttp import web
    seen = {}

    async def diag(request):
        seen["auth"] = request.headers.get("Authorization")
        return web.json_response({"willUseMock": False, "keys": {}})

    body = await _with_fake_rag([web.get("/v1/diagnostics", diag)], rag_client.diagnostics)
    assert seen["auth"] == f"Bearer {RAG_KEY}", seen
    assert body == {"willUseMock": False, "keys": {}}, body


@at("rag_client: diagnostics 가 401 을 받으면 정상으로 보지 않고 RagError")
async def _():
    from aiohttp import web

    async def diag(_):
        return web.json_response({"success": False, "error": {"code": "UNAUTHORIZED"}}, status=401)

    try:
        await _with_fake_rag([web.get("/v1/diagnostics", diag)], rag_client.diagnostics)
    except rag_client.RagError as e:
        assert "401" in str(e), e
    else:
        raise AssertionError("401 인데 진단이 성공으로 처리됐다")


if __name__ == "__main__":
    for line in PASS:
        print(f"  통과  {line}")
    for line in FAIL:
        print(f"  실패  {line}")
    print(f"\n{len(PASS)} 통과 / {len(FAIL)} 실패")
    sys.exit(1 if FAIL else 0)
