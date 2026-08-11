"""Hybrid retrieval: BM25 + dense, fused with RRF, then near-duplicates collapsed.

Both rank lists are kept in the returned `Hit`s. That is deliberate: failure analysis
asks "did BM25 miss it, or the dense side?", and a fused list alone cannot answer it.
"""

from collections import defaultdict

from app.core.config import settings
from app.models.chunk import Chunk, Hit
from app.rag.indexer import Embedder, Index


def fuse(
    bm25_ranked: list[str],
    dense_ranked: list[str],
    method: str = "rrf",
    weight: float = 0.5,
    k: int = settings.rrf_k,
) -> list[tuple[str, float]]:
    """Combine two ranked id lists into one.

    `rrf` — reciprocal rank fusion, `Σ 1/(k + rank)`. Needs no score normalisation,
    which is why it is the default: with only ~10 candidates per side, min-max
    normalisation has a tiny denominator and the resulting order is unstable.

    `cc` — convex combination of positions normalised to 0..1, kept only so
    `scripts/compare_fusion.py` can measure the two against the frozen question set.
    Note this is **not** Type4: it normalises *ranks*, not scores, so like RRF it discards
    score magnitude. Day 5 measured a true score-based variant separately and found it is
    the one that recovers the two failures diagnosed in docs/NOTES.md — see that memo.
    `method` stays a local argument; it is deliberately not threaded through the
    retriever, the API, or config, because a switch with one production value is dead
    flexibility.
    """
    if method == "rrf":
        scores: dict[str, float] = defaultdict(float)
        for ranked in (bm25_ranked, dense_ranked):
            for rank, chunk_id in enumerate(ranked, start=1):
                scores[chunk_id] += 1.0 / (k + rank)
    elif method == "cc":
        bm25_scores = _rank_to_normalised(bm25_ranked)
        dense_scores = _rank_to_normalised(dense_ranked)
        scores = defaultdict(float)
        for chunk_id in set(bm25_ranked) | set(dense_ranked):
            scores[chunk_id] = weight * bm25_scores.get(chunk_id, 0.0) + (1 - weight) * dense_scores.get(
                chunk_id, 0.0
            )
    else:
        raise ValueError(f"unknown fusion method {method!r}")

    return sorted(scores.items(), key=lambda kv: -kv[1])


def _rank_to_normalised(ranked: list[str]) -> dict[str, float]:
    """1.0 for the top hit down to 0.0 for the last, by position."""
    if len(ranked) <= 1:
        return {chunk_id: 1.0 for chunk_id in ranked}
    last = len(ranked) - 1
    return {chunk_id: 1.0 - rank / last for rank, chunk_id in enumerate(ranked)}


def collapse_duplicates(
    fused: list[tuple[str, float]], by_id: dict[str, Chunk]
) -> list[tuple[str, float]]:
    """Drop a chunk when a better-scoring kept chunk retells the same passage.

    Links are pairwise rather than a shared group id, so this only ever drops a chunk
    against a specific chunk that names it. Two unrelated Ch1 anecdotes that happen to
    appear inside the same Ch3 block both survive.
    """
    kept: list[tuple[str, float]] = []
    dropped: set[str] = set()
    for chunk_id, score in fused:
        if chunk_id in dropped:
            continue
        kept.append((chunk_id, score))
        dropped.update(by_id[chunk_id].duplicates)
    return kept


class HybridRetriever:
    def __init__(self, index: Index, embedder: Embedder | None = None) -> None:
        # The index is injected, never loaded here: `get_index()` caches one per process,
        # and loading it per request would reload a 133MB model every time.
        self._index = index
        self._embedder = embedder or Embedder()

    def search(
        self,
        question: str,
        top_k: int = settings.top_k,
        candidates: int = settings.candidates,
    ) -> list[Hit]:
        bm25_ranked = self._index.search_bm25(question, candidates)
        dense_ranked = self._index.search_dense(self._embedder.embed_query(question), candidates)

        bm25_rank = {chunk_id: i for i, chunk_id in enumerate(bm25_ranked, start=1)}
        dense_rank = {chunk_id: i for i, chunk_id in enumerate(dense_ranked, start=1)}

        fused = fuse(bm25_ranked, dense_ranked)
        for chunk_id, _ in fused:
            if chunk_id not in self._index.by_id:
                raise ValueError(f"index returned unknown chunk id {chunk_id!r}")

        return [
            Hit(
                chunk=self._index.by_id[chunk_id],
                bm25_rank=bm25_rank.get(chunk_id),
                dense_rank=dense_rank.get(chunk_id),
                fused=score,
            )
            for chunk_id, score in collapse_duplicates(fused, self._index.by_id)[:top_k]
        ]
