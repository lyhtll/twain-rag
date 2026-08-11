# Mark Twain QA Bot

A RAG system whose only knowledge source is one ebook — "Mark Twain Anecdotes and
Quotes" (David Bruce, 2008). It answers from retrieved chunks only, cites them, and
says the answer is not in the book when it isn't.

## Tech Stack
- Python 3.13
- PyMuPDF (extraction — font weight and coordinates), rank-bm25 (keyword),
  sentence-transformers `BAAI/bge-small-en-v1.5` (embeddings), numpy (vector search)
- Anthropic SDK, `claude-opus-5` — answer generation via `messages.parse()`
- FastAPI + uvicorn, one static HTML page — query surface
- pydantic / pydantic-settings — models and config
- No vector DB and no RAG framework. See `agent_docs/rag.md` for why.

## HOW (commands)
```bash
pip install -r requirements.txt
python -m scripts.ingest data/book.pdf   # chunk + index (reproduction step 1)
uvicorn main:app                         # query at localhost:8000 (step 2)
python -m eval.report                    # run the 10-question set -> docs/EVAL.md
pytest -q                                # unit tests (no API key, no PDF needed)
```

## ARCHITECTURE
```
app/
├── core/
│   ├── config.py         # Settings(BaseSettings) + settings singleton
│   └── dependencies.py   # get_index() / get_retriever() / get_answer_agent()
├── models/
│   ├── chunk.py          # Chunk, Page, Line, Hit
│   ├── agent.py          # LLM I/O types: AnswerOut, Citation
│   └── schemas/ask/      # request.py, response.py — HTTP DTOs
├── rag/
│   ├── text.py           # tokenize(), norm(), doc_for()
│   ├── extractor.py      # PdfExtractor — pages, printed page numbers, bold flags
│   ├── chunker.py        # Chunker — chapter-aware rules + near-duplicate marking
│   ├── indexer.py        # Embedder, Index — build/save/load/search_bm25/search_dense
│   └── retriever.py      # HybridRetriever — RRF + duplicate collapse
├── agents/
│   └── answer_agent.py   # AnswerAgent — the only Claude caller
├── api/ask.py            # APIRouter
└── observability.py      # log_run() -> runs/*.jsonl
main.py                   # FastAPI assembly
scripts/ingest.py         # CLI entry (assignment §4 reproduction command)
static/index.html         # question box, answer, citations. No build step.
eval/{questions.yaml, report.py}
tests/test_pipeline.py
data/ index/ runs/        # gitignored
docs/                     # EVAL.md, CHUNK_STATS.md (generated), NOTES.md (Korean)
```

Naming follows agora-backend: `*Agent` calls an LLM, everything else does not.

## Reference Docs
Read the relevant doc before starting a task.
- `agent_docs/rag.md` — chunk units, retrieval, answer rules, citation format
- `agent_docs/eval.md` — eval protocol, grading criteria, failure classification
- `agent_docs/conventions.md` — commit format, layout, DI, test rules

## IMPORTANT (graded directly — violating these zeroes the category)

1. **Never answer from knowledge outside the retrieved chunks.** Supplementing an
   answer with what the model already knows about Mark Twain counts as wrong. If the
   retrieved chunks do not contain the answer, reply `Not in this book.`. State this
   constraint in the prompt itself, not just in code.
2. **Every answer carries chunk titles and page numbers.** The model names which chunk
   and which sentence it used; the title and page come from the `Chunk` record, never
   from the model. `format_answer()` MUST NOT emit a citation it did not verify.
3. **`eval/questions.yaml` is frozen.** Do not edit questions or expected evidence
   after its first commit. If retrieval is wrong, fix the code and leave the question
   alone. If an edit seems genuinely necessary, ask the user first.
4. **Never commit `data/*.pdf` or `data/chunks.jsonl`.** The ebook is distributed for
   non-commercial use in unmodified form. Only code and processing scripts go in the
   repository.
5. **Never hand-write `docs/EVAL.md` or `docs/CHUNK_STATS.md`.** Generate them from
   script output only — a hand-written table turns into a lie the next time the code
   changes.

## Verification (definition of done for every task)

After changing code, **run the checks below and confirm they pass** before reporting
completion. If a check fails, show its output and say it failed.

| Changed | Command | Pass condition |
|---|---|---|
| `rag/extractor.py` | `pytest -q -k page` | header parsed and stripped; 47 content pages; front/back matter excluded |
| `rag/chunker.py` | `pytest -q -k chunk` | chunk count > 0; every chunk has `title` and pages; `page_start <= page_end` |
| `rag/indexer.py` | `pytest -q -k index` | `build().save()` then `load()` keeps `embeddings` rows aligned with `ids` |
| `rag/retriever.py` | `pytest -q -k retrieve` | for known questions, the expected chunk is in top-3 |
| `agents/answer_agent.py` | `pytest -q -k "answer or citation"` | empty hits -> refusal text; unknown `chunk_id` or unquotable `quote` rejected |
| `api/ask.py` | `pytest -q -k api` | `POST /ask` returns a JSON **object** with `text`/`sources`/`refused` |
| eval code | `python -m eval.report` | all 10 questions run and the table is generated |

The whole suite must pass with **no API key, no PDF, and no embedding model**. That is
what dependency injection is for — see `agent_docs/conventions.md`.

---

## How to work

**1. Think before coding.** State assumptions. If there are several readings, present
them instead of picking one silently. If a simpler approach exists, say so. If
something is unclear, stop and ask.

**2. Simplicity first.** The minimum code that solves the problem. No unrequested
features, abstractions, or config options. No error handling for impossible states.
Do not add code for a problem you have not measured — mark the deferral with a
`ponytail:` comment naming the trigger that would justify it.

**3. Surgical changes.** Do not touch code, comments, or formatting unrelated to the
request. Match the existing style. Remove only the imports your own change orphaned;
mention pre-existing dead code instead of deleting it.

**4. Goal-driven execution.** Turn the task into a verifiable goal.
"Improve retrieval" -> "measure whether the expected chunk lands in top-3 for 5 known
questions, compare before and after". For multi-step work, write
`step -> how it is verified` first.
