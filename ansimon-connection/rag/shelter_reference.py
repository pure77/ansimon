# -*- coding: utf-8 -*-
"""5-1) 쉼터 실존 검증 - 서울 열린데이터광장 원천 데이터 로더/조회 인덱스

evidence_verifier.py가 "안내 계획에 포함된 쉼터가 실제로 존재하는 시설인가"를
교차 검증할 때 쓰는 조회 인덱스. data.seoul.go.kr의 다운로드 버튼이 자바스크립트
트리거라 자동 수집이 불가능하므로, 팀원이 직접 받은 .xlsx를 data/ 아래 정해진
이름으로 저장하면 load_default_index()가 이를 우선 로드하고, 없으면
fixtures/sample_seoul_shelters.csv(예시 구조, 실제 데이터 아님)로 폴백한다.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent
FIXTURE_CSV_PATH = BASE_DIR / "fixtures" / "sample_seoul_shelters.csv"

# data/ 아래 이 이름으로 저장하면 자동으로 실데이터로 전환된다.
DEFAULT_XLSX_SOURCES = {
    "SMART_SHELTER": "서울시_스마트쉼터_현황.xlsx",
    "SHADE_CANOPY": "서울시_그늘막_현황.xlsx",
    "COOLING_FOG": "서울시_쿨링포그_현황.xlsx",
    "HEAT_SHELTER": "서울시_무더위쉼터_현황.xlsx",
}

# 서울 열린데이터광장 원천 파일의 흔한 컬럼명 후보 (데이터셋마다 표기가 조금씩 다름)
COLUMN_CANDIDATES = {
    "gu": ["자치구", "자치구명", "시군구", "구", "구분"],
    "facility_name": ["시설명", "명칭", "쉼터명", "설치대상명"],
    "install_location": ["설치장소", "위치", "설치위치"],
    "address": ["상세주소", "주소", "소재지", "소재지도로명주소", "지번주소"],
    "install_year": ["설치년도", "설치연도", "준공년도"],
}


def _normalize(text: Optional[str]) -> str:
    if not text:
        return ""
    return "".join(str(text).split()).lower()


def _pick_column(columns: list[str], candidates: list[str]) -> Optional[str]:
    for cand in candidates:
        if cand in columns:
            return cand
    return None


@dataclass(frozen=True)
class ShelterRecord:
    gu: str
    facility_type: str
    facility_name: str
    install_location: str
    address: str
    install_year: str
    source_dataset: str


class ShelterReferenceIndex:
    def __init__(self, records: Optional[list[ShelterRecord]] = None):
        self.records: list[ShelterRecord] = records or []

    def __len__(self) -> int:
        return len(self.records)

    def extend(self, other: "ShelterReferenceIndex") -> None:
        self.records.extend(other.records)

    @classmethod
    def load_from_csv(cls, path: Path, source_dataset: Optional[str] = None) -> "ShelterReferenceIndex":
        records = []
        with Path(path).open(encoding="utf-8") as f:
            for row in csv.DictReader(f):
                records.append(
                    ShelterRecord(
                        gu=row.get("gu", ""),
                        facility_type=row.get("facility_type", ""),
                        facility_name=row.get("facility_name", ""),
                        install_location=row.get("install_location", ""),
                        address=row.get("address", ""),
                        install_year=row.get("install_year", ""),
                        source_dataset=source_dataset or row.get("source_dataset", ""),
                    )
                )
        return cls(records)

    @classmethod
    def load_from_xlsx(
        cls,
        path: Path,
        facility_type: str,
        source_dataset: str,
        sheet_name: int | str = 0,
    ) -> "ShelterReferenceIndex":
        import pandas as pd

        df = pd.read_excel(path, sheet_name=sheet_name, dtype=str).fillna("")
        columns = list(df.columns)
        col_map = {
            key: _pick_column(columns, candidates)
            for key, candidates in COLUMN_CANDIDATES.items()
        }

        records = []
        for _, row in df.iterrows():
            records.append(
                ShelterRecord(
                    gu=str(row[col_map["gu"]]) if col_map["gu"] else "",
                    facility_type=facility_type,
                    facility_name=str(row[col_map["facility_name"]]) if col_map["facility_name"] else "",
                    install_location=str(row[col_map["install_location"]]) if col_map["install_location"] else "",
                    address=str(row[col_map["address"]]) if col_map["address"] else "",
                    install_year=str(row[col_map["install_year"]]) if col_map["install_year"] else "",
                    source_dataset=source_dataset,
                )
            )
        return cls(records)

    def find_by_name_or_address(self, query: str, limit: int = 5, min_score: float = 0.35) -> list[ShelterRecord]:
        """느슨한 문자열 매칭(부분 문자열 우선, 없으면 유사도)으로 후보를 찾는다."""
        nq = _normalize(query)
        if not nq:
            return []

        scored: list[tuple[float, ShelterRecord]] = []
        for r in self.records:
            name_n = _normalize(r.facility_name)
            addr_n = _normalize(r.address)
            loc_n = _normalize(r.install_location)
            if nq in name_n or nq in addr_n or nq in loc_n or name_n in nq:
                score = 1.0
            else:
                score = max(
                    SequenceMatcher(None, nq, name_n).ratio(),
                    SequenceMatcher(None, nq, addr_n).ratio(),
                )
            if score >= min_score:
                scored.append((score, r))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [r for _, r in scored[:limit]]

    def exists(self, name: str, address: Optional[str] = None,
               min_score: float = 0.6) -> bool:
        """이 시설이 원천 데이터에 있는가. 근거검증(SHELTER_NOT_FOUND)의 판정 기준.

        find_by_name_or_address 를 그대로 쓰면 안 된다. 그쪽은 "이름 + 주소"를 한 덩어리로
        이어붙여 유사도를 재는데, 질의가 길어질수록 아무 레코드와도 0.35 를 넘겨버린다.
        실제로 "가상의쉼터12345 서울특별시 어딘가 999" 가 "가산동 마을회관" 에 매칭돼
        존재하지 않는 쉼터가 검증을 통과했다. 여기서는 **시설명끼리만** 비교하고
        기준도 0.6 으로 올린다. 주소는 이름이 애매할 때의 보조 신호로만 쓴다.
        """
        nq = _normalize(name)
        if not nq:
            return False
        aq = _normalize(address)

        for r in self.records:
            fn, loc, ad = (_normalize(r.facility_name), _normalize(r.install_location),
                           _normalize(r.address))
            if fn and (nq in fn or fn in nq or SequenceMatcher(None, nq, fn).ratio() >= min_score):
                return True
            if loc and (nq in loc or loc in nq):
                return True
            # 이름을 못 찾아도 주소가 정확히 일치하면 같은 시설로 본다
            if aq and ad and (aq in ad or ad in aq):
                return True
        return False


def load_default_index(base_dir: Path = BASE_DIR) -> ShelterReferenceIndex:
    """data/ 아래 실데이터 xlsx가 있으면 그것을, 없으면 샘플 CSV를 로드한다."""
    data_dir = base_dir / "data"
    facility_type_by_key = {
        "SMART_SHELTER": "스마트쉼터",
        "SHADE_CANOPY": "그늘막",
        "COOLING_FOG": "쿨링포그",
        "HEAT_SHELTER": "무더위쉼터",
    }

    index = ShelterReferenceIndex()
    found_any = False
    for key, filename in DEFAULT_XLSX_SOURCES.items():
        xlsx_path = data_dir / filename
        if xlsx_path.exists():
            found_any = True
            index.extend(
                ShelterReferenceIndex.load_from_xlsx(
                    xlsx_path,
                    facility_type=facility_type_by_key[key],
                    source_dataset=key,
                )
            )

    if found_any:
        return index

    return ShelterReferenceIndex.load_from_csv(FIXTURE_CSV_PATH, source_dataset="SAMPLE_NOT_REAL")


if __name__ == "__main__":
    idx = load_default_index()
    print(f"[shelter_reference] 로드된 레코드 수: {len(idx)}")
    for query in ["종로노인종합복지관", "잠실역", "존재하지않는가짜쉼터12345"]:
        hits = idx.find_by_name_or_address(query)
        print(f"query='{query}' -> exists={idx.exists(query)}, hits={[h.facility_name for h in hits]}")
