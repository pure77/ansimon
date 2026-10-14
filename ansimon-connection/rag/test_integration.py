# -*- coding: utf-8 -*-
"""통합 테스트

    python test_integration.py            # 오프라인 (기본). 외부 API 를 하나도 안 부른다
    python test_integration.py --live     # 실제 서울시/TMAP/Alan 까지 호출

왜 오프라인이 기본인가: 해커톤 당일 포털 점검이나 키 만료로 테스트가 빨간불이 되면
"우리 코드가 깨진 건지 남의 API 가 죽은 건지" 구분이 안 된다. 우리 로직은 우리 손으로
검증하고, 외부 연동은 --live 로 따로 확인한다.

--- 테스트 격리 원칙 (전판에서 여기를 어겨서 오진이 났다) --------------------
1. `.env` 는 **이 파일이 맨 처음에 직접 로드한다.** 예전엔 안 했는데, [5] 단계에서
   `import server` 가 내부적으로 load_dotenv 를 부르면서 테스트 중간에 환경변수가
   생겨났다. [1]~[4] 는 키 없이 돌고 [5] 부터 실 API 를 부르는 상태가 되어,
   같은 코드가 순서에 따라 다르게 동작했다.
2. 가짜 TMAP 은 **컨텍스트 매니저로만** 설치하고 반드시 되돌린다. 예전엔 모듈 전역을
   갈아끼우고 복구하지 않아서, 한 번 설치되면 그 뒤 모든 테스트(특히 --live 의 실 API
   테스트)가 가짜를 쓰게 됐다.
3. 픽스처 의존 단정(쉼터 이름 == "종로노인종합복지관 경로당")은 오프라인에서만.
   --live 에서는 구조만 본다.
"""
from __future__ import annotations

import json
import os
import sys
from contextlib import contextmanager
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

LIVE = "--live" in sys.argv
FIXTURE = str(BASE_DIR / "fixtures" / "sample_shelters_geo.csv")

# (1) .env 를 가장 먼저, 명시적으로. 이 아래 어떤 import 도 환경을 바꾸지 못하게 한다.
try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")
except ImportError:
    print("! python-dotenv 가 없습니다. pip install python-dotenv", file=sys.stderr)

if LIVE:
    # 실 API 를 보러 왔으므로 픽스처 스위치는 꺼둔다
    os.environ.pop("SHELTER_FILE", None)
else:
    # Alan 키를 "빈 값"으로 덮어 mock 경로를 강제한다. pop 으로 지우면 안 된다 —
    # load_dotenv 는 os.environ 에 키가 "없을 때만" 채우므로, 지워두면 나중에
    # `import server` 가 부르는 load_dotenv 가 .env 에서 키를 되살려 테스트 도중에
    # 실 API 를 때린다. 빈 문자열로 점유해두면 아무도 덮어쓰지 못한다.
    os.environ["ALAN_API_KEY"] = ""
    os.environ["SHELTER_FILE"] = FIXTURE

import alan_client          # noqa: E402
import llm_client           # noqa: E402
import pipeline             # noqa: E402
import shelter_client       # noqa: E402

PASSED: list[str] = []
FAILED: list[tuple[str, str]] = []
SKIPPED: list[tuple[str, str]] = []


class Skip(Exception):
    """이 모드에서는 의미가 없는 테스트."""


def check(name: str, fn) -> None:
    try:
        fn()
        PASSED.append(name)
        print(f"  PASS  {name}")
    except Skip as e:
        SKIPPED.append((name, str(e)))
        print(f"  SKIP  {name}  ({e})")
    except AssertionError as e:
        FAILED.append((name, str(e)))
        print(f"  FAIL  {name}\n        {e}")
    except Exception as e:
        FAILED.append((name, f"{type(e).__name__}: {e}"))
        print(f"  ERROR {name}\n        {type(e).__name__}: {e}")


# --- 가짜 TMAP + 픽스처 (반드시 복구된다) -----------------------------------

_FAKE_WALK = {
    "종로노인종합복지관 경로당": (3, 162, ["삼봉로를 따라 80m 이동", "횡단보도 후 직진", "도착"]),
    "을지로경로당": (7, 480, ["을지로를 따라 400m 이동", "도착"]),
    "용산역광장 스마트쉼터": (25, 1900, ["한강대로를 따라 1.8km 이동", "도착"]),
    "왕십리광장 그늘막": (12, 900, ["왕십리로를 따라 900m 이동", "횡단보도 후 직진", "도착"]),
    "건대입구역 쿨링포그": (30, 2400, ["능동로를 따라 2.4km 이동", "도착"]),
}


@contextmanager
def offline_shelter(only: set[str] | None = None, fail_all: bool = False):
    """쉼터 목록=픽스처 CSV, TMAP=가짜. 블록을 벗어나면 원상복구된다.

    실제 TMAP 응답 파싱은 _parse_tmap 단위 테스트가 따로 검증하므로, 여기서는
    "경로가 붙었을 때/안 붙었을 때의 배선"만 본다.
    """
    orig_walk = shelter_client.walk_time
    orig_file = os.environ.get("SHELTER_FILE")

    async def fake(session, lat, lon, dest):
        if fail_all or dest["name"] not in _FAKE_WALK:
            return None
        if only is not None and dest["name"] not in only:
            return None
        minutes, meters, route = _FAKE_WALK[dest["name"]]
        return dest | {"walk_minutes": minutes, "walk_meters": meters,
                       "crossings": sum(1 for s in route if "횡단보도" in s), "route": route}

    shelter_client.walk_time = fake
    os.environ["SHELTER_FILE"] = FIXTURE
    try:
        yield
    finally:
        shelter_client.walk_time = orig_walk
        if orig_file is None:
            os.environ.pop("SHELTER_FILE", None)
        else:
            os.environ["SHELTER_FILE"] = orig_file


@contextmanager
def env(**kv):
    old = {k: os.environ.get(k) for k in kv}
    os.environ.update({k: str(v) for k, v in kv.items()})
    try:
        yield
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


# --- 1. 쉼터 모듈 (항상 픽스처+가짜. 순수 로직 검증) ------------------------


def t_shelter_selftest():
    shelter_client.demo()


def t_shelter_picks_shortest_walk():
    with offline_shelter():
        s = shelter_client.recommend_shelter(37.5665, 126.9780, FIXTURE)
    # 도보시간이 가장 짧은 곳. 직선거리 최단(종로)과 일치하는지는 상관없다 —
    # 판단 근거는 항상 TMAP 도보시간이다
    assert s["name"] == "종로노인종합복지관 경로당", s["name"]
    assert s["walk_minutes"] == 3 and s["crossings"] == 1, s
    assert s["route"][-1] == "도착", s["route"]
    assert s["source"] == "SEOUL_FILE" and s["needs_review"] is False, s
    assert any(a["name"] == "을지로경로당" for a in s["alternatives"]), s["alternatives"]


def t_shelter_needs_review_over_20min():
    with offline_shelter(only={"용산역광장 스마트쉼터"}):
        s = shelter_client.recommend_shelter(37.5665, 126.9780, FIXTURE)
    assert s["needs_review"] is True and s["walk_minutes"] == 25, s


def t_shelter_tmap_all_fail_uses_straight_line():
    """TMAP 전부 실패 -> 직선거리로 가장 가까운 쉼터를 추천하되 출처를 명시한다."""
    with offline_shelter(fail_all=True):
        s = shelter_client.recommend_shelter(37.5665, 126.9780, FIXTURE)

    assert s["name"] == "종로노인종합복지관 경로당", s["name"]   # 서울시청에서 직선 최단
    assert s["route_source"] == "STRAIGHT_LINE_FALLBACK", s
    assert s["estimated_walk_minutes"] and s["distance_m"], s
    # TMAP 값 자리에 추정치를 채우면 안 된다 — 하류가 확정 도보시간으로 오해한다
    assert s.get("walk_minutes") is None, f"추정치가 walk_minutes 에 들어갔다: {s}"
    assert s.get("walk_meters") is None, f"추정치가 walk_meters 에 들어갔다: {s}"
    assert s["crossings"] is None and s["route"] == [], s
    assert s["needs_review"] is False, f"700m 거리인데 사람 확인 대기로 묶였다: {s}"
    assert s["alternatives"][0]["estimated_walk_minutes"], s["alternatives"]


def t_shelter_straight_line_far_needs_review():
    """직선거리 추정으로도 20분을 넘으면 폭염에 혼자 보내지 않는다."""
    with offline_shelter(fail_all=True):
        # 강남 한복판 — 픽스처 쉼터가 전부 멀다
        s = shelter_client.recommend_shelter(37.4979, 127.0276, FIXTURE)
    assert s["route_source"] == "STRAIGHT_LINE_FALLBACK", s
    assert s["estimated_walk_minutes"] > 20 and s["needs_review"] is True, s


def t_shelter_open_status():
    with offline_shelter():
        s = shelter_client.recommend_shelter(37.5665, 126.9780, FIXTURE)
    assert s["open_status"] in ("OPEN", "CLOSED"), s
    assert s["open_hours_raw"] == "09:00~18:00", s


def t_fake_tmap_is_restored():
    """(2)번 원칙 자체를 검증한다 — 가짜가 새어나가면 --live 가 통째로 거짓말이 된다."""
    real = shelter_client.walk_time
    with offline_shelter():
        assert shelter_client.walk_time is not real, "가짜가 설치되지 않았다"
    assert shelter_client.walk_time is real, "가짜 TMAP 이 복구되지 않았다"


# --- 2. Alan 응답 파싱 ------------------------------------------------------


def t_extract_json_plain():
    assert alan_client.extract_json('{"a": 1}') == {"a": 1}


def t_extract_json_fenced():
    assert alan_client.extract_json('```json\n{"a": 1}\n```') == {"a": 1}


def t_extract_json_with_prose():
    text = ('요청하신 안내 계획입니다.\n\n{"guidanceSentences": [{"text": "물을 드세요", '
            '"evidenceChunkIds": ["c1"]}]}\n\n도움이 되셨길 바랍니다.')
    got = alan_client.extract_json(text)
    assert got["guidanceSentences"][0]["evidenceChunkIds"] == ["c1"], got


def t_extract_json_nested_and_braces_in_string():
    got = alan_client.extract_json('answer: {"msg": "중괄호 } 포함", "inner": {"k": [1,2]}} 끝')
    assert got["inner"]["k"] == [1, 2], got


def t_extract_json_no_json_raises():
    try:
        alan_client.extract_json("JSON 없이 그냥 설명만 했습니다.")
    except ValueError:
        return
    raise AssertionError("JSON 이 없는데 예외가 안 났다")


# --- 3. 쉼터 필드 정규화 ----------------------------------------------------


def t_normalize_snake_case():
    n = llm_client.normalize_shelter(
        {"name": "A", "walk_minutes": 5, "walk_meters": 300, "needs_review": False,
         "open_status": "OPEN", "alternatives": [{"name": "B", "walk_minutes": 7, "crossings": 1}]})
    assert n["walkMinutes"] == 5 and n["walkMeters"] == 300, n
    assert n["alternatives"][0]["walkMinutes"] == 7, n


def t_normalize_camel_case():
    n = llm_client.normalize_shelter({"name": "A", "walkMinutes": 5, "needsReview": True})
    assert n["walkMinutes"] == 5 and n["needsReview"] is True, n


# --- 4. 엔드투엔드 ----------------------------------------------------------

PROFILE = {"targetAudience": ["ELDERLY"], "age": 82, "livesAlone": True,
           "latitude": 37.5665, "longitude": 126.9780}
RISK = {"riskLevel": "HIGH", "riskScore": 0.83, "riskFactors": ["독거", "고령"]}
WEATHER = {"temperatureC": 36.2, "heatWarning": "폭염경보"}


def _plan(**kw):
    return pipeline.generate_intervention_plan(
        elderly_id=kw.pop("eid", 101), risk_snapshot_id=kw.pop("rid", 812),
        elderly_profile=kw.pop("profile", PROFILE), risk_snapshot=kw.pop("risk", RISK),
        weather=WEATHER, **kw)


def _assert_guidance_ok(plan):
    assert plan["guidanceSentences"], f"안내 문장이 하나도 없다. warnings={plan['warnings']}"
    assert all(s["evidenceChunkIds"] for s in plan["guidanceSentences"]), \
        "근거 chunk_id 가 비어있는 문장이 있다"


def t_e2e_latlon_to_plan():
    """이번 통합의 핵심: 위경도만 주면 쉼터 -> LLM -> 검증까지 한 번에."""
    if LIVE:
        plan = _plan()
        _assert_guidance_ok(plan)
        sh = plan["recommendedShelter"]
        # 실패 원인을 메시지에 담는다. 예전엔 "쉼터가 자동 조회되지 않았다" 만 나와서
        # 서울API 문제인지 TMAP 문제인지 구분이 안 됐다.
        assert sh is not None, f"쉼터 자동조회 실패. warnings={plan['warnings']}"
        assert sh["walkMinutes"], f"TMAP 도보시간이 비었다: {sh}"
        assert sh["route"], f"TMAP 경로 문장이 비었다: {sh}"
        print(f"        실 API 결과: {sh['name']} / 도보 {sh['walkMinutes']}분 / "
              f"횡단보도 {sh['crossings']}회 / 모델 {plan['modelUsed']}")
        return

    with offline_shelter():
        plan = _plan()
    _assert_guidance_ok(plan)
    sh = plan["recommendedShelter"]
    assert sh is not None, f"쉼터가 자동 조회되지 않았다. warnings={plan['warnings']}"
    assert sh["name"] == "종로노인종합복지관 경로당", sh
    assert sh["walkMinutes"] == 3 and sh["crossings"] == 1, sh
    assert sh["route"] and sh["alternatives"], sh


def t_e2e_shelter_lookup_failure_does_not_kill_plan():
    """쉼터 API 가 죽어도 안내 문장은 나와야 한다 (과잉 차단 방지)."""
    orig = shelter_client.recommend_shelter
    shelter_client.recommend_shelter = lambda *a, **k: (_ for _ in ()).throw(
        shelter_client.ShelterLookupError("포털 점검중"))
    try:
        plan = _plan(eid=102, rid=813)
    finally:
        shelter_client.recommend_shelter = orig

    _assert_guidance_ok(plan)
    assert plan["recommendedShelter"] is None, plan["recommendedShelter"]
    assert any("쉼터 조회 실패" in w for w in plan["warnings"]), plan["warnings"]


def t_e2e_needs_review_blocks_call():
    """도보 20분 초과 -> 기본 정책에서는 자동전화 보류."""
    if LIVE:
        raise Skip("실 API 로는 needs_review 를 강제할 수 없다")
    with offline_shelter(only={"용산역광장 스마트쉼터"}), env(SHELTER_REVIEW_BLOCKS_CALL="1"):
        try:
            _plan(eid=103, rid=814)
        except pipeline.GuidanceGenerationError as e:
            assert "SHELTER_ROUTE_NEEDS_REVIEW" in {i.code for i in e.issues}, e.issues
            return
    raise AssertionError("needs_review 인데 자동전화가 보류되지 않았다")


def t_e2e_needs_review_non_blocking_mode():
    """SHELTER_REVIEW_BLOCKS_CALL=0 -> 전화는 걸되 쉼터에 확인 필요 표시."""
    if LIVE:
        raise Skip("실 API 로는 needs_review 를 강제할 수 없다")
    with offline_shelter(only={"용산역광장 스마트쉼터"}), env(SHELTER_REVIEW_BLOCKS_CALL="0"):
        plan = _plan(eid=106, rid=817)
    _assert_guidance_ok(plan)
    assert plan["recommendedShelter"]["needsReview"] is True, plan["recommendedShelter"]
    assert any("needs_review" in w for w in plan["warnings"]), plan["warnings"]


def t_e2e_straight_line_fallback_announces_itself():
    """TMAP 실패 -> 직선거리 쉼터가 추천되고, 안내에 고정 고지문이 반드시 들어간다."""
    if LIVE:
        raise Skip("실 API 로는 TMAP 전면 실패를 강제할 수 없다")
    from schemas import STRAIGHT_LINE_NOTICE

    with offline_shelter(fail_all=True):
        plan = _plan(eid=107, rid=818)

    sh = plan["recommendedShelter"]
    assert sh is not None, f"직선거리 폴백이 안 나왔다. warnings={plan['warnings']}"
    assert sh["routeSource"] == "STRAIGHT_LINE_FALLBACK", sh
    assert sh["estimatedWalkMinutes"] and sh["walkMinutes"] is None, sh

    texts = [s["text"] for s in plan["guidanceSentences"]]
    assert STRAIGHT_LINE_NOTICE in texts, f"고지 문구가 빠졌다: {texts}"
    assert texts[-1] == STRAIGHT_LINE_NOTICE, "고지 문구는 쉼터 안내 직전(맨 뒤)에 와야 한다"
    assert any("직선거리" in w for w in plan["warnings"]), plan["warnings"]


def t_e2e_tmap_route_has_no_straight_line_notice():
    """반대 방향: TMAP 경로가 멀쩡하면 고지문이 붙으면 안 된다."""
    from schemas import STRAIGHT_LINE_NOTICE
    with offline_shelter():
        plan = _plan(eid=108, rid=819)
    assert plan["recommendedShelter"]["routeSource"] == "TMAP", plan["recommendedShelter"]
    assert STRAIGHT_LINE_NOTICE not in [s["text"] for s in plan["guidanceSentences"]]


def t_verifier_catches_missing_notice():
    """생성기가 고지문을 빠뜨리면 근거검증이 막는다 (LLM 이 규칙을 어길 때의 안전망)."""
    import evidence_verifier
    from schemas import STRAIGHT_LINE_NOTICE

    fallback = {"routeSource": "STRAIGHT_LINE_FALLBACK", "name": "X", "source": "SEOUL_FILE"}
    bad = {"guidanceSentences": [{"text": "물을 드세요", "evidenceChunkIds": ["c1"]}],
           "recommendedShelter": fallback}
    codes = {i.code for i in evidence_verifier.verify_guidance_output(bad, {"c1"}, {})}
    assert "STRAIGHT_LINE_NOTICE_MISSING" in codes, codes

    # 반대로 TMAP 경로에 고지문이 붙어도 잡는다
    wrong = {"guidanceSentences": [{"text": STRAIGHT_LINE_NOTICE, "evidenceChunkIds": []}],
             "recommendedShelter": {"routeSource": "TMAP", "name": "X", "source": "SEOUL_FILE"}}
    codes = {i.code for i in evidence_verifier.verify_guidance_output(wrong, set(), {})}
    assert "STRAIGHT_LINE_NOTICE_UNEXPECTED" in codes, codes

    # 고지문은 근거 ID 가 없어도 MISSING_EVIDENCE 로 잡히지 않는다 (시스템 고지문이라)
    ok = {"guidanceSentences": [{"text": STRAIGHT_LINE_NOTICE, "evidenceChunkIds": []}],
          "recommendedShelter": fallback}
    codes = {i.code for i in evidence_verifier.verify_guidance_output(ok, set(), {})}
    assert "MISSING_EVIDENCE" not in codes, codes


def t_e2e_critical_uses_fixed_emergency_template():
    from schemas import EMERGENCY_GUIDANCE_TEMPLATE
    plan = _plan(eid=104, rid=815, profile={"targetAudience": ["ELDERLY"]},
                 risk={"riskLevel": "CRITICAL", "riskScore": 0.97}, auto_shelter=False)
    assert plan["emergencyFlag"] is True, plan
    assert plan["emergencyMessage"] == EMERGENCY_GUIDANCE_TEMPLATE, plan["emergencyMessage"]


def t_e2e_fake_shelter_is_blocked():
    try:
        _plan(eid=105, rid=816, profile={"targetAudience": ["ELDERLY"]},
              shelter={"name": "가상의쉼터12345", "address": "서울특별시 어딘가 999"})
    except pipeline.GuidanceGenerationError as e:
        assert "SHELTER_NOT_FOUND" in {i.code for i in e.issues}, [str(i) for i in e.issues]
        return
    raise AssertionError("존재하지 않는 쉼터가 통과됐다")


# --- 5. HTTP 서버 -----------------------------------------------------------


def t_http_endpoints():
    from fastapi.testclient import TestClient
    import server

    client = TestClient(server.app)
    assert client.get("/health").json() == {"status": "ok"}

    diag = client.get("/v1/diagnostics").json()
    assert "keys" in diag and "alan" in diag, diag

    body = {"elderlyId": 201, "riskSnapshotId": 901,
            "elderlyProfile": PROFILE, "riskSnapshot": RISK, "weather": WEATHER}

    if LIVE:
        r = client.post("/v1/shelter/recommend", json={"latitude": 37.5665, "longitude": 126.9780})
        assert r.status_code == 200, r.text
        assert r.json().get("route_source") == "TMAP", \
            f"TMAP 이 아니라 직선거리 폴백으로 응답했습니다: {r.text[:300]}"

        r = client.post("/v1/intervention-plans", json=body)
        if r.status_code == 422:
            raise AssertionError(
                "실 API 인데 needs_review 로 보류됐다 -> TMAP 경로 계산이 실패하고 있다. "
                "`python shelter_client.py` 로 단독 확인하세요. 응답: " + r.text[:300])
        assert r.status_code == 200, r.text
        sh = r.json()["recommendedShelter"]
        assert sh["routeSource"] == "TMAP", f"직선거리 폴백으로 응답: {sh}"
        assert sh["walkMinutes"], sh
        return

    with offline_shelter():
        r = client.post("/v1/shelter/recommend",
                        json={"latitude": 37.5665, "longitude": 126.9780, "file": FIXTURE})
        assert r.status_code == 200, r.text
        assert r.json()["name"] == "종로노인종합복지관 경로당", r.json()

        r = client.post("/v1/intervention-plans", json=body)
        assert r.status_code == 200, r.text
        assert r.json()["recommendedShelter"]["walkMinutes"] == 3, r.json()["recommendedShelter"]

    # 보류 케이스는 422 + issues
    r = client.post("/v1/intervention-plans", json={
        "elderlyId": 202, "riskSnapshotId": 902,
        "elderlyProfile": {"targetAudience": ["ELDERLY"]},
        "riskSnapshot": {"riskLevel": "HIGH", "riskScore": 0.7},
        "shelter": {"name": "가상의쉼터12345", "address": "어딘가"}})
    assert r.status_code == 422, r.status_code
    assert r.json()["detail"]["error"] == "GUIDANCE_GENERATION_BLOCKED", r.json()


# --- 6. --live 전용 ---------------------------------------------------------


def t_live_alan():
    if not LIVE:
        raise Skip("--live 에서만")
    import alan_check
    assert alan_check.main() == 0, "Alan API 진단 실패 — 위 출력 참고"


def t_live_shelter():
    """실제 서울열린데이터광장 + TMAP. 가짜가 안 끼도록 여기서 한 번 더 확인한다."""
    if not LIVE:
        raise Skip("--live 에서만")
    assert "fake" not in shelter_client.walk_time.__name__, \
        "가짜 TMAP 이 아직 설치돼 있다 — 이 테스트는 무의미하다"

    s = shelter_client.recommend_shelter(37.5665, 126.9780)
    print(json.dumps(s, ensure_ascii=False, indent=2))
    assert s.get("name"), s
    # 직선거리 폴백은 이제 "정상 동작"이라 name 만 봐서는 TMAP 성공 여부를 알 수 없다.
    # 이 테스트의 목적은 TMAP 연동 확인이므로 route_source 를 못 박아 본다.
    assert s.get("route_source") == "TMAP", (
        f"TMAP 경로를 못 받아 직선거리로 폴백했습니다 ({s.get('reason')}). "
        f"appKey/쿼터/엔드포인트를 확인하세요.")
    assert s.get("walk_minutes") and s.get("route"), f"TMAP 값이 비었다: {s}"


def main() -> int:
    print("=" * 62)
    print(f" 안심온 통합 테스트 ({'LIVE — 실제 API 호출' if LIVE else '오프라인'})")
    print("=" * 62)

    print("\n[1] 쉼터 모듈 (픽스처 + 가짜 TMAP, 순수 로직)")
    check("쉼터 자체검사 (거리·정렬·응답파싱)", t_shelter_selftest)
    check("도보 최단 쉼터 선택 + 대안 목록", t_shelter_picks_shortest_walk)
    check("도보 20분 초과 -> needs_review", t_shelter_needs_review_over_20min)
    check("TMAP 전부 실패 -> 직선거리 쉼터 추천 + 출처 표시", t_shelter_tmap_all_fail_uses_straight_line)
    check("직선거리 추정 20분 초과 -> needs_review", t_shelter_straight_line_far_needs_review)
    check("운영시간 -> open_status", t_shelter_open_status)
    check("가짜 TMAP 이 반드시 복구된다", t_fake_tmap_is_restored)

    print("\n[2] Alan 응답 파싱")
    check("순수 JSON", t_extract_json_plain)
    check("코드펜스 감싼 JSON", t_extract_json_fenced)
    check("설명문 사이에 낀 JSON", t_extract_json_with_prose)
    check("중첩/문자열 속 중괄호", t_extract_json_nested_and_braces_in_string)
    check("JSON 없으면 예외", t_extract_json_no_json_raises)

    print("\n[3] 쉼터 필드 정규화")
    check("snake_case 입력", t_normalize_snake_case)
    check("camelCase 입력", t_normalize_camel_case)

    print(f"\n[4] 엔드투엔드 ({'실 API' if LIVE else '픽스처'})")
    check("위경도만으로 안내계획 생성", t_e2e_latlon_to_plan)
    check("쉼터 조회 실패해도 안내는 생성", t_e2e_shelter_lookup_failure_does_not_kill_plan)
    check("needs_review -> 자동전화 보류 (기본)", t_e2e_needs_review_blocks_call)
    check("needs_review -> 전화는 걸되 확인표시 (BLOCKS_CALL=0)", t_e2e_needs_review_non_blocking_mode)
    check("TMAP 실패 -> 직선거리 쉼터 + 고지문 강제", t_e2e_straight_line_fallback_announces_itself)
    check("TMAP 정상 -> 고지문 안 붙음", t_e2e_tmap_route_has_no_straight_line_notice)
    check("고지문 누락/오부착 -> 근거검증이 차단", t_verifier_catches_missing_notice)
    check("CRITICAL -> 고정 응급문구", t_e2e_critical_uses_fixed_emergency_template)
    check("없는 쉼터 -> 차단", t_e2e_fake_shelter_is_blocked)

    print("\n[5] HTTP 서버")
    check("/health /diagnostics /shelter /intervention-plans", t_http_endpoints)

    print("\n[6] 실제 외부 API")
    check("Alan API 진단", t_live_alan)
    check("서울시 쉼터 + TMAP 실호출", t_live_shelter)

    print("\n" + "=" * 62)
    print(f"  통과 {len(PASSED)} / 실패 {len(FAILED)} / 건너뜀 {len(SKIPPED)}")
    for name, err in FAILED:
        print(f"   X {name}: {err}")
    if not LIVE:
        print("  * 오프라인 결과입니다. TMAP 실연동은 --live 로 확인하세요.")
    print("=" * 62)
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
