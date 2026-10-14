# -*- coding: utf-8 -*-
"""백엔드 계약 + 입력 검증.

이 파일 하나가 "무엇이 나가는가"와 "무엇이 들어올 수 있는가"를 안다.
바깥으로 나가는 값은 전부 여기를 통과한다.

나가는 것 — `POST /internal/v1/contact/results` (ContactController.java) 한 개뿐이다:

    {"elderlyId", "externalCallId",
     "plan": {actionGuidance, shelterRecommendationText, callQuestionOrder, evidenceDocumentIds},
     "call": {answered, summary, shelterIntent, canMoveAlone, helpNeeded,
              symptomMentioned, confidence, transcriptRef, endedAt}}

들어오는 것에서 특히 조심하는 것:

  risk score   백엔드/ML 이 0~100 으로 줄 때가 있다. 0~1 로 환산하고 환산했다고 남긴다.
  consent      동의 상태가 아니면 전화를 만들지 않는다 (fail-closed).
  region_code  서울(11…) 이 아니면 공공 쉼터 데이터가 없다. 쉼터를 조회하지도, 묻지도 않는다.
  시각         start < end, peak 는 둘 다 있거나 둘 다 없다.
  위경도       -90~90 / -180~180.
"""
from __future__ import annotations

import hashlib
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

KST = timezone(timedelta(hours=9))

# 공공 무더위쉼터 데이터가 있는 지역. 법정동코드 앞 두 자리 = 시도.
# 서울(11) 외 지역은 쉼터 목록 자체가 없어서, 조회하면 서울 시설이 수백 km 떨어진 채로 나온다.
SHELTER_REGION_PREFIX = os.getenv("SHELTER_REGION_PREFIX", "11")

RISK_LEVELS = ("LOW", "MEDIUM", "HIGH", "CRITICAL")
YNU = ("YES", "NO", "UNKNOWN")
SUMMARY_MAX = 1000            # 백엔드 summary 컬럼 길이

# 자동 전화를 허용할 consent_status. 백엔드 enum 이 확정되면 여기만 고친다.
CONSENT_OK = {s.strip().upper() for s in
              os.getenv("CONSENT_OK_VALUES", "AGREED,GRANTED,CONSENTED").split(",") if s.strip()}

# 전화 모듈의 call_ending(voice/report.py:ending()) -> 통화가 이루어졌는가.
# 받으셨다가 중간에 끊으신 것도 '받은' 것이다. 무슨 일이 있었는지는 summary 앞머리에 남는다.
ANSWERED_ENDINGS = {"COMPLETED", "USER_HUNG_UP_EARLY", "TIMEOUT"}


class ContractError(ValueError):
    """계약을 어기는 값. 전화를 걸기 전에 되돌린다."""


class ConsentError(ContractError):
    """동의하지 않은(또는 동의 상태를 모르는) 대상자. 자동 전화를 만들지 않는다."""


# --- 원시값 정리 --------------------------------------------------------------

def dec4(value: Any, lo: float = 0.0, hi: float = 1.0, default: float = 0.0) -> float:
    try:
        return round(min(max(float(value), lo), hi), 4)
    except (TypeError, ValueError):
        return default


def ynu(value: Any) -> str:
    v = str(value).upper() if value is not None else ""
    return v if v in YNU else "UNKNOWN"


def normalize_risk_score(raw: Any, warnings: list) -> float:
    """0~1 로. 82.5 같은 백분율 입력이 실제로 들어온다.

    ML 쪽이 0~1 로 내보내도록 변경 예정이지만 이 함수는 남긴다 — 0~1 입력은 그대로
    통과하므로 비용이 없고, 스케일 회귀를 잡는 안전망이 된다.
    """
    try:
        v = float(raw)
    except (TypeError, ValueError):
        raise ContractError(f"risk.score 가 숫자가 아닙니다: {raw!r}")
    if v < 0:
        warnings.append(f"risk.score 가 음수({v})라 0 으로 보정했습니다.")
        return 0.0
    if v <= 1:
        return round(v, 4)
    if v <= 100:
        warnings.append(f"risk.score 를 0~100 스케일로 보고 {v} → {round(v / 100, 4)} 로 환산했습니다.")
        return round(v / 100, 4)
    warnings.append(f"risk.score 가 100 을 넘어({v}) 1.0 으로 보정했습니다.")
    return 1.0


def dt(value: Any, field: str) -> Optional[datetime]:
    """어떤 모양으로 오든 KST datetime 으로. 시간대 정보가 없으면 KST 로 본다."""
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        d = value
    else:
        s = str(value).strip().replace("Z", "+00:00")
        try:
            d = datetime.fromisoformat(s)
        except ValueError:
            raise ContractError(f"{field} 시각을 해석할 수 없습니다: {value!r}")
    return d.astimezone(KST) if d.tzinfo else d.replace(tzinfo=KST)


def utc_iso(d: Optional[datetime] = None) -> str:
    """백엔드가 받는 시각 형식: UTC ISO-8601 + Z ("2026-08-19T02:30:00Z")."""
    return (d or datetime.now(KST)).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def coord(value: Any, field: str, limit: float) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        raise ContractError(f"{field} 가 숫자가 아닙니다: {value!r}")
    if not -limit <= v <= limit:
        raise ContractError(f"{field} 범위 초과({v}). 허용 -{limit}~{limit}")
    return round(v, 7)


def stable_id(*parts: Any) -> int:
    """내용에서 만드는 id. 같은 대상자·같은 위험시간대면 항상 같다.

    실행할 때마다 세는 카운터를 쓰면 어떤 입력이든 1 이 되고 멱등키가 고정된다.
    """
    return int(hashlib.sha1("|".join(str(x) for x in parts).encode("utf-8")).hexdigest()[:8], 16)


# --- 개인 취약정보 -> targetAudience (규칙 기반) --------------------------------
# ML 점수와 섞지 않는다. 어떤 단어 때문에 어떤 태그가 붙었는지 사람이 읽어서 검증할 수 있어야 한다.
AUDIENCE_RULES = (
    (("고혈압", "혈압"), "BLOOD_PRESSURE"),
    (("당뇨",), "DIABETES"),
    (("심장", "심혈관", "협심", "부정맥"), "CARDIOVASCULAR"),
    (("신장", "투석", "콩팥"), "RENAL"),
    (("거동", "보행", "휠체어", "지팡이", "장애"), "DISABLED"),
)


def audience_from_note(note: Optional[str]) -> tuple[list[str], list[str]]:
    tags, reasons = ["ELDERLY"], []
    for words, tag in AUDIENCE_RULES:
        hit = next((w for w in words if w in (note or "")), None)
        if hit and tag not in tags:
            tags.append(tag)
            reasons.append(f"'{hit}' 언급 → {tag}")
    return tags, reasons


def has_shelter_data(region_code: Optional[str]) -> bool:
    """이 지역에 공공 무더위쉼터 데이터가 있는가.

    서울(11…) 만 있다. 그 외 지역에서 쉼터를 조회하면 목록이 서울 것뿐이라
    수백 km 떨어진 시설이 '가장 가까운 쉼터'로 나온다. 조회하지 않는 게 맞다.
    """
    return bool(region_code) and str(region_code).startswith(SHELTER_REGION_PREFIX)


# --- 입력 정규화 --------------------------------------------------------------

def parse_request(payload: dict) -> dict:
    """요청을 하나의 모양으로 편다. camelCase / snake_case 둘 다 받는다."""
    def g(d: dict, *names, default=None):
        for n in names:
            if isinstance(d, dict) and d.get(n) is not None:
                return d[n]
        return default

    warnings: list[str] = []
    e = payload.get("elderly") or payload.get("elderlyProfile") or {}
    loc = payload.get("location") or {}
    r = payload.get("risk") or payload.get("riskSnapshot") or {}
    if not isinstance(e, dict) or not isinstance(r, dict):
        raise ContractError("elderly / risk 는 객체여야 합니다.")

    elderly_id = g(e, "id", "elderlyId", "elderly_id")
    if elderly_id is None:
        raise ContractError("elderly.id 가 없습니다. 백엔드의 elderly_profile PK 를 그대로 주세요 "
                            "— 이 값이 결과를 어느 대상자에 붙일지 결정합니다.")

    consent = str(g(e, "consentStatus", "consent_status", default="") or "").strip().upper()
    if consent not in CONSENT_OK:
        raise ConsentError(
            f"consent_status={consent or '없음'} — 동의 상태가 아니라 자동 전화를 만들지 않습니다. "
            f"(허용: {sorted(CONSENT_OK)} · CONSENT_OK_VALUES 로 조정)")

    phone = re.sub(r"[^0-9+]", "", str(g(e, "phone", default="") or ""))
    if not phone:
        raise ContractError("elderly.phone 이 없습니다 — 걸 곳이 없습니다.")

    level = str(g(r, "level", "riskLevel", "risk_level", default="") or "").upper()
    if level not in RISK_LEVELS:
        raise ContractError(f"risk.level 이 {RISK_LEVELS} 중 하나가 아닙니다: {level!r}")

    t_start = dt(g(r, "targetStartAt", "target_start_at"), "risk.targetStartAt")
    t_end = dt(g(r, "targetEndAt", "target_end_at"), "risk.targetEndAt")
    if t_start and t_end and t_start >= t_end:
        raise ContractError("risk.targetStartAt 이 targetEndAt 보다 뒤입니다 (start < end).")

    p_start = dt(g(r, "peakStartAt", "peak_start_at"), "risk.peakStartAt")
    p_end = dt(g(r, "peakEndAt", "peak_end_at"), "risk.peakEndAt")
    if bool(p_start) != bool(p_end):
        raise ContractError("peak_start_at / peak_end_at 은 둘 다 있거나 둘 다 없어야 합니다.")
    if p_start and p_start >= p_end:
        raise ContractError("risk.peakStartAt 이 peakEndAt 보다 뒤입니다.")

    region = g(e, "regionCode", "region_code") or g(r, "regionCode", "region_code")
    shelter_ok = has_shelter_data(region)
    if not shelter_ok:
        warnings.append(
            f"region_code={region or '없음'} — 공공 무더위쉼터 데이터가 없는 지역이라 "
            f"쉼터를 조회하지 않고 통화에서도 제외했습니다 (데이터가 있는 지역: "
            f"{SHELTER_REGION_PREFIX}…).")

    note = g(e, "healthNote", "health_note")
    audience, reasons = audience_from_note(note)

    return {
        "elderly_id": int(elderly_id),
        "phone": phone,
        "region_code": region,
        "shelter_available": shelter_ok,
        "latitude": coord(g(loc, "latitude", "lat") or g(e, "latitude", "lat"), "latitude", 90),
        "longitude": coord(g(loc, "longitude", "lon", "lng") or g(e, "longitude", "lon"),
                           "longitude", 180),
        "age": g(e, "age"), "health_note": note,
        "target_audience": audience, "selection_reasons": reasons,
        "risk_level": level,
        "risk_score": normalize_risk_score(g(r, "score", "riskScore", "risk_score", default=0),
                                           warnings),
        "risk_snapshot_id": g(r, "id", "riskSnapshotId", "risk_snapshot_id"),
        "target_start_at": t_start, "target_end_at": t_end,
        "peak_start_at": p_start, "peak_end_at": p_end,
        "top_factors": list(g(r, "topFactors", "top_factors", "riskFactors", "risk_factors",
                              default=[]) or []),
        "weather": payload.get("weather") or {},
        "dry_run": bool(payload.get("dryRun") or payload.get("dry_run")),
        "warnings": warnings,
    }


# --- 한국어 시각 (전화로 읽어 드릴 문장) ---------------------------------------
_HOURS = ("열두", "한", "두", "세", "네", "다섯", "여섯", "일곱", "여덟", "아홉", "열", "열한")


def _period(h: int) -> str:
    return "새벽" if h < 6 else "아침" if h < 11 else "낮" if h < 18 else "저녁" if h < 21 else "밤"


def korean_window(start: Optional[datetime], end: Optional[datetime]) -> Optional[str]:
    """'오늘 낮 한 시부터 세 시까지'. 없으면 None — 없는 걸 지어내지 않는다."""
    if not start or not end:
        return None
    today = datetime.now(KST).date()
    day = ("오늘" if start.date() == today else
           "내일" if start.date() == today + timedelta(days=1) else
           f"{start.month}월 {start.day}일")
    sp, sh = _period(start.hour), f"{_HOURS[start.hour % 12]} 시"
    ep, eh = _period(end.hour), f"{_HOURS[end.hour % 12]} 시"
    return f"{day} {sp} {sh}부터 {eh if sp == ep else f'{ep} {eh}'}까지"


# --- 통화에 넣을 문장 ---------------------------------------------------------

def action_guidance(window: Optional[str], sentences: list[str],
                    emergency: Optional[str] = None) -> str:
    """plan.actionGuidance — 어르신께 읽어 드릴 예방 안내 한 덩어리."""
    parts = []
    if emergency:
        parts.append(emergency)          # 응급 안내가 있으면 맨 앞
    if window:
        parts.append(f"{window} 더위가 가장 심합니다.")
    parts += [s.strip() for s in sentences if s and s.strip()]
    return " ".join(parts)


def shelter_recommendation_text(rec: Optional[dict]) -> Optional[str]:
    """plan.shelterRecommendationText — 쉼터가 없으면 None (문장을 지어내지 않는다).

    도보 시간은 TMAP 실측일 때만 말한다. 직선거리 폴백의 추정치를 여기 넣으면
    어르신이 '3분이면 가겠네' 하고 나섰다가 15분을 걷는다. 그 경우 대신
    안내 문장에 고정 고지문이 들어간다(rag/schemas.STRAIGHT_LINE_NOTICE).
    """
    if not rec or not rec.get("name"):
        return None
    # 시설명마다 받침이 달라 조사(로/으로)를 붙이면 어색해진다. 조사 없는 형태로 쓴다.
    text = f"가까운 무더위쉼터는 {rec['name']} 입니다."
    if rec.get("routeSource") == "TMAP" and rec.get("walkMinutes"):
        text += f" 걸어서 약 {rec['walkMinutes']}분 거리입니다."
    return text


def document_ids(chunk_ids: list[str]) -> list[str]:
    """plan.evidenceDocumentIds — 청크 id 가 아니라 **문서** id 를 준다.

    RAG 청크 id 는 `{document_id}__{index}` 형식이다 (heat_illness_manual_v1__0013).
    백엔드는 근거 문서 단위로 보관하므로 앞부분만 잘라 중복을 없앤다.
    """
    return list(dict.fromkeys(str(c).split("__")[0] for c in chunk_ids if c))


def transcript_ref(provider: str, call_id: Optional[str],
                   when: Optional[datetime] = None) -> Optional[str]:
    """원문이 아니라 접근 제어된 참조값만. 전사 텍스트는 어디에도 싣지 않는다."""
    if not call_id:
        return None
    d = (when or datetime.now(KST))
    return f"{provider.lower()}/{d:%Y/%m/%d}/{call_id}"


# --- 최종 출력 ---------------------------------------------------------------

def build_result(elderly_id: int, external_call_id: Optional[str], guidance: str,
                 shelter_text: Optional[str], questions: list[str], docs: list[str],
                 observation: dict, meta: dict) -> dict:
    """`POST /internal/v1/contact/results` 본문. 백엔드가 받는 건 이게 전부다."""
    ending = str(meta.get("call_ending") or "").upper()
    ended = dt(observation.get("ended_at"), "ended_at") or datetime.now(KST)
    return {
        "elderlyId": int(elderly_id),
        "externalCallId": external_call_id,
        "plan": {
            "actionGuidance": guidance,
            "shelterRecommendationText": shelter_text,
            "callQuestionOrder": list(questions),
            "evidenceDocumentIds": list(docs),
        },
        "call": {
            "answered": ending in ANSWERED_ENDINGS,
            "summary": str(observation.get("summary") or "")[:SUMMARY_MAX],
            "shelterIntent": ynu(observation.get("shelter_intent")),
            "canMoveAlone": ynu(observation.get("can_move_alone")),
            "helpNeeded": ynu(observation.get("help_needed")),
            "symptomMentioned": ynu(observation.get("symptom_mentioned")),
            "confidence": dec4(observation.get("confidence")),
            "transcriptRef": transcript_ref(meta.get("provider") or "clawops",
                                            meta.get("provider_call_id"), ended),
            "endedAt": utc_iso(ended),
        },
    }
