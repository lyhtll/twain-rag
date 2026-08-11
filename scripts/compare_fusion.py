"""One-off: RRF vs convex combination, on retrieval only.

    python -m scripts.compare_fusion

No model calls — this measures which chunks reach top-3, not what is answered, so it is
free and repeatable. Two sets are reported:

- the **frozen** question set, which is what the memo quotes;
- the **diagnostic** probes written after the frozen run, where two answerable questions
  were lost. Those two are the reason this comparison stopped being a curiosity: RRF
  discards score magnitude, and both failures were a strong single-list hit losing to two
  mediocre both-list hits.

Nothing here changes production. `fuse()` stays on RRF: the frozen set had already been
run when these numbers were taken, and changing retrieval after seeing the score is the
one thing the freeze exists to prevent.
"""

import sys

import yaml

from app.core.config import settings
from app.rag.indexer import Embedder, Index
from app.rag.retriever import collapse_duplicates, fuse
from eval.report import QUESTIONS, evidence_hit

# Answerable question -> the chunk that answers it. Written after the frozen run, so these
# are a diagnostic, never part of the graded score.
DIAGNOSTIC = [
    (
        "Which of his host's household devices did Twain silence because he thought "
        "they were overworked?",
        "c0029",
    ),
    ("How many different explanations does this book give for the name 'Mark Twain'?", "c0178"),
    ("What does the book record about Twain and profanity?", "c0018"),
    ("What does the book say about Twain and advertising?", "c0072"),
]


def top_ids(index: Index, embedder: Embedder, question: str, method: str, weight: float) -> list[str]:
    bm25 = index.search_bm25(question, settings.candidates)
    dense = index.search_dense(embedder.embed_query(question), settings.candidates)
    fused = fuse(bm25, dense, method=method, weight=weight)
    kept = collapse_duplicates(fused, index.by_id)[: settings.top_k]
    return [chunk_id for chunk_id, _ in kept]


def main() -> int:
    index = Index.load()
    embedder = Embedder()
    questions = yaml.safe_load(QUESTIONS.read_text(encoding="utf-8"))
    answerable = [q for q in questions if q["kind"] != "absent"]

    variants = [("rrf", 0.5), ("cc", 0.5), ("cc", 0.3), ("cc", 0.7)]
    print(f"{'variant':<12} {'frozen top-3':>14} {'diagnostic top-3':>18}")
    for method, weight in variants:
        frozen = 0
        for question in answerable:
            ids = top_ids(index, embedder, question["question"], method, weight)
            ok, _ = evidence_hit(question["evidence"], [index.by_id[i] for i in ids])
            frozen += ok
        diag = sum(
            want in top_ids(index, embedder, question, method, weight)
            for question, want in DIAGNOSTIC
        )
        label = method if method == "rrf" else f"cc w={weight}"
        print(f"{label:<12} {frozen:>10}/{len(answerable)} {diag:>14}/{len(DIAGNOSTIC)}")

    print("\nper-question, diagnostic set (rank of the expected chunk in each list):")
    for question, want in DIAGNOSTIC:
        bm25 = index.search_bm25(question, settings.candidates)
        dense = index.search_dense(embedder.embed_query(question), settings.candidates)
        b = bm25.index(want) + 1 if want in bm25 else None
        d = dense.index(want) + 1 if want in dense else None
        rrf_in = want in top_ids(index, embedder, question, "rrf", 0.5)
        cc_in = want in top_ids(index, embedder, question, "cc", 0.5)
        print(
            f"  {want}  bm25={str(b):<5} dense={str(d):<5} "
            f"rrf_top3={'O' if rrf_in else 'X'}  cc_top3={'O' if cc_in else 'X'}   {question[:46]}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
