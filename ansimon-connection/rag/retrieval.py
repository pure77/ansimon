# -*- coding: utf-8 -*-
"""2) 검색

TF-IDF(문자 n-gram) + 코사인 유사도 기반 검색기.
한국어 형태소 분석기 없이도 동작하도록 char n-gram을 사용해
오프라인/제약 환경에서도 안정적으로 실행된다.

대상자 태그로 1차 필터링(해당 대상자 + GENERAL + EMERGENCY 청크로 후보를 좁힘) 후
질의 유사도로 재정렬한다. 예를 들어 노인 프로필이면 heading_path에 "노인"이 걸린
청크(ELDERLY 태그)가 후보 풀에 남아 우선적으로 검색된다.

인터페이스(search 함수의 시그니처)가 구현(TF-IDF)과 분리돼 있어, 운영 단계에서
문장 임베딩 + 벡터DB로 교체해도 pipeline.py는 수정할 필요가 없다.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

BASE_DIR = Path(__file__).resolve().parent
CHUNKS_PATH = BASE_DIR / "out" / "chunks.jsonl"


@dataclass
class RetrievedChunk:
    chunk_id: str
    document_id: str
    text: str
    heading_path: list[str]
    target_audience: list[str]
    page_number: Optional[int]
    score: float = field(default=0.0)


def load_active_chunks(chunks_path: Path = CHUNKS_PATH) -> list[dict]:
    if not chunks_path.exists():
        raise FileNotFoundError(
            f"{chunks_path} 가 없습니다. 먼저 ingest.py를 실행해 청크를 생성하세요."
        )
    with chunks_path.open(encoding="utf-8") as f:
        chunks = [json.loads(line) for line in f if line.strip()]
    return [c for c in chunks if c.get("active", True)]


def _filter_by_audience(chunks: list[dict], target_audience: Optional[list[str]]) -> list[dict]:
    if not target_audience:
        return chunks
    allowed = set(target_audience) | {"GENERAL", "EMERGENCY"}
    filtered = [c for c in chunks if allowed & set(c["target_audience"])]
    return filtered if filtered else chunks


def search(
    query: str,
    target_audience: Optional[list[str]] = None,
    top_k: int = 5,
    chunks: Optional[list[dict]] = None,
) -> list[RetrievedChunk]:
    """질의(query)에 가장 관련 있는 청크 top_k개를 반환한다."""
    pool = chunks if chunks is not None else load_active_chunks()
    pool = _filter_by_audience(pool, target_audience)
    if not pool:
        return []

    corpus = [c["text"] for c in pool]
    vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), min_df=1)
    doc_matrix = vectorizer.fit_transform(corpus)
    query_vec = vectorizer.transform([query])

    scores = cosine_similarity(query_vec, doc_matrix)[0]
    ranked_idx = sorted(range(len(pool)), key=lambda i: scores[i], reverse=True)

    results: list[RetrievedChunk] = []
    for i in ranked_idx[:top_k]:
        c = pool[i]
        results.append(
            RetrievedChunk(
                chunk_id=c["chunk_id"],
                document_id=c["document_id"],
                text=c["text"],
                heading_path=c["heading_path"],
                target_audience=c["target_audience"],
                page_number=c.get("page_number"),
                score=float(scores[i]),
            )
        )
    return results


if __name__ == "__main__":
    demo_queries = [
        ("노인 폭염 대비 수칙 알려줘", ["ELDERLY"]),
        ("실외에서 일하는 사람 온열질환 예방", ["OUTDOOR_WORKER"]),
        ("의식을 잃었을 때 응급조치", ["EMERGENCY"]),
    ]
    for query, audience in demo_queries:
        print(f"\n=== query='{query}' target_audience={audience} ===")
        for r in search(query, target_audience=audience, top_k=3):
            print(f"  [{r.score:.3f}] {r.chunk_id} {r.heading_path} | {r.text[:50]}")
