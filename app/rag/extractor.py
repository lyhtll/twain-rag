"""PDF -> structured lines, with printed page numbers and bold flags.

The book prints its page number as a *header* (topmost line of each page), not a
footer. That line is stripped from the body and its value becomes the page's
`printed` number — reading it beats assuming a constant PDF-to-printed offset.
"""

import re
from pathlib import Path
from typing import Any, Protocol

import pymupdf

from app.models.chunk import Line, Page

PAGE_NUMBER = re.compile(r"^\s*(\d{1,3})\s*$")

# PyMuPDF's default text flags include TEXT_MEDIABOX_CLIP, which drops this book's
# page-number header (it sits at y=36.4, above the body at y=72.3, and gets clipped
# even though the mediabox is 0..648). Without these explicit flags the header is
# invisible and every page's `printed` comes back None. poppler/pdftotext keeps it,
# which is how the discrepancy was found.
TEXT_FLAGS = pymupdf.TEXT_PRESERVE_LIGATURES | pymupdf.TEXT_PRESERVE_WHITESPACE

# Printed pages 1-47 are the knowledge source: Ch1 1-26, Ch2 27-33, Ch3 34-47.
# Front matter (title, copyright, TOC) carries no printed number. Appendix A
# (48-49) is the *author's* autobiography, Appendix B (50-55) his book list —
# including either would let David Bruce's life answer questions about Twain's.
CONTENT_FIRST_PAGE = 1
CONTENT_LAST_PAGE = 47

# Body leading is ~13.7pt, so anything within 3pt of the previous baseline is the
# same visual line, not the next one.
SAME_LINE_TOLERANCE = 3.0


class PdfDocument(Protocol):
    def __len__(self) -> int: ...
    def __getitem__(self, i: int) -> Any: ...


class PdfExtractor:
    """Reads a PDF into `Page`/`Line` records. No chunking decisions here."""

    def __init__(self, doc: PdfDocument | None = None, path: Path | None = None) -> None:
        if doc is None and path is None:
            raise ValueError("PdfExtractor needs either a doc or a path")
        self._doc = doc if doc is not None else pymupdf.open(path)

    def parse(self) -> list[Page]:
        return [self._page(i) for i in range(len(self._doc))]

    def content_pages(self) -> list[Page]:
        """Body pages only, verified contiguous.

        A page whose header failed to parse would silently vanish here, so the
        contiguity check is the guard: it turns a parsing regression into an
        error instead of a quietly shorter book.
        """
        pages = [
            p
            for p in self.parse()
            if p.printed is not None and CONTENT_FIRST_PAGE <= p.printed <= CONTENT_LAST_PAGE
        ]
        found = [p.printed for p in pages]
        expected = list(range(CONTENT_FIRST_PAGE, CONTENT_LAST_PAGE + 1))
        if found != expected:
            missing = sorted(set(expected) - set(found))
            raise ValueError(
                f"expected printed pages {CONTENT_FIRST_PAGE}-{CONTENT_LAST_PAGE}, "
                f"got {len(found)} pages; missing {missing}"
            )
        return pages

    def _page(self, index: int) -> Page:
        lines = _lines(self._doc[index])
        printed, body = _split_header(lines)
        return Page(pdf_index=index + 1, printed=printed, lines=body)


def _lines(page: Any) -> list[Line]:
    """One `Line` per visual line of the page.

    PyMuPDF splits a justified line into one entry per word when the word gaps are
    wide (p.9 "Noisy Clocks" comes back as 7 fragments sharing y=269.87). Left as
    fragments, `x_right` would describe a word instead of the line, which is exactly
    the signal Ch2's paragraph detection reads. So fragments sharing a baseline are
    merged back into one line.
    """
    fragments: list[tuple[float, float, float, bool, str]] = []
    for block in page.get_text("dict", flags=TEXT_FLAGS)["blocks"]:
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            text = "".join(s["text"] for s in spans).strip()
            if not text:
                continue
            x0, y0, x1, _ = line["bbox"]
            fragments.append((y0, x0, x1, any("Bold" in s.get("font", "") for s in spans), text))

    # Cluster by baseline first, *then* order within the line. Sorting by (y, x) up
    # front would misplace a fragment whose baseline is off by a fraction of a point:
    # at y=269.90 it sorts after everything at y=269.87 and lands at the end of the
    # line instead of its x position.
    fragments.sort(key=lambda f: f[0])
    clusters: list[list[tuple[float, float, float, bool, str]]] = []
    for frag in fragments:
        if clusters and abs(frag[0] - clusters[-1][0][0]) <= SAME_LINE_TOLERANCE:
            clusters[-1].append(frag)
        else:
            clusters.append([frag])

    out: list[Line] = []
    for cluster in clusters:
        cluster.sort(key=lambda f: f[1])
        out.append(
            Line(
                text=" ".join(f[4] for f in cluster),
                bold=any(f[3] for f in cluster),
                y_top=cluster[0][0],
                x_right=max(f[2] for f in cluster),
            )
        )
    return out


def _split_header(lines: list[Line]) -> tuple[int | None, list[Line]]:
    """Pull the printed page number off the top of the page, if there is one."""
    if not lines:
        return None, []
    match = PAGE_NUMBER.match(lines[0].text)
    if match is None:
        return None, lines
    return int(match.group(1)), lines[1:]
