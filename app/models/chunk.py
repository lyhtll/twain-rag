from typing import NamedTuple

from pydantic import BaseModel, Field

# PyMuPDF coordinates: origin at the page's top-left, units are pt (1/72 inch),
# y grows downward. This book is 432 x 648 pt (6 x 9 in). Every line from
# get_text("dict") carries bbox = (x0, y0, x1, y1).


class Line(NamedTuple):
    text: str
    bold: bool  # span["font"] contains "Bold" -> heading candidate
    y_top: float  # bbox[1]; reading order, paragraph gaps, topmost = page-number header
    x_right: float  # bbox[2]; justified body lines end at a near-constant right margin
    block: int  # PyMuPDF block index; one block == one printed paragraph in this book


class Page(NamedTuple):
    pdf_index: int  # 1-based PDF page
    printed: int | None  # parsed from the top-of-page header; None on front matter
    lines: list[Line]


class Chunk(BaseModel):
    """One retrieval + citation unit. Round-trips through data/chunks.jsonl."""

    id: str
    chapter: int  # 1 | 2 | 3
    title: str  # Ch1: anecdote heading / Ch3: question / Ch2: derived from the text
    page_start: int  # printed page numbers, not PDF indices
    page_end: int
    text: str
    # Ids of chunks that retell the same passage. Pairwise, not a group label: one Ch3
    # block can contain four *different* Ch1 anecdotes, so a shared group id would make
    # those four look like duplicates of each other and collapse them wrongly.
    duplicates: list[str] = Field(default_factory=list)

    @property
    def page_label(self) -> str:
        span = (
            f"p.{self.page_start}"
            if self.page_start == self.page_end
            else f"p.{self.page_start}-{self.page_end}"
        )
        return f"Ch.{self.chapter}, {span}"


class Hit(NamedTuple):
    chunk: Chunk
    bm25_rank: int | None  # None when that retriever missed it — kept for failure analysis
    dense_rank: int | None
    fused: float
