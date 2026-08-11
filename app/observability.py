"""One-line-per-query run log — the backbone of the failure analysis.

Both rank lists are recorded separately. "Did BM25 miss it or did the dense side?" is
the question that separates a chunking failure from a retrieval failure, and a fused
list alone cannot answer it. Rejected citations are recorded too: those are
generation-stage findings.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

from app.core.config import settings
from app.models.agent import Citation
from app.models.chunk import Hit
from app.models.schemas.ask import AskResponse


def log_run(
    question: str,
    hits: list[Hit],
    response: AskResponse,
    rejected: list[Citation] | None = None,
    directory: Path = settings.runs_dir,
    question_id: str | None = None,
) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    now = datetime.now(UTC)
    record = {
        "ts": now.isoformat(),
        "question_id": question_id,
        "question": question,
        "retrieved": [
            {
                "id": hit.chunk.id,
                "chapter": hit.chunk.chapter,
                "pages": hit.chunk.page_label,
                "bm25_rank": hit.bm25_rank,
                "dense_rank": hit.dense_rank,
                "fused": round(hit.fused, 6),
            }
            for hit in hits
        ],
        "answer": response.text,
        "refused": response.refused,
        "sources": [s.model_dump() for s in response.sources],
        "rejected_citations": [c.model_dump() for c in (rejected or [])],
    }
    path = directory / f"{now:%Y-%m-%d}.jsonl"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
