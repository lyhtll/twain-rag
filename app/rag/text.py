"""Text normalisation shared by indexing, duplicate detection, and citation checks.

These live in one place because the callers must agree. A tokenizer that differs
between corpus and query breaks BM25 with no error, and a normaliser that differs
between duplicate detection and quote verification makes the two judge by different
rules.
"""

import re

from app.core.config import settings
from app.models.chunk import Chunk

_PUNCT = re.compile(r"[^a-z0-9]+")
_WS = re.compile(r"\s+")

# The book uses curly quotes and en/em dashes. A model retyping a quote with straight
# ASCII is quoting correctly, not forging, so both sides are folded before comparison.
_FOLD = str.maketrans(
    {
        "‘": "'",
        "’": "'",
        "“": '"',
        "”": '"',
        "–": "-",
        "—": "-",
        "…": "...",
    }
)


def tokenize(text: str) -> list[str]:
    """Lowercase alphanumeric tokens. Used for BM25 on both corpus and query."""
    return [t for t in _PUNCT.split(text.lower()) if t]


def norm(text: str) -> str:
    """Collapse whitespace and fold typographic punctuation to ASCII."""
    return _WS.sub(" ", text.translate(_FOLD)).strip()


def doc_for(chunk: Chunk) -> str:
    """The string that gets indexed — same for BM25 and the embeddings.

    Ch1 and Ch3 titles are printed in the book and are real query terms ("Steamboat
    Pilot"). Ch2's title is a slice of its own text, so including it would count those
    characters twice and weight the opening clause. Index printed titles, never derived
    ones.

    Ch2 gets an attribution frame instead. bge-small encodes sentence *form* as well as
    content, and this book's chapters differ in form: an interrogative query moves toward
    Ch1's narrative prose and Ch3's Q&A (mean cosine +0.18) while Ch2's bare aphorisms do
    not move at all, so a question about a quotation lands far from its own answer.
    Framing the quotation as reported speech closes that gap — measured on ten ad-hoc Ch2
    questions, the median dense rank of the correct chunk goes 2 -> 1 and the worst cases
    collapse (96 -> 1, 21 -> 3, 9 -> 1, 5 -> 1), with every Ch1/Ch3 rank unchanged.

    Only the indexed string changes. `chunk.text`, the title, the page span and the quote
    verification all read the printed text, so citations are untouched.
    """
    if chunk.chapter == 2:
        return settings.ch2_index_prefix + chunk.text
    return f"{chunk.title}\n{chunk.text}"
