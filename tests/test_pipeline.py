"""Runs with no API key, no PDF, and no embedding model.

Anything that needs the real book is a manual check (see docs/NOTES.md), not a test.
"""

import pytest

from app.rag.extractor import PdfExtractor


class FakePage:
    """Stands in for a pymupdf.Page.

    Rows are (text, bold, y_top, x_left, x_right). x_left is real geometry here, not
    padding: the extractor orders same-baseline fragments by it.
    """

    def __init__(self, rows: list[tuple[str, bool, float, float, float]]) -> None:
        self._rows = rows

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
                        for text, bold, y, xl, xr in self._rows
                    ]
                }
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
