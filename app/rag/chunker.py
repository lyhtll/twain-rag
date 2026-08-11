"""Chapter-aware chunking. One unit per chapter, because the chapters differ.

Ch1 prints a short bold heading per anecdote; Ch2 prints no headings at all and runs
quotations as consecutive paragraphs; Ch3 uses bold questions that wrap across two
lines. Measured chunk lengths differ by 20x between chapters (Ch2 ~89 chars, Ch3 ~2482),
so a single rule would be wrong for two of the three.
"""

import difflib
from dataclasses import dataclass, field

from app.core.config import settings
from app.models.chunk import Chunk, Line, Page
from app.rag.text import norm

CHAPTER_RANGES = {1: (1, 26), 2: (27, 33), 3: (34, 47)}


def chapter_of(printed: int) -> int:
    for chapter, (first, last) in CHAPTER_RANGES.items():
        if first <= printed <= last:
            return chapter
    raise ValueError(f"printed page {printed} is outside the content chapters")


@dataclass
class _Draft:
    """A chunk under construction: title fixed, body and page span still growing."""

    chapter: int
    title: str
    pages: list[int]
    body: list[str] = field(default_factory=list)

    def finish(self, index: int) -> Chunk:
        return Chunk(
            id=f"c{index:04d}",
            chapter=self.chapter,
            title=self.title,
            page_start=min(self.pages),
            page_end=max(self.pages),
            text=" ".join(self.body).strip(),
        )


class Chunker:
    def __init__(self, ch2_title_chars: int = settings.ch2_title_chars) -> None:
        self._ch2_title_chars = ch2_title_chars

    def chunk(self, pages: list[Page]) -> list[Chunk]:
        drafts: list[_Draft] = []
        for chapter, (first, last) in CHAPTER_RANGES.items():
            in_chapter = [p for p in pages if first <= (p.printed or 0) <= last]
            handler = {1: self._chunk_ch1, 2: self._chunk_ch2, 3: self._chunk_ch3}[chapter]
            drafts.extend(handler(in_chapter))
        return [d.finish(i) for i, d in enumerate(drafts) if d.body]

    # -- Ch1: one bold heading per anecdote, never wrapped (longest measured: 29 chars)
    def _chunk_ch1(self, pages: list[Page]) -> list[_Draft]:
        drafts: list[_Draft] = []
        for page in pages:
            for line in _body_lines(page):
                if line.bold:
                    drafts.append(_Draft(chapter=1, title=line.text, pages=[page.printed]))
                elif drafts:
                    drafts[-1].body.append(line.text)
                    drafts[-1].pages.append(page.printed)
        return drafts

    # -- Ch2: no headings. One printed paragraph = one quotation = one chunk.
    def _chunk_ch2(self, pages: list[Page]) -> list[_Draft]:
        drafts: list[_Draft] = []
        for page in pages:
            for block in sorted({ln.block for ln in _body_lines(page)}):
                lines = [ln for ln in _body_lines(page) if ln.block == block]
                text = " ".join(ln.text for ln in lines).strip()
                if not text:
                    continue
                drafts.append(
                    _Draft(chapter=2, title=self._derive_title(text), pages=[page.printed], body=[text])
                )
        return drafts

    def _derive_title(self, text: str) -> str:
        if len(text) <= self._ch2_title_chars:
            return text
        return text[: self._ch2_title_chars].rstrip() + "…"

    # -- Ch3: bold questions wrapping two lines, plus a bold notice that is not a heading
    def _chunk_ch3(self, pages: list[Page]) -> list[_Draft]:
        drafts: list[_Draft] = []
        pending: list[Line] = []
        pending_pages: list[int] = []
        for page in pages:
            for line in _body_lines(page):
                if line.bold:
                    pending.append(line)
                    pending_pages.append(page.printed)
                    joined = " ".join(ln.text for ln in pending)
                    # Every Ch3 heading is a question. The chapter's opening notice
                    # ("Note: Some anecdotes are repeated in this short biographical
                    # sketch.") is also bold and sits directly above the first question,
                    # with no body text between — so a plain "merge consecutive bold
                    # lines" rule would fuse notice and question into one fake heading.
                    # Flush on '?' as a heading, on '.' as a discard.
                    if joined.endswith("?"):
                        drafts.append(
                            _Draft(chapter=3, title=joined, pages=list(dict.fromkeys(pending_pages)))
                        )
                        pending, pending_pages = [], []
                    elif joined.endswith("."):
                        pending, pending_pages = [], []
                else:
                    # ponytail: a bold run ending in neither '?' nor '.' is dropped.
                    # Never happens in this book; revisit if a heading goes missing from
                    # docs/CHUNK_STATS.md.
                    pending, pending_pages = [], []
                    if drafts:
                        drafts[-1].body.append(line.text)
                        drafts[-1].pages.append(page.printed)
        return drafts


def mark_duplicates(
    chunks: list[Chunk],
    min_words: int = settings.dup_min_words,
    min_ratio: float = settings.dup_min_ratio,
) -> int:
    """Link chunks that retell the same passage. Returns the number of pairs found.

    Ch3 says so itself: "Note: Some anecdotes are repeated in this short biographical
    sketch." But the wording differs between copies (Ch1 "Samuel" becomes Ch3 "Sam"),
    so hash equality finds nothing and even the longest verbatim run gets cut short by a
    single substituted name. Hence the longest-common-subsequence of *words*, with two
    criteria:

    - absolute: a shared run of `min_words`, which catches long retellings;
    - relative: a run covering `min_ratio` of the shorter chunk, which catches short
      restatements — Ch3's "real name" answer is 8 words and is verbatim the opening
      sentence of Ch1 'Name', so no absolute threshold could ever reach it.

    Compared across Ch1 x Ch3 only (92 x 11 = 1012 pairs). Ch1 x Ch2 was measured and
    shares no run over 8 words: Ch2 holds independent aphorisms, not retold anecdotes.

    `autojunk=False` is load-bearing. SequenceMatcher discards elements appearing more
    than len(b)//100 + 1 times once len(b) >= 200, and a 3000-char Ch3 block is ~500
    words — "the", "a", "Twain" would all be junked and long matches could not form.
    The failure is silent: every pair reports a longest match of 1.
    """
    words = {c.id: norm(c.text).split() for c in chunks}
    ch1 = [c for c in chunks if c.chapter == 1]
    ch3 = [c for c in chunks if c.chapter == 3]

    pairs = 0
    for a in ch1:
        aw = words[a.id]
        for b in ch3:
            bw = words[b.id]
            match = difflib.SequenceMatcher(None, aw, bw, autojunk=False).find_longest_match(
                0, len(aw), 0, len(bw)
            )
            if match.size >= min_words or match.size >= min_ratio * min(len(aw), len(bw)):
                a.duplicates.append(b.id)
                b.duplicates.append(a.id)
                pairs += 1
    return pairs


def _body_lines(page: Page) -> list[Line]:
    """Lines that are knowledge source: no chapter headings, no stray page numbers."""
    return [ln for ln in page.lines if not ln.text.startswith("Chapter ") and not ln.text.isdigit()]
