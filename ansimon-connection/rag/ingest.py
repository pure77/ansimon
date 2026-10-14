# -*- coding: utf-8 -*-
"""1) 문서 수집·청킹

원본 PDF(질병관리청 「대상자별 온열질환 예방 매뉴얼」)를 읽어
- 문서 메타데이터(제목/기관/발행일/원문 URL/적용대상)를 out/documents.json에,
- 의미 단위 청크(문단/목록 분리 + heading_path + target_audience 자동 태깅)를
  out/chunks.jsonl에 저장한다.

문서 구조 규칙(원문 PDF 작성 규칙과 1:1로 대응):
  "■ N. 제목"        -> 대분류 제목 (heading_path[0])
  "▶ 대상자: 이름"    -> 대상자별 소제목 (heading_path[1], 자동 태깅의 1차 근거)
  "• 텍스트"          -> 목록(불릿) 항목 -> 항목 단위 청크
  "N) 텍스트"         -> 목록(번호) 항목 -> 항목 단위 청크
  그 외 줄            -> 문단 텍스트(줄바꿈으로 끊긴 문장은 공백으로 재결합 후 청크화)

재실행 시 기존 문서/청크를 삭제하지 않고 active=False 로 비활성화한 뒤 새 버전을
active=True 로 추가한다 (삭제 대신 이력 보존).
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pypdf import PdfReader

from schemas import TargetAudience

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_PDF_PATH = BASE_DIR / "data" / "heat_illness_manual.pdf"
DOCUMENTS_PATH = BASE_DIR / "out" / "documents.json"
CHUNKS_PATH = BASE_DIR / "out" / "chunks.jsonl"

H1_RE = re.compile(r"^■\s*(\d+)\.\s*(.+)$")
H2_RE = re.compile(r"^▶\s*대상자\s*:\s*(.+)$")
BULLET_RE = re.compile(r"^[•\-]\s*(.+)$")
NUMBERED_RE = re.compile(r"^(\d+)\)\s*(.+)$")

META_LABEL_RE = re.compile(r"^(발행기관|발행일|적용대상|원문\s*URL[^:]*)\s*:\s*(.+)$")
URL_RE = re.compile(r"https?://\S+")

# 소제목("▶ 대상자: X")에 쓰인 표현 -> target_audience enum 1차 매핑
AUDIENCE_LABEL_MAP = {
    "노인": TargetAudience.ELDERLY,
    "임신부": TargetAudience.PREGNANT,
    "장애인": TargetAudience.DISABLED,
    "심뇌혈관질환자": TargetAudience.CARDIOVASCULAR,
    "신장질환자": TargetAudience.RENAL,
    "혈압질환자": TargetAudience.BLOOD_PRESSURE,
    "당뇨질환자": TargetAudience.DIABETES,
    "실외근로자": TargetAudience.OUTDOOR_WORKER,
    "어린이": TargetAudience.CHILD,
}

# 본문 어디서든 이 키워드가 등장하면 태그를 보강한다 (구조와 독립적인 2차 태깅).
KEYWORD_AUDIENCE_MAP = {
    "노인": TargetAudience.ELDERLY,
    "고령": TargetAudience.ELDERLY,
    "임신부": TargetAudience.PREGNANT,
    "태아": TargetAudience.PREGNANT,
    "장애인": TargetAudience.DISABLED,
    "휠체어": TargetAudience.DISABLED,
    "심뇌혈관": TargetAudience.CARDIOVASCULAR,
    "심장": TargetAudience.CARDIOVASCULAR,
    "신장질환": TargetAudience.RENAL,
    "혈압": TargetAudience.BLOOD_PRESSURE,
    "당뇨": TargetAudience.DIABETES,
    "혈당": TargetAudience.DIABETES,
    "실외근로자": TargetAudience.OUTDOOR_WORKER,
    "옥외작업": TargetAudience.OUTDOOR_WORKER,
    "어린이": TargetAudience.CHILD,
    "119": TargetAudience.EMERGENCY,
    "응급": TargetAudience.EMERGENCY,
}


def _extract_lines(pdf_path: Path) -> list[tuple[int, str]]:
    """(1-indexed page_number, stripped line text) 리스트. 빈 줄은 제외."""
    reader = PdfReader(str(pdf_path))
    lines: list[tuple[int, str]] = []
    for page_idx, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        for raw_line in text.split("\n"):
            line = raw_line.strip()
            if line:
                lines.append((page_idx, line))
    return lines


def _auto_tag(text: str, h1: Optional[str], h2: Optional[str]) -> list[str]:
    tags: set[TargetAudience] = set()
    if h2 and h2 in AUDIENCE_LABEL_MAP:
        tags.add(AUDIENCE_LABEL_MAP[h2])
    if h1 and "응급" in h1:
        tags.add(TargetAudience.EMERGENCY)
    for keyword, tag in KEYWORD_AUDIENCE_MAP.items():
        if keyword in text:
            tags.add(tag)
    if not tags:
        tags.add(TargetAudience.GENERAL)
    return sorted(t.value for t in tags)


def _parse_pdf(pdf_path: Path) -> tuple[dict, list[dict]]:
    lines = _extract_lines(pdf_path)

    title: Optional[str] = None
    meta: dict[str, str] = {}
    h1: Optional[str] = None
    h2: Optional[str] = None

    raw_chunks: list[dict] = []
    para_buffer: list[str] = []
    para_page: Optional[int] = None

    def flush_paragraph():
        nonlocal para_buffer, para_page
        if para_buffer:
            text = " ".join(para_buffer).strip()
            if text:
                raw_chunks.append(
                    {
                        "content_type": "paragraph",
                        "text": text,
                        "heading_path": [h for h in (h1, h2) if h],
                        "page_number": para_page,
                    }
                )
        para_buffer = []
        para_page = None

    content_started = False
    for page_num, line in lines:
        is_structural = bool(H1_RE.match(line) or H2_RE.match(line))
        if not content_started and not is_structural:
            # 표지 영역: 라벨:값 메타데이터 또는 제목 후보로만 취급하고
            # 청크 스트림에는 포함하지 않는다.
            meta_match = META_LABEL_RE.match(line)
            if meta_match:
                label, value = meta_match.group(1), meta_match.group(2)
                if label.startswith("발행기관"):
                    meta["organization"] = value.strip()
                elif label.startswith("발행일"):
                    meta["published_date"] = value.strip()
                elif label.startswith("적용대상"):
                    meta["target_audience_note"] = value.strip()
                elif label.startswith("원문"):
                    url_match = URL_RE.search(value)
                    meta["source_url"] = url_match.group(0) if url_match else value.strip()
            elif title is None:
                title = line
            continue

        content_started = True

        h1_match = H1_RE.match(line)
        if h1_match:
            flush_paragraph()
            h1 = f"{h1_match.group(1)}. {h1_match.group(2)}"
            h2 = None
            continue

        h2_match = H2_RE.match(line)
        if h2_match:
            flush_paragraph()
            h2 = h2_match.group(1).strip()
            continue

        bullet_match = BULLET_RE.match(line)
        if bullet_match:
            flush_paragraph()
            raw_chunks.append(
                {
                    "content_type": "bullet",
                    "text": bullet_match.group(1).strip(),
                    "heading_path": [h for h in (h1, h2) if h],
                    "page_number": page_num,
                }
            )
            continue

        num_match = NUMBERED_RE.match(line)
        if num_match:
            flush_paragraph()
            raw_chunks.append(
                {
                    "content_type": "numbered",
                    "text": num_match.group(2).strip(),
                    "heading_path": [h for h in (h1, h2) if h],
                    "page_number": page_num,
                }
            )
            continue

        # 일반 문단 줄: 줄바꿈으로 끊긴 문장을 이어 붙이기 위해 버퍼에 누적
        if para_page is None:
            para_page = page_num
        para_buffer.append(line)

    flush_paragraph()

    document_meta = {
        "title": title or pdf_path.stem,
        "organization": meta.get("organization", "미상"),
        "published_date": meta.get("published_date", "미상"),
        "source_url": meta.get("source_url", ""),
        "target_audience_note": meta.get("target_audience_note", ""),
    }
    return document_meta, raw_chunks


def _next_version(existing_documents: list[dict], slug: str) -> int:
    versions = [
        d["version"]
        for d in existing_documents
        if d["document_id"].rsplit("_v", 1)[0] == slug
    ]
    return (max(versions) if versions else 0) + 1


def ingest_document(pdf_path: Optional[Path] = None) -> dict:
    pdf_path = Path(pdf_path) if pdf_path else DEFAULT_PDF_PATH
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF를 찾을 수 없습니다: {pdf_path}")

    DOCUMENTS_PATH.parent.mkdir(parents=True, exist_ok=True)

    existing_documents: list[dict] = []
    if DOCUMENTS_PATH.exists():
        existing_documents = json.loads(DOCUMENTS_PATH.read_text(encoding="utf-8"))

    existing_chunks: list[dict] = []
    if CHUNKS_PATH.exists():
        with CHUNKS_PATH.open(encoding="utf-8") as f:
            existing_chunks = [json.loads(line) for line in f if line.strip()]

    slug = re.sub(r"[^a-zA-Z0-9]+", "_", pdf_path.stem).strip("_").lower()
    version = _next_version(existing_documents, slug)
    document_id = f"{slug}_v{version}"

    document_meta, raw_chunks = _parse_pdf(pdf_path)
    ingested_at = datetime.now(timezone.utc).isoformat()

    all_audience_tags: set[str] = set()
    new_chunks: list[dict] = []
    for idx, rc in enumerate(raw_chunks):
        tags = _auto_tag(rc["text"], rc["heading_path"][0] if rc["heading_path"] else None,
                          rc["heading_path"][1] if len(rc["heading_path"]) > 1 else None)
        all_audience_tags.update(tags)
        new_chunks.append(
            {
                "chunk_id": f"{document_id}__{idx:04d}",
                "document_id": document_id,
                "chunk_index": idx,
                "content_type": rc["content_type"],
                "text": rc["text"],
                "heading_path": rc["heading_path"],
                "target_audience": tags,
                "page_number": rc["page_number"],
                "active": True,
            }
        )

    # 같은 문서(slug)의 이전 버전은 삭제 대신 비활성화해 이력을 보존한다.
    for d in existing_documents:
        if d["document_id"].rsplit("_v", 1)[0] == slug:
            d["active"] = False
    for c in existing_chunks:
        if c["document_id"].rsplit("_v", 1)[0] == slug:
            c["active"] = False

    new_document = {
        "document_id": document_id,
        "slug": slug,
        "version": version,
        "title": document_meta["title"],
        "organization": document_meta["organization"],
        "published_date": document_meta["published_date"],
        "source_url": document_meta["source_url"],
        "target_audience_note": document_meta["target_audience_note"],
        "target_audience_scope": sorted(all_audience_tags),
        "file_path": str(pdf_path.relative_to(BASE_DIR)),
        "chunk_count": len(new_chunks),
        "ingested_at": ingested_at,
        "active": True,
    }

    all_documents = existing_documents + [new_document]
    all_chunks = existing_chunks + new_chunks

    DOCUMENTS_PATH.write_text(
        json.dumps(all_documents, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with CHUNKS_PATH.open("w", encoding="utf-8") as f:
        for c in all_chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    return {
        "document_id": document_id,
        "chunk_count": len(new_chunks),
        "total_chunks_in_store": len(all_chunks),
        "target_audience_scope": new_document["target_audience_scope"],
    }


if __name__ == "__main__":
    summary = ingest_document()
    print(f"[ingest] document_id={summary['document_id']}")
    print(f"[ingest] 이번 인입 청크 수: {summary['chunk_count']}건")
    print(f"[ingest] 저장소 전체 청크 수(비활성 포함): {summary['total_chunks_in_store']}건")
    print(f"[ingest] 대상자 태그 범위: {summary['target_audience_scope']}")
