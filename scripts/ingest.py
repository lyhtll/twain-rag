"""PDF -> chunks (-> index, added on day 3). Assignment §4 reproduction command:

    python -m scripts.ingest data/book.pdf
"""

import statistics as st
import sys
from collections import Counter
from pathlib import Path

from app.core.config import settings
from app.models.chunk import Chunk
from app.rag.chunker import CHAPTER_RANGES, Chunker, mark_duplicates
from app.rag.extractor import PdfExtractor
from app.rag.indexer import Index, save_chunks

CHAPTER_NAMES = {1: "Anecdotes", 2: "Quotations", 3: "His Life"}


def write_stats(chunks: list[Chunk], pairs: int, path: Path = Path("docs/CHUNK_STATS.md")) -> None:
    """Generated, never hand-written — a hand-edited table lies after the next change."""
    path.parent.mkdir(parents=True, exist_ok=True)
    per = Counter(c.chapter for c in chunks)
    lines = [
        "# 청크 통계",
        "",
        f"`python -m scripts.ingest {settings.book_path}` 로 생성된다. 손으로 고치지 않는다.",
        "",
        f"**총 청크 수: {len(chunks)}**",
        "",
        "| 장 | 인쇄 쪽 | 청크 수 | 평균 자수 | 중위 | 최소 | 최대 |",
        "|---|---|---|---|---|---|---|",
    ]
    for chapter, (first, last) in CHAPTER_RANGES.items():
        sizes = [len(c.text) for c in chunks if c.chapter == chapter]
        lines.append(
            f"| Ch{chapter} {CHAPTER_NAMES[chapter]} | {first}–{last} | {per[chapter]} | "
            f"{st.mean(sizes):.0f} | {st.median(sizes):.0f} | {min(sizes)} | {max(sizes)} |"
        )

    all_sizes = sorted(len(c.text) for c in chunks)
    lines += [
        "",
        f"전체 청크 평균: {st.mean(all_sizes):.0f}자. "
        f"중위: {st.median(all_sizes):.0f}. "
        f"범위: {all_sizes[0]}–{all_sizes[-1]}.",
        "",
        "장 사이 평균이 20배 벌어지는 것이 한 가지 청킹 규칙으로는 안 되는 이유다. 제목 없는",
        "Ch2의 한 줄 인용문과 두 쪽에 걸친 Ch3의 질문 블록은 다른 종류의 물건이고,",
        "각각이 독자가 인용할 단위다.",
        "",
        "## 최단·최장 청크",
        "",
        "| 청크 | 장 | 쪽 | 자수 | 제목 |",
        "|---|---|---|---|---|",
    ]
    ranked = sorted(chunks, key=lambda c: len(c.text))
    for chunk in ranked[:3] + ranked[-3:]:
        lines.append(
            f"| `{chunk.id}` | Ch{chunk.chapter} | {chunk.page_label} | {len(chunk.text)} "
            f"| {chunk.title[:60]} |"
        )

    linked = [c for c in chunks if c.duplicates]
    lines += [
        "",
        "## 근사 중복 링크 (Ch1 ↔ Ch3)",
        "",
        f"{pairs}쌍, {len(linked)}개 청크. 책이 직접 알려준다 — Ch3 첫 줄이",
        '"Note: Some anecdotes are repeated in this short biographical sketch." 다.',
        "두 사본을 모두 유지한다. 쪽수가 다르므로 인용은 독자가 실제로 펼 수 있는 쪽을",
        "가리켜야 한다. 낮은 점수의 사본은 검색 시점에 접는다.",
        "",
        "링크는 공유 그룹 라벨이 아니라 쌍 단위다. Ch3 블록 하나가 서로 *다른* Ch1 일화를",
        "최대 4개 재수록하므로, 라벨을 공유하면 그 넷이 서로의 중복인 것처럼 보인다.",
        "",
        "| Ch3 청크 | 쪽 | 재수록한 Ch1 일화 |",
        "|---|---|---|",
    ]
    by_id = {c.id: c for c in chunks}
    for chunk in chunks:
        if chunk.chapter == 3 and chunk.duplicates:
            retold = ", ".join(f"Ch1 `{d}` {by_id[d].title}" for d in chunk.duplicates)
            lines.append(f"| `{chunk.id}` | {chunk.page_label} | {retold} |")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(pdf: Path) -> None:
    pages = PdfExtractor(path=pdf).content_pages()
    print(f"[1/4] extracted {len(pages)} content pages (printed 1–{pages[-1].printed})")

    chunks = Chunker().chunk(pages)
    per = Counter(c.chapter for c in chunks)
    print(f"[2/4] chunked: {' / '.join(f'Ch{c} {per[c]}' for c in sorted(per))} = {len(chunks)}")

    pairs = mark_duplicates(chunks)
    print(f"[3/4] near-duplicate pairs: {pairs}")

    save_chunks(chunks)
    write_stats(chunks, pairs)
    print(f"[4/4] wrote {settings.chunks_path} and docs/CHUNK_STATS.md")

    index = Index.build(chunks)
    index.save()
    print(f"      built index in {settings.index_dir}/ ({len(chunks)} chunks)")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else settings.book_path)
