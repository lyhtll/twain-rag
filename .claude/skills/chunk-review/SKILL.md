---
name: chunk-review
description: |
  Use when writing or changing chunking code, or when inspecting chunk output.
  Triggers on: PDF text extraction, chunk boundary rules, front-matter exclusion,
  duplicate anecdotes, chunk statistics, "are these chunks any good".
---

# Chunk Review

Read `agent_docs/rag.md` § R1 Chunking first — the unit and the record schema are
defined there. This is the checklist for verifying the output.

## Read the chunks, don't just count them

Print 5 chunks and read them: the shortest, the longest, and 3 at random. A chunk
count and a mean length can look perfect while every chunk is cut mid-sentence.
For each one ask: is this a self-contained anecdote? Could a reader answer a factual
question from it alone?

## Required checks before calling chunking done

1. **No chunk is empty or whitespace-only.**
2. **Every chunk has a non-empty `title` and an integer `page`.** These are the
   citation. A chunk without them cannot be used in an answer.
3. **`page` matches the printed page number**, not the PDF page index — they differ
   by the front matter offset. Verify against 2 chunks by opening the book.
4. **Front matter is gone.** Grep the chunks for "copyright", "table of contents",
   "all rights reserved", "about the author". Hits mean the exclusion rule missed.
5. **Running headers/footers are gone.** If the same short line appears in more than
   ~10 chunks, it is page furniture, not content.
6. **No chunk is cut mid-sentence at its start or end** — sample 5 and look at the
   first and last 40 characters.
7. **Duplicate anecdotes share a `dup_group`.** Find them by normalized-text hash or
   high similarity, not by title alone (headings may differ between chapters 1 and 3).

## Statistics

Regenerate `docs/CHUNK_STATS.md` from code whenever chunking changes:
total count, count per chapter, mean and median character length, and the 3 shortest
and 3 longest chunks with their titles. Never hand-edit that file.

## Judgment calls to record, not to hide

If the heading pattern does not cleanly delimit anecdotes, or a section is ambiguous
(front matter or content?), pick a rule, state it in `docs/NOTES.md`, and say why.
The assignment grades the reasoning behind the chunk unit, so an explained imperfect
boundary scores better than an unexplained tidy one.

## Verify
```bash
pytest -q tests/test_pipeline.py -k chunk
python -m twainbot.ingest data/book.pdf   # then read docs/CHUNK_STATS.md
```
