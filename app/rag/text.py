"""Text normalisation shared by indexing, duplicate detection, and citation checks.

These live in one place because the callers must agree. A tokenizer that differs
between corpus and query breaks BM25 with no error, and a normaliser that differs
between duplicate detection and quote verification makes the two judge by different
rules.
"""

import re

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
    """
    return chunk.text if chunk.chapter == 2 else f"{chunk.title}\n{chunk.text}"
