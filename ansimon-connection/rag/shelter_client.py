# -*- coding: utf-8 -*-
"""쉼터 추천 (서울열린데이터광장 + TMAP 보행자경로) — LLM 파이프라인 직결용

est-hackathon_tmap/shelter/recommend.py 를 anshimon-rag 안으로 이식한 버전.
원본과 달라진 점(원본은 CLI 전용이라 그대로는 import 가 안 됐다):

  1. 원본 33행 `DEMO_LATLON = (37.5301 127.1236)` 문법오류(쉼표 누락) 수정.
     -> 원본 파일은 현재 import·실행 자체가 불가능하다.
  2. `sys.exit()` -> `ShelterLookupError` 예외. 서버 안에서 프로세스가 죽으면 안 된다.
  3. README/schemas 가 약속했지만 원본에 없던 필드 구현:
     `crossings`(횡단보도 수), `route`(음성안내용 경로 문장), `alternatives`(대안 쉼터).
  4. TMAP `searchOption=30`(최단거리+계단제외) 적용 — 고령자를 육교/지하보도 계단으로
     보내지 않는 것이 "편한 경로"의 핵심이라고 README 가 명시하고 있었으나 코드엔 없었다.
  5. 운영시간 컬럼이 있으면 `open_status` 를 OPEN/CLOSED 로 계산(없으면 UNKNOWN).
     LLM 은 이 값을 "설명"만 하고 생성하지 않는다 (AC-007).
  6. 동기 진입점 `recommend_shelter()` 추가 — FastAPI/Spring 에서 바로 호출 가능.

정렬 기준은 원본 그대로다. 직선거리는 후보를 줄이는 용도일 뿐이고, 추천 근거는 항상
TMAP 도보 시간이다.

TMAP 이 전부 실패하면 **직선거리로 가장 가까운 쉼터를 추천하되 그 사실을 명시한다.**
(원본과 이전 버전은 아무것도 추천하지 않고 needs_review 만 올렸다. 그러면 지도 API 가
흔들리는 폭염 피크에 어르신이 갈 곳을 하나도 못 듣는다.) 대신 다음을 지킨다:
  - `route_source = "STRAIGHT_LINE_FALLBACK"` 로 출처를 못 박는다
  - TMAP 값(walk_minutes/walk_meters/crossings/route)은 **비워 둔다.** 추정치를 그 자리에
    채우면 하류가 확정 도보시간으로 오해한다
  - `estimated_walk_minutes` 를 따로 준다 (고령자 보행속도 + 우회 보정)
  - 파이프라인이 schemas.STRAIGHT_LINE_NOTICE 고지문을 안내에 강제로 끼워 넣고,
    근거검증이 그 고지문 유무를 ERROR 로 감시한다

단독 실행:
    python shelter_client.py                       # 예시 좌표(서울시청), OpenAPI
    python shelter_client.py 37.5013 127.0396
    python shelter_client.py --file=무더위쉼터.csv
    python shelter_client.py --demo                # 네트워크 없이 로직만 검증
"""
from __future__ import annotations

import asyncio
import csv
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from math import asin, ceil, cos, radians, sin, sqrt
from pathlib import Path
from typing import Any, Optional

import aiohttp

from schemas import ROUTE_SOURCE_STRAIGHT_LINE, ROUTE_SOURCE_TMAP

BASE_DIR = Path(__file__).resolve().parent

# DB 연결 전까지 쓰는 예시 좌표. 나중에 elderly_profile.latitude/longitude 로 대체된다.
DEMO_LATLON = (37.5665, 126.9780)   # 서울시청

SEOUL = "http://openapi.seoul.go.kr:8088"
TMAP = "https://apis.openapi.sk.com/tmap/routes/pedestrian?version=1"

PAGE = 1000          # 서울 오픈API 는 1회 최대 1000건
CANDIDATES = 5       # TMAP 은 1건당 1콜이라 직선거리 상위 N개만 확인한다
WALK_LIMIT_MIN = 20  # 폭염에 고령자가 걸을 만한 상한. 넘으면 사람이 확인해야 한다
ROUTE_STEPS_MAX = 6  # 전화로 읽어줄 수 있는 안내 문장 수 상한
TMAP_SEARCH_OPTION = 30  # 최단거리 + 계단 제외 (고령자 보행)

# --- TMAP 실패 시 직선거리 폴백에 쓰는 보정값 -------------------------------
# 예전에는 TMAP 이 전부 실패하면 쉼터를 아예 추천하지 않았다(needs_review 만 올림).
# 그러면 폭염 피크에 지도 API 가 흔들릴 때 어르신이 갈 곳을 아무것도 못 듣는다.
# 그래서 "직선거리로 가장 가까운 곳"을 추천하되, 그게 추정치라는 사실을
# route_source 로 표시하고 고정 고지문(schemas.STRAIGHT_LINE_NOTICE)을 함께 내보낸다.
# 지역사회 거주 65세 이상 평균 보행속도는 약 1.0~1.2m/s 지만, 폭염에 천천히 걷는 것을
# 감안해 0.83m/s(50m/분)로 보수적으로 잡는다. 더 낮추면(0.75m/s) 700m 짜리 쉼터도
# 20분 초과로 걸려 대부분의 폴백이 사람 확인 대기로 묶인다 — 그건 과잉이다.
ELDERLY_WALK_M_PER_MIN = 50
DETOUR_FACTOR = 1.3           # 직선거리 -> 실제 도보거리 우회 보정 (도시부 통상치)

# 쉼터명·주소 후보 키. 위경도는 이름으로 찾지 않는다 (아래 latlon 참고).
NAME_KEYS = ("쉼터명칭", "시설명", "명칭", "R_AREA_NM", "RSTR_NM", "FCLTY_NM", "AREA_NM", "NM")
ADDR_KEYS = ("도로명주소", "지번주소", "소재지도로명주소",
             "RN_DETAIL_ADRES", "RDNMADR", "ADRES", "DTL_ADRES", "LNMADR")

# 한반도 위경도 범위. 두 구간이 겹치지 않아서 값만 보고 위도/경도를 구분할 수 있다.
LAT_RANGE, LON_RANGE = (33.0, 39.0), (124.0, 132.0)

_TIME_RE = re.compile(r"^(\d{1,2})[:시]?(\d{2})?")
_WARNED: set[str] = set()


class ShelterLookupError(RuntimeError):
    """쉼터 목록을 확보하지 못했다. 서버는 이 예외를 502/503 으로 변환한다."""


# --- 좌표/행 파싱 -----------------------------------------------------------


def pick(row: dict, keys: tuple[str, ...]):
    for k in keys:
        if (v := row.get(k)) not in (None, ""):
            return v
    return None


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """직선거리(m). 후보를 줄이는 용도로만 쓴다."""
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * 6371000 * asin(sqrt(a))


def latlon(row: dict) -> tuple[float, float] | None:
    """필드명이 아니라 값의 범위로 위도·경도를 찾는다.

    포털·데이터셋마다 컬럼명이 LA/LAT/YCORD/위도 등으로 제각각인데, 한국 위도(33~39)와
    경도(124~132)는 범위가 겹치지 않는다. TM 좌표(21만·54만)는 범위 밖이라 자동 제외된다.
    """
    lat = lon = None
    for v in row.values():
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        if lat is None and LAT_RANGE[0] < f < LAT_RANGE[1]:
            lat = f
        elif lon is None and LON_RANGE[0] < f < LON_RANGE[1]:
            lon = f
    return (lat, lon) if lat and lon else None


def _open_status(row: dict) -> tuple[str, Optional[str]]:
    """운영시간 컬럼이 있으면 지금 열려있는지 계산한다. 없으면 UNKNOWN.

    이 값은 '사실'이라 LLM 이 만들어내면 안 된다 (AC-007). 원천 데이터에서만 온다.
    """
    begin = end = None
    for k, v in row.items():
        if not isinstance(v, str) or not v.strip():
            continue
        key = str(k)
        if ("운영" in key or "OPER" in key.upper()) and ("시작" in key or "BEGIN" in key.upper()):
            begin = v.strip()
        elif ("운영" in key or "OPER" in key.upper()) and ("종료" in key or "END" in key.upper()):
            end = v.strip()

    if not (begin and end):
        return "UNKNOWN", None

    raw = f"{begin}~{end}"

    def _hm(text: str) -> Optional[int]:
        m = _TIME_RE.match(text)
        if not m:
            return None
        return int(m.group(1)) * 60 + int(m.group(2) or 0)

    b, e = _hm(begin), _hm(end)
    if b is None or e is None:
        return "UNKNOWN", raw

    # 한국 시설의 운영시간이므로 KST 로 판정한다. datetime.now() 는 서버 로컬시간이라
    # UTC 장비에 올리면 9시간 어긋나 OPEN/CLOSED 가 뒤집힌다.
    now = datetime.now(timezone(timedelta(hours=9)))
    minutes = now.hour * 60 + now.minute
    return ("OPEN" if b <= minutes < e else "CLOSED"), raw


def to_shelter(row: dict) -> dict | None:
    """원본 행 -> 우리 모양. 좌표를 못 찾은 행은 버린다."""
    if not (c := latlon(row)):
        return None
    if (name := pick(row, NAME_KEYS)) is None and "name" not in _WARNED:
        _WARNED.add("name")   # 이름 컬럼만 못 찾은 건 치명적이지 않다. 딱 한 번만 알린다.
        print(f"  ! 쉼터명 컬럼을 못 찾았습니다. 실제 컬럼: {', '.join(row)}\n"
              f"    -> shelter_client.py 의 NAME_KEYS 에 추가하세요.", file=sys.stderr)
    if pick(row, ADDR_KEYS) is None and "addr" not in _WARNED:
        _WARNED.add("addr")   # 주소가 비면 복지사가 어디인지 확인할 방법이 없다
        print(f"  ! 쉼터 주소 컬럼을 못 찾았습니다. 실제 컬럼: {', '.join(row)}\n"
              f"    -> shelter_client.py 의 ADDR_KEYS 에 추가하세요.", file=sys.stderr)
    status, hours = _open_status(row)
    return {"name": name or "이름 미상", "address": pick(row, ADDR_KEYS),
            "lat": c[0], "lon": c[1], "open_status": status, "open_hours_raw": hours}


def from_file(path: str) -> list[dict]:
    """포털에서 직접 내려받은 CSV/JSON. 시연 때 API 장애에 걸리지 않는 길."""
    p = Path(path)
    if not p.is_absolute() and not p.exists():
        p = BASE_DIR / path          # 서버에서 상대경로로 넘어와도 찾을 수 있게
    if not p.exists():
        raise ShelterLookupError(f"쉼터 파일을 찾을 수 없습니다: {path}")

    if p.suffix.lower() == ".csv":
        with p.open(encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))

    body = json.loads(p.read_text(encoding="utf-8-sig"))
    if isinstance(body, list):
        return body
    for v in body.values():                      # {"DATA":[...]} / {"서비스명":{"row":[...]}}
        if isinstance(v, list):
            return v
        if isinstance(v, dict) and isinstance(v.get("row"), list):
            return v["row"]
    raise ShelterLookupError(f"{path} 에서 행 목록을 못 찾았습니다. 최상위 키: {list(body)}")


# --- 외부 API ---------------------------------------------------------------


async def fetch_shelters(s: aiohttp.ClientSession) -> list[dict]:
    """서울열린데이터광장 무더위쉼터 목록. 1000건씩 끝까지 받는다."""
    key = os.getenv("SHELTER_API_BASE_URL") or os.getenv("SHELTER_API_KEY")
    if not key:
        raise ShelterLookupError("SHELTER_API_BASE_URL(인증키)가 .env 에 없습니다.")
    key = key.strip()
    service = os.getenv("SHELTER_SERVICE", "TbGtnHwcwP").strip()

    rows: list[dict] = []
    while True:
        start = len(rows) + 1
        url = f"{SEOUL}/{key}/json/{service}/{start}/{start + PAGE - 1}/"
        try:
            async with s.get(url, timeout=aiohttp.ClientTimeout(total=20)) as r:
                body = await r.json(content_type=None)
        except Exception as e:   # 워크플로우 §11: 쉼터 API 실패는 예상된 상황이다
            raise ShelterLookupError(
                f"쉼터 API 연결 실패 ({type(e).__name__}) — {SEOUL}. 망 차단·오타·포털 점검을 확인하세요."
            ) from e

        block = body.get(service) if isinstance(body.get(service), dict) else {}
        result = block.get("RESULT") or body.get("RESULT") or {}
        code = result.get("CODE", "")
        if code and code != "INFO-000":
            raise ShelterLookupError(
                f"쉼터 API 오류 {code}: {result.get('MESSAGE')} (SERVICE={service}). "
                f"포털 > 해당 데이터셋 > Open API 탭의 '서비스명'을 .env 의 SHELTER_SERVICE 에 넣으세요."
            )

        page = block.get("row") or []
        if not page:
            if not rows:   # 첫 페이지부터 비었다 = 추측이 틀렸다. 원본을 그대로 보여준다.
                raise ShelterLookupError(
                    "쉼터 목록이 비었습니다. 서버 원본 응답: "
                    + json.dumps(body, ensure_ascii=False)[:500]
                    + " -> 서비스명이 틀렸을 가능성이 큽니다. SHELTER_FILE 로 CSV 를 쓰는 것도 방법입니다."
                )
            break
        rows += page
        total = block.get("list_total_count")
        if len(page) < PAGE or (total and len(rows) >= int(total)):
            break
    return rows


def _parse_tmap(payload: dict) -> dict:
    """TMAP 보행자경로 응답 -> 도보시간/거리/횡단보도수/안내문장."""
    features = payload["features"]
    head = features[0]["properties"]

    steps: list[str] = []
    crossings = 0
    for f in features:
        p = f.get("properties", {})
        desc = (p.get("description") or "").strip()
        if not desc:
            continue
        if "횡단보도" in desc:
            crossings += 1
        steps.append(desc)

    return {
        "walk_meters": int(head["totalDistance"]),
        "walk_minutes": max(1, round(head["totalTime"] / 60)),
        "crossings": crossings,
        # 전화로 읽어줄 문장. 너무 길면 어르신이 못 따라오므로 앞부분만 남기고 마지막은 도착 안내.
        "route": (steps[:ROUTE_STEPS_MAX] + ["도착"]) if len(steps) > ROUTE_STEPS_MAX else steps or ["도착"],
    }


async def walk_time(s: aiohttp.ClientSession, lat: float, lon: float,
                    dest: dict) -> dict | None:
    """TMAP 보행자 경로. 실패하면 None — 직선거리로 대체하지 않는다."""
    key = (os.getenv("TMAP_APP_KEY") or "").strip()
    if not key:
        print("  · TMAP_APP_KEY 가 없습니다 — 경로 계산을 건너뜁니다.", file=sys.stderr)
        return None

    body = {"startX": lon, "startY": lat, "endX": dest["lon"], "endY": dest["lat"],
            "reqCoordType": "WGS84GEO", "resCoordType": "WGS84GEO",
            "searchOption": TMAP_SEARCH_OPTION,   # 최단거리 + 계단제외
            "startName": "출발지", "endName": "쉼터"}
    try:
        async with s.post(TMAP, json=body, timeout=aiohttp.ClientTimeout(total=15),
                          headers={"appKey": key, "Content-Type": "application/json"}) as r:
            if r.status != 200:
                print(f"  · TMAP {r.status} — {dest['name']} 건너뜀", file=sys.stderr)
                return None
            payload = await r.json(content_type=None)
    except Exception as e:
        print(f"  · TMAP 실패 ({type(e).__name__}) — {dest['name']} 건너뜀", file=sys.stderr)
        return None

    try:
        return dest | _parse_tmap(payload)
    except (KeyError, IndexError, TypeError) as e:
        print(f"  · TMAP 응답 파싱 실패 ({type(e).__name__}) — {dest['name']} 건너뜀", file=sys.stderr)
        return None


# --- 추천 -------------------------------------------------------------------


def _estimate_walk_minutes(distance_m: float) -> int:
    """직선거리 -> 고령자 도보 추정 분. 확정값이 아니라 '추정'이라는 점이 중요하다."""
    return max(1, ceil(distance_m * DETOUR_FACTOR / ELDERLY_WALK_M_PER_MIN))


def _straight_line_fallback(lat: float, lon: float, near: list[dict], source: str) -> dict:
    """TMAP 이 전부 실패했을 때 직선거리로 가장 가까운 쉼터를 추천한다.

    TMAP 값(walk_minutes/walk_meters/crossings/route)은 **비워 둔다.** 추정치를 그 자리에
    채우면 하류 모듈이 확정 도보시간으로 오해한다. 대신 distance_m 과
    estimated_walk_minutes 를 따로 주고, route_source 로 출처를 못 박는다.
    """
    if not near:
        return {"source": source, "name": "확인 필요", "needs_review": True,
                "reason": "쉼터 후보 없음", "route_source": ROUTE_SOURCE_STRAIGHT_LINE,
                "candidates": 0, "route": [], "alternatives": []}

    ranked = sorted(near, key=lambda x: haversine(lat, lon, x["lat"], x["lon"]))
    best = ranked[0]
    distance = haversine(lat, lon, best["lat"], best["lon"])
    estimated = _estimate_walk_minutes(distance)

    return best | {
        "source": source,
        "route_source": ROUTE_SOURCE_STRAIGHT_LINE,
        "reason": "TMAP 경로 계산 실패 — 직선거리로 대체",
        "distance_m": round(distance, 1),
        "estimated_walk_minutes": estimated,
        # 경로를 모르니 안내 문장도 없다. 고지문이 이 빈자리를 설명한다.
        "route": [],
        "crossings": None,
        "candidates": 0,
        # 추정으로도 20분을 넘으면 폭염에 혼자 보낼 수 없다
        "needs_review": estimated > WALK_LIMIT_MIN,
        "alternatives": [
            {"name": a["name"],
             "estimated_walk_minutes": _estimate_walk_minutes(haversine(lat, lon, a["lat"], a["lon"]))}
            for a in ranked[1:]
        ],
    }


def _rank(routed: list[dict]) -> list[dict]:
    """도보시간 -> 횡단보도 수 순. 시간이 같으면 길을 덜 건너는 쪽이 고령자에게 안전하다."""
    return sorted(routed, key=lambda x: (x["walk_minutes"], x.get("crossings", 0)))


async def recommend_shelter_async(lat: float, lon: float, path: Optional[str] = None,
                                  candidates: int = CANDIDATES) -> dict:
    """도보 시간이 가장 짧은 쉼터 1곳 + 대안. pipeline 의 shelter 인자에 그대로 넣는다."""
    async with aiohttp.ClientSession() as s:
        rows = from_file(path) if path else await fetch_shelters(s)
        all_ = [x for r in rows if (x := to_shelter(r))]
        if not all_:
            raise ShelterLookupError(
                f"{len(rows)}행을 받았지만 위경도를 가진 행이 하나도 없습니다. "
                f"첫 행: {json.dumps(rows[0], ensure_ascii=False)[:300] if rows else '(없음)'}"
            )
        print(f"쉼터 {len(all_)}곳 확보 (원본 {len(rows)}행)", file=sys.stderr)

        # 직선거리 상위 N개만 TMAP 에 물어본다
        near = sorted(all_, key=lambda x: haversine(lat, lon, x["lat"], x["lon"]))[:candidates]
        routed = [x for x in await asyncio.gather(
            *(walk_time(s, lat, lon, d) for d in near)) if x]

    source = "SEOUL_FILE" if path else "SEOUL_OPENAPI"

    if not routed:
        return _straight_line_fallback(lat, lon, near, source)

    ranked = _rank(routed)
    best = ranked[0]
    return best | {
        # 이 쉼터는 서울시 원천 데이터에서 직접 골라온 것이다. 근거검증에서 다시
        # 실존 대조할 필요가 없다는 표시 (evidence_verifier._check_shelter_exists 참고).
        "source": source,
        "route_source": ROUTE_SOURCE_TMAP,
        "distance_m": round(haversine(lat, lon, best["lat"], best["lon"]), 1),
        "candidates": len(routed),
        # 폭염에 20분 넘게 걷게 하지 않는다. 사회복지사가 판단하도록 넘긴다.
        "needs_review": best["walk_minutes"] > WALK_LIMIT_MIN,
        "alternatives": [
            {"name": a["name"], "walk_minutes": a["walk_minutes"], "crossings": a.get("crossings", 0)}
            for a in ranked[1:]
        ],
    }


def recommend_shelter(lat: float, lon: float, path: Optional[str] = None,
                      candidates: int = CANDIDATES) -> dict:
    """동기 진입점. FastAPI(def 핸들러)·Spring·pipeline 어디서든 바로 호출한다."""
    path = path or os.getenv("SHELTER_FILE") or None
    return asyncio.run(recommend_shelter_async(lat, lon, path, candidates))


# --- 자체검사 ---------------------------------------------------------------


def demo() -> None:
    """API 없이 도는 자체검사 — 후보 압축·정렬·응답 파싱만 확인한다."""
    me = (37.5665, 126.9780)
    assert 885 < haversine(37.5665, 126.9780, 37.5745, 126.9780) < 895   # 위도 0.008° ≈ 890m
    assert haversine(*me, *me) == 0

    # 실제 데이터 모양 그대로: 컬럼명을 몰라도, 경도가 위도보다 앞에 와도 잡아야 한다.
    rows = [{"R_AREA_NM": "먼쉼터", "LAT": "37.60", "LOT": "126.98"},
            {"쉼터명칭": "가까운쉼터", "경도": "126.9785", "위도": "37.5670",
             "X좌표": "211184.80", "Y좌표": "547780.40", "년도": "2026"},
            {"R_AREA_NM": "좌표없음", "LAT": "", "LOT": ""},
            {"R_AREA_NM": "해외", "LAT": "48.85", "LOT": "2.35"}]
    ok = [x for r in rows if (x := to_shelter(r))]
    assert len(ok) == 2, ok
    assert (ok[1]["lat"], ok[1]["lon"]) == (37.5670, 126.9785), ok[1]   # TM 좌표에 안 속음
    ok[1]["name"] = "가까운쉼터"        # 한글 컬럼명은 NAME_KEYS 밖 -> "이름 미상"

    near = sorted(ok, key=lambda x: haversine(*me, x["lat"], x["lon"]))
    assert near[0]["name"] == "가까운쉼터"

    # 직선거리가 가까워도 도보가 더 걸리면 뒤집힌다 — 이게 이 파일의 존재 이유다
    routed = [near[0] | {"walk_minutes": 18, "crossings": 0}, near[1] | {"walk_minutes": 6, "crossings": 2}]
    assert _rank(routed)[0]["name"] == "먼쉼터"

    # 도보시간이 같으면 횡단보도가 적은 쪽
    tie = [{"name": "길많이건넘", "walk_minutes": 5, "crossings": 3},
           {"name": "길안건넘", "walk_minutes": 5, "crossings": 0}]
    assert _rank(tie)[0]["name"] == "길안건넘"

    # TMAP 응답 파싱: 횡단보도 개수와 안내 문장
    fake = {"features": [
        {"properties": {"totalDistance": 162, "totalTime": 180}},
        {"properties": {"description": "성내로 를 따라 80m 이동"}},
        {"properties": {"description": "횡단보도 후 직진"}},
        {"properties": {"description": "도착"}},
    ]}
    parsed = _parse_tmap(fake)
    assert parsed == {"walk_meters": 162, "walk_minutes": 3, "crossings": 1,
                      "route": ["성내로 를 따라 80m 이동", "횡단보도 후 직진", "도착"]}, parsed

    # 운영시간 파싱
    assert _open_status({"평일운영시작시각": "09:00", "평일운영종료시각": "18:00"})[1] == "09:00~18:00"
    assert _open_status({"이름": "값"}) == ("UNKNOWN", None)

    print("자체검사 통과 — 직선거리 압축 + 도보시간/횡단보도 정렬 + TMAP 파싱 + 운영시간")


if __name__ == "__main__":
    if "--demo" in sys.argv:
        demo()
        raise SystemExit

    try:
        from dotenv import load_dotenv
        load_dotenv(BASE_DIR / ".env")
    except ImportError:
        pass

    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    file_arg = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--file=")), None)
    lat, lon = (float(args[0]), float(args[1])) if len(args) > 1 else DEMO_LATLON
    print(f"기준 위치 {lat}, {lon}" + ("  (예시 좌표)" if (lat, lon) == DEMO_LATLON else ""))
    try:
        print(json.dumps(recommend_shelter(lat, lon, file_arg), ensure_ascii=False, indent=2))
    except ShelterLookupError as e:
        sys.exit(f"쉼터 조회 실패: {e}")
