# RAG Pipeline

## Pipeline
```
PDF -> PyMuPDF lines (font weight + coordinates, printed page numbers)
    -> chapter-aware chunking -> data/chunks.jsonl
    -> BM25 index + bge-small embeddings -> index/

question (English)
    -> BM25 top-10  +  embedding top-10        (both rank lists kept)
    -> RRF fusion -> duplicate collapse -> top-3
    -> prompt (excerpts only) -> claude-opus-5 -> answer + verified citations
```

## Language decision
**Questions and chunks are both English.** The book is English, so keeping the query in
the same language removes the cross-lingual gap and gives the highest top-3 hit rate.
It also allows a small English-only embedding model (`bge-small-en-v1.5`, 384-dim).
Cost of this choice, to record in `docs/NOTES.md`: the system cannot take Korean
questions. Do not translate the book — a paraphrase between the answer and its evidence
defeats the point of citing.

## What the book actually looks like (measured)

58 PDF pages, 47 content pages. **Printed page = PDF index − 3**, verified across all 47.

| Section | Printed | PDF | Structure |
|---|---|---|---|
| Front matter | — | 1–3 | Title, license, TOC — **excluded** |
| Ch1 ANECDOTES | 1–26 | 4–29 | 92 bold headings (`Spelling`, `Steamboat Pilot`) + body |
| Ch2 QUOTATIONS | 27–33 | 30–36 | **No headings.** Quotations run as consecutive paragraphs |
| Ch3 HIS LIFE | 34–47 | 37–50 | 9 bold **questions** as headings, each wrapping 2 lines, + long answers |
| Appendix A | 48–49 | 51–52 | The *author's* autobiography — **excluded** |
| Appendix B | 50–55 | 53–58 | The author's book list — **excluded** |

**Excluding Appendix A is mandatory.** It is David Bruce's own life story (born 1954),
so including it would let the author's biography answer questions about Twain's.

### The page number is a top header, and PyMuPDF hides it by default

Each content page carries its printed number as the topmost line (y≈36.4; body starts at
y≈72.3). PyMuPDF's default text flags include `TEXT_MEDIABOX_CLIP`, which **drops that
line entirely** — every page comes back with no number. Pass explicit flags:

```python
TEXT_FLAGS = pymupdf.TEXT_PRESERVE_LIGATURES | pymupdf.TEXT_PRESERVE_WHITESPACE
page.get_text("dict", flags=TEXT_FLAGS)
```

`extractor.py` strips that line from the body and uses its value as `printed`. Reading
the number beats assuming a constant offset, and `content_pages()` raises if any of
printed 1–47 is missing — a parsing regression must not silently shorten the book.

### PyMuPDF also splits justified lines into words

A widely-set justified line comes back as one entry per word: p.9 "Noisy Clocks" is 7
fragments sharing `y=269.87`. Left as fragments, `x_right` describes a word instead of
the line — and `x_right` is exactly the signal Ch2's paragraph detection reads. So
`_lines()` merges fragments that share a baseline.

**Cluster by baseline first, then order within the line.** Sorting by `(y, x)` in one
pass misplaces a fragment whose baseline is off by a fraction of a point: at y=269.90 it
sorts after everything at y=269.87 and lands at the end of the line, producing
"Humorist of Mark". Real PDFs have sub-point baseline jitter.

### Headings are detected by font weight

`span["font"]` contains `"Bold"`. This is why PyMuPDF is used and pypdf/pdftotext are
not — neither exposes font weight. Measured bold-line counts: Ch1 93 (1 chapter heading
+ 92 anecdotes), Ch2 1 (chapter heading only — confirming Ch2 has no titles), Ch3 22
(chapter heading + a 2-line `Note:` + 9 questions wrapping across 2 lines each).

Regex fallback if font detection ever fails: line ≤ 45 chars, does not end in
terminal punctuation, previous line does. Body text is justified to 55–58 chars, so a
short line is a paragraph end and ends in punctuation.

## R1 Chunking

**One unit per chapter, because the three chapters are structurally different.**
A single rule would be wrong for two of the three. Exact boundary code is confirmed on
day 2 against the real book; the units are:

- **Ch1** — bold heading to next bold heading. `title` = the heading.
- **Ch2** — one quotation = one paragraph. `title` is derived from the first 40 chars of
  the text plus `…`, since nothing is printed to use.
- **Ch3** — bold question (merge consecutive bold lines; the question wraps) to the next
  question. `title` = the full question.
- **Excluded** — front matter, both appendices, the `Chapter N: ...` all-caps lines, and
  Ch3's `Note: Some anecdotes are repeated...` notice.

**Exclude before merging bold lines.** In Ch3 the chapter heading and the two-line
`Note:` sit directly above the first question, all bold and consecutive. Merge first and
they become one fake question.

**Do not split paragraphs the book itself merged.** p.29 prints two unrelated aphorisms
in a single paragraph ("There are lies, damned lies, and statistics. Against the assault
of laughter nothing can stand."). Splitting on sentences would be re-editing the book;
the printed paragraph stays the unit.

Measured chunk counts (day 1): Ch1 92 at ~420 chars, Ch2 82 at ~89 chars, Ch3 9 at
~2482 chars — about 183 total. The 20x spread across chapters is why one rule could not
have worked, and why **Ch2's very short chunks are a day-3 watch item**: BM25 length
normalization favours short documents, so Ch2 may crowd out top-3.

`Chunk.page_start` / `page_end` come from the min/max printed page of the lines that fed
the chunk — recorded during the page-by-page walk. There is no global text string and no
character-offset table; those existed only to derive page numbers.

### Ch2's derived title is not indexed

`doc_for()` decides the indexed string, and BM25 and the embeddings use the same one:

```python
def doc_for(c: Chunk) -> str:
    return c.text if c.chapter == 2 else f"{c.title}\n{c.text}"
```

Ch1/Ch3 titles are printed in the book and are real query terms. Ch2's title is a slice
of its own text, so indexing `title + text` would count those 40 chars twice and weight
the opening clause. **Index printed titles; never index derived ones.**

### Duplicate anecdotes (Ch1 ↔ Ch3)

The book says so itself: Ch3 opens with *"Note: Some anecdotes are repeated in this
short biographical sketch."* But the wording differs between copies (Ch1 "Mark Twain's
real name was…" vs Ch3 "When Sam Clemens was a steamboat pilot…"), so **hash equality
finds nothing.** Use the longest common subsequence of **words**, threshold 25 words:

```python
m = difflib.SequenceMatcher(None, a_words, b_words, autojunk=False).find_longest_match(...)
```

Candidates are **Ch1 x Ch3 only** — 92 x 9 = 828 pairs. Ch1 x Ch2 was measured on day 1
and shares no 8-word run with any quotation: Ch2 holds independent aphorisms, not retold
anecdotes.

`autojunk=False` is not optional. `SequenceMatcher` discards any element appearing more
than `len(b)//100 + 1` times once `len(b) >= 200`. On character sequences that junks
spaces and `e`/`t`/`a`, and a 200-character shared block reports a longest match of
**1**, with no error — the feature would look implemented and catch nothing. Word
sequences trip the same threshold (a 3000-char block is ~500 words), so the flag is
required either way; words are also ~70x faster than characters here.

Both copies stay as chunks — their page numbers differ and a citation must point at a
page the reader can open. They share a `dup_group`, collapsed at retrieval time so the
prompt never holds the same anecdote twice.

## R2 Retrieval

Hybrid, because the halves fail differently: BM25 catches proper nouns and exact phrases
("Halley's Comet", "Susy"), embeddings catch paraphrases sharing no words.

- BM25: `rank_bm25.BM25Okapi` over `tokenize(doc_for(chunk))`.
- Dense: `bge-small-en-v1.5`, `normalize_embeddings=True`. **The query gets the prefix
  `"Represent this sentence for searching relevant passages: "`; passages do not.**
  `Embedder.embed_query()` is the only place that prefix is added.
- Fusion: RRF, `score = Σ 1/(60 + rank)`. No score normalization needed, which is why it
  beats a weighted sum when there are only 3–10 candidates per side.
- Then collapse `dup_group`, then top-3.

**Keep both rank lists.** Failure analysis asks "did BM25 miss it or did the dense side?"
and that question is unanswerable from a fused list alone. This is also why
`EnsembleRetriever` was rejected — it returns only the fusion.

**No ANN index, no vector DB.** ~200 chunks × 384 dims is 297KB; `E @ q` is ~76k
multiply-adds, microseconds, and *exact*. Query embedding (~10–20ms) dominates by three
orders of magnitude, so an ANN index would optimize the part that is not the bottleneck
— and its 95–99% recall would put a 10-percentage-point wobble into a 10-question eval
that could not be distinguished from a retrieval-design error.

`HybridRetriever` takes the `Index` in its constructor. It must never call `Index.load()`
itself — that would reload a 133MB model per request.

**Never return an empty result to signal "not in the book."** A weak match is still a
match; deciding the book does not cover something is the generation step's job. (This is
why dynamic-k was rejected: dropping the third chunk can refuse a question that was
answerable.)

## R3 Answer

`claude-opus-5`, `max_tokens=4096` (thinking is on by default on this model and shares
the cap). `AnswerAgent` is the only class that calls Claude.

Rules the prompt must state explicitly:
1. Answer using the provided excerpts only. Do not use anything you know about Mark
   Twain from outside them.
2. If the excerpts do not contain the answer, reply exactly `이 책에는 없습니다`.
3. For each claim, name the excerpt id and quote the sentence you relied on, verbatim.

### Citations are built in two steps and verified twice

The model returns `AnswerOut{text, citations: [Citation{chunk_id, quote}]}` via
`client.messages.parse()`. **It never returns titles or page numbers** — those come from
the `Chunk` record, so they cannot be invented.

```python
if c.chunk_id not in given:                        # (1) chunk we never supplied
    drop
if norm(c.quote) not in norm(given[c.chunk_id].text):   # (2) sentence not in that chunk
    drop
```

(2) catches what (1) cannot: (1) only proves the model looked at a chunk, not that it
quoted it rather than paraphrasing or inventing. `norm()` collapses whitespace and
normalizes curly quotes and dashes — the book uses `“ ” ’` and em dashes, and a model
that retypes them straight is quoting correctly, not forging.

A failed verification drops that citation and is logged; it is a generation-stage finding
for R5, not a crash. Zero surviving citations with a non-empty retrieval **is** a bug —
raise.

Output carries `title`, `page_label` (`Ch.1, p.1-2`), and the verified quote, because
assignment §4 requires that a grader can check the passage in the book.

## Rejected, with reasons (record in `docs/NOTES.md`)

- **prev/next chunk augmentation** — in an anecdote collection the neighbouring chunk is
  a *different anecdote*; it adds noise, not context. R4's "scattered across passages"
  questions are answered by top-3 spanning Ch1 and Ch3, which are not adjacent.
- **Dynamic k / shortening the evidence** — a bonus item, but it can drop the chunk that
  held the answer and refuse an answerable question. Conflicts with R2 above.
- **Parent-Child chunking** — Ch3 blocks are long, but embedding dilution has not been
  measured. Reconsider only if day-3 retrieval shows Ch3 blocks missing top-3.
- **HyDE** — generating a hypothetical answer to search with pulls the model's outside
  knowledge of Twain into retrieval, the opposite of this system's constraint.
- **Cross-encoder reranking** — add only if a failure is diagnosed as a *ranking* problem.

## Verify
```bash
pytest -q                                       # no API key, no PDF, no model needed
python -m scripts.ingest data/book.pdf          # then read docs/CHUNK_STATS.md
uvicorn main:app                                # factual questions cite; absent ones refuse
```
