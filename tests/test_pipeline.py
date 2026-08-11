"""Runs with no API key, no PDF, and no embedding model.

Anything that needs the real book is a manual check (see docs/NOTES.md), not a test.
"""

import pytest

from app.rag.extractor import PdfExtractor


class FakePage:
    """Stands in for a pymupdf.Page.

    Each positional argument is one PyMuPDF *block*, which in this book is one printed
    paragraph — that grouping is what Ch2 chunking reads. Rows are
    (text, bold, y_top, x_left, x_right); x_left is real geometry, not padding, because
    the extractor orders same-baseline fragments by it.
    """

    def __init__(self, *blocks: list[tuple[str, bool, float, float, float]]) -> None:
        self._blocks = blocks

    def get_text(self, kind: str, flags: int | None = None) -> dict:
        assert kind == "dict"
        return {
            "blocks": [
                {
                    "lines": [
                        {
                            "bbox": (xl, y, xr, y + 12.0),
                            "spans": [
                                {
                                    "text": text,
                                    "font": "ABCDEF+TimesNewRomanPS-BoldMT"
                                    if bold
                                    else "ABCDEF+TimesNewRomanPSMT",
                                }
                            ],
                        }
                        for text, bold, y, xl, xr in rows
                    ]
                }
                for rows in self._blocks
            ]
        }


class FakeDoc:
    def __init__(self, pages: list[FakePage]) -> None:
        self._pages = pages

    def __len__(self) -> int:
        return len(self._pages)

    def __getitem__(self, i: int) -> FakePage:
        return self._pages[i]


def _body_page(printed: int) -> FakePage:
    """A content page: numeric header on top, then a bold heading and body text."""
    return FakePage(
        [
            (str(printed), False, 36.4, 200.0, 220.0),
            ("Spelling", True, 94.2, 72.0, 119.3),
            ("When Samuel Langhorne Clemens was a schoolboy, he", False, 116.0, 72.0, 363.0),
        ]
    )


def _front_matter() -> FakePage:
    return FakePage([("TABLE OF CONTENTS", False, 72.3, 100.0, 300.0)])


def test_page_header_is_parsed_and_stripped():
    pages = PdfExtractor(doc=FakeDoc([_body_page(27)])).parse()
    assert pages[0].printed == 27
    assert [ln.text for ln in pages[0].lines] == [
        "Spelling",
        "When Samuel Langhorne Clemens was a schoolboy, he",
    ], "the page-number line must not leak into the body"


def test_page_without_numeric_header_has_no_printed_number():
    pages = PdfExtractor(doc=FakeDoc([_front_matter()])).parse()
    assert pages[0].printed is None


def test_bold_flag_marks_headings_only():
    page = PdfExtractor(doc=FakeDoc([_body_page(1)])).parse()[0]
    assert [ln.bold for ln in page.lines] == [True, False]


def test_lines_are_sorted_top_to_bottom():
    doc = FakeDoc([FakePage([("second", False, 200.0, 72.0, 300.0), ("first", False, 100.0, 72.0, 300.0)])])
    page = PdfExtractor(doc=doc).parse()[0]
    assert [ln.text for ln in page.lines] == ["first", "second"]


def test_word_fragments_on_one_baseline_are_merged():
    """PyMuPDF splits wide-set justified lines into one entry per word.

    Left unmerged, `x_right` would describe a word rather than the line — the exact
    signal Ch2 paragraph detection reads.
    """
    doc = FakeDoc(
        [
            FakePage(
                [
                    ("of", False, 269.87, 260.8, 273.8),  # deliberately out of x order
                    ("Humorist", False, 269.87, 72.0, 120.3),
                    ("Mark", False, 269.9, 130.6, 159.6),  # 0.03pt off the baseline
                    ("Huckleberry Finn, once stayed at the home", False, 283.79, 72.0, 363.0),
                ]
            )
        ]
    )
    page = PdfExtractor(doc=doc).parse()[0]
    assert [ln.text for ln in page.lines] == [
        "Humorist Mark of",
        "Huckleberry Finn, once stayed at the home",
    ]
    assert page.lines[0].x_right == 273.8, "merged line keeps the rightmost edge"


def test_bold_survives_a_merge():
    doc = FakeDoc([FakePage([("What was Mark", True, 100.0, 72.0, 200.0), ("Twain's", False, 100.0, 205.0, 260.0)])])
    page = PdfExtractor(doc=doc).parse()[0]
    assert page.lines[0].bold is True


def test_content_pages_drops_front_and_back_matter():
    doc = FakeDoc(
        [_front_matter(), _front_matter(), _front_matter()]
        + [_body_page(n) for n in range(1, 48)]
        + [_body_page(48), _body_page(49)]  # Appendix A — the author's own life story
    )
    pages = PdfExtractor(doc=doc).content_pages()
    assert [p.printed for p in pages] == list(range(1, 48))


def test_content_pages_raises_when_a_page_is_missing():
    """A header-parsing regression must fail loudly, not silently shorten the book."""
    doc = FakeDoc([_body_page(n) for n in range(1, 48) if n != 20])
    with pytest.raises(ValueError, match=r"missing \[20\]"):
        PdfExtractor(doc=doc).content_pages()


# --------------------------------------------------------------------------- chunking

from app.models.chunk import Chunk, Line, Page
from app.rag.chunker import Chunker, mark_duplicates


def _page(printed: int, *blocks) -> Page:
    """A content page with the numeric header prepended to the first block."""
    header = [(str(printed), False, 36.4, 200.0, 220.0)]
    first, *rest = blocks or ([],)
    return PdfExtractor(doc=FakeDoc([FakePage(header + list(first), *rest)])).parse()[0]._replace(
        printed=printed
    )


def test_ch1_bold_heading_starts_a_chunk_and_body_follows():
    pages = [
        _page(
            1,
            [
                ("Chapter 1: MARK TWAIN: ANECDOTES", True, 72.3, 72.0, 330.0),
                ("Spelling", True, 94.2, 72.0, 119.3),
                ("He deliberately misspelled a word.", False, 116.0, 72.0, 363.0),
                ("Name", True, 140.0, 72.0, 100.0),
                ("His real name was Samuel.", False, 160.0, 72.0, 363.0),
            ],
        )
    ]
    chunks = Chunker().chunk(pages)
    assert [(c.title, c.text) for c in chunks] == [
        ("Spelling", "He deliberately misspelled a word."),
        ("Name", "His real name was Samuel."),
    ], "the all-caps chapter heading must not become a chunk"


def test_chunk_page_span_covers_every_contributing_page():
    pages = [
        _page(1, [("Steamboat Pilot", True, 94.2, 72.0, 200.0), ("It began here.", False, 116.0, 72.0, 363.0)]),
        _page(2, [("It continued here.", False, 72.3, 72.0, 363.0)]),
    ]
    (chunk,) = Chunker().chunk(pages)
    assert (chunk.page_start, chunk.page_end) == (1, 2)
    assert chunk.page_label == "Ch.1, p.1-2"
    assert chunk.text == "It began here. It continued here."


def test_ch2_one_printed_paragraph_is_one_chunk():
    """Two aphorisms, the first of which fills the right margin.

    p.30 and p.32 print exactly this shape, and it is why the x_right "short last line"
    heuristic under-counts Ch2 by two: blocks are the signal, not line width.
    """
    pages = [
        _page(
            27,
            [("I have never taken any exercise except sleeping and resting.", False, 94.2, 72.0, 365.2)],
            [("Go to Heaven for the climate, Hell for the company.", False, 116.0, 72.0, 328.9)],
        )
    ]
    chunks = Chunker().chunk(pages)
    assert len(chunks) == 2
    assert chunks[0].title == "I have never taken any exercise except s…", chunks[0].title
    assert chunks[1].title == "Go to Heaven for the climate, Hell for t…"
    assert all(c.chapter == 2 for c in chunks)


def test_ch3_merges_a_wrapped_question_and_drops_the_notice():
    pages = [
        _page(
            34,
            [
                ("Chapter 3: MARK TWAIN: HIS LIFE", True, 72.3, 72.0, 330.0),
                ("Note: Some anecdotes are repeated in this short", True, 94.2, 72.0, 340.0),
                ("biographical sketch.", True, 108.0, 72.0, 200.0),
                ("What is one story of how Mark Twain got his", True, 130.0, 72.0, 340.0),
                ("pseudonym?", True, 144.0, 72.0, 150.0),
                ("Rivermen called out mark twain.", False, 166.0, 72.0, 363.0),
            ],
        )
    ]
    (chunk,) = Chunker().chunk(pages)
    assert chunk.title == "What is one story of how Mark Twain got his pseudonym?"
    assert chunk.text == "Rivermen called out mark twain."


def _chunk(cid: str, chapter: int, text: str, page: int = 1) -> Chunk:
    return Chunk(id=cid, chapter=chapter, title="t", page_start=page, page_end=page, text=text)


SHARED = (
    "As a young schoolboy Samuel got into trouble with his teacher and she sent him "
    "outside to find a switch that she could use to hit him young Samuel returned with "
    "a wood shaving that would definitely not hurt"
)
FILLER = " ".join(f"word{i}" for i in range(220))


def test_duplicates_link_a_long_retelling_across_chapters():
    """The Ch3 fixture is deliberately over 200 words.

    difflib's autojunk only engages at len(b) >= 200, so a short fixture would pass even
    with the flag missing — and with it missing this pair reports a longest match of 1.
    """
    a = _chunk("c1", 1, SHARED)
    b = _chunk("c2", 3, f"{FILLER} {SHARED} {FILLER}")
    assert len(b.text.split()) > 200
    assert mark_duplicates([a, b]) == 1
    assert a.duplicates == ["c2"] and b.duplicates == ["c1"]


def test_duplicates_catch_a_short_restatement_by_ratio():
    """Ch3's 'real name' answer is 8 words and no absolute threshold can reach it."""
    a = _chunk("c1", 1, f"Mark Twain's real name was Samuel Langhorne Clemens. {FILLER}")
    b = _chunk("c2", 3, "Mark Twain's real name was Samuel Langhorne Clemens.")
    assert mark_duplicates([a, b], min_words=20) == 1


def test_two_different_ch1_anecdotes_are_never_linked_to_each_other():
    """One Ch3 block retells four separate Ch1 anecdotes (measured: c0183).

    A shared group label would make those four look like duplicates of one another and
    collapse them at retrieval time, so the links must stay pairwise.
    """
    a = _chunk("c1", 1, SHARED)
    b = _chunk("c2", 1, f"Something else entirely. {FILLER}")
    big = _chunk("c3", 3, f"{SHARED} {FILLER} Something else entirely. {FILLER}")
    mark_duplicates([a, b, big])
    assert set(big.duplicates) == {"c1", "c2"}
    assert a.duplicates == ["c3"] and b.duplicates == ["c3"]
    assert "c2" not in a.duplicates and "c1" not in b.duplicates


def test_unrelated_chunks_are_not_linked():
    a = _chunk("c1", 1, "A short anecdote about a cat and a hot stove lid.")
    b = _chunk("c2", 3, f"{FILLER} nothing in common here {FILLER}")
    assert mark_duplicates([a, b]) == 0
