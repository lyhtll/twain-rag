# Mark Twain QA Bot

A minimal RAG system whose only knowledge source is one ebook — *Mark Twain Anecdotes and
Quotes* (David Bruce, 2008). It answers from retrieved excerpts only, cites the chunk
title and printed page for every claim, and answers `이 책에는 없습니다` when the book
does not cover the question.

The PDF is **not** in this repository. It is distributed for non-commercial use in
unmodified form, so only code and processing scripts are committed — download it yourself
and put it at `data/book.pdf`.

## Reproduce

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt

# 1. PDF -> chunks -> indexes. Regenerates data/ , index/ and docs/CHUNK_STATS.md
#    from scratch. No credential needed.
.venv/bin/python -m scripts.ingest data/book.pdf

# 2. Ask. Credential needed — see below.
.venv/bin/uvicorn main:app          # then open http://localhost:8000
```

```bash
curl -sX POST localhost:8000/ask -H 'content-type: application/json' \
     -d '{"text":"At whose home was Mark Twain staying when he stopped all the clocks?"}'
```

```json
{"text": "He was staying at the home of political cartoonist Thomas Nast.",
 "sources": [{"chunk_id": "c0029", "title": "Noisy Clocks", "page": "Ch.1, p.9",
              "quote": "During the night, Mr. Twain was bothered by the sounds of the Nast family’s clocks…"}],
 "refused": false}
```

## Credential

Answer generation needs one. **Ingest, retrieval and the tests need none** — you can
regenerate every artifact and run the whole test suite without any credential.

Default path bills to a Claude Pro/Max subscription:

```bash
claude setup-token            # prints a one-year OAuth token; it is not saved for you
cp .env.example .env          # paste it as CLAUDE_CODE_OAUTHTOKEN=
unset ANTHROPIC_API_KEY       # it outranks the OAuth token if both are set
```

To pay per token through the Messages API instead, put this in `.env`:

```
answer_provider=api
ANTHROPIC_API_KEY=sk-ant-...
```

Both paths go through the same `AnswerAgent`; only the transport differs. See
`app/agents/claude_code_client.py` for what the subscription path has to compensate for.

## Evaluate

```bash
.venv/bin/python -m eval.report        # runs eval/questions.yaml -> docs/EVAL.md
.venv/bin/python -m scripts.compare_fusion   # RRF vs CC, retrieval only, no model calls
```

`eval/questions.yaml` was written and committed **before** any chunking, retrieval or
answer code existed (`git log --oneline eval/questions.yaml`) and has not been edited
since. Human judgements live in `eval/marks.yaml`; `docs/EVAL.md` is generated from both
and is never hand-edited.

## Test

```bash
.venv/bin/python -m pytest -q          # 45 tests, ~0.4s
```

The suite runs with **no credential, no PDF and no embedding model**. Dependencies are
injected through `Protocol`s (`app/rag/indexer.py`, `app/agents/answer_agent.py`) and API
tests stub the FastAPI dependencies, so nothing downloads a model or opens a socket.

## How it works

```
PDF ─ PyMuPDF (font weight, printed page numbers)
    └ chapter-aware chunking ─ data/chunks.jsonl ─ BM25 + bge-small ─ index/

question ─ BM25 top-10 ┐
                       ├ RRF ─ collapse duplicates ─ top-3 ─ claude ─ verified citations
           dense top-10┘
```

- **Chunking is per chapter** because the three chapters are structurally different:
  Ch1 has bold anecdote headings, Ch2 has no headings at all, Ch3 uses bold questions.
  Measured chunk lengths differ 20x between them. `docs/NOTES.md` §1.
- **Retrieval is hybrid** because the halves fail differently — BM25 carries rare nouns,
  the embeddings carry paraphrase. `docs/NOTES.md` §4 has a measured case of each.
- **Citations are built in two steps.** The model returns only a chunk id and a verbatim
  quote; the title and page come from the chunk record, so they cannot be invented. A
  citation is dropped unless it names a supplied excerpt *and* quotes a sentence really in
  it. An answer with no surviving citation raises rather than shipping.
- **No vector DB, no RAG framework.** 187 chunks × 384 dims is 287KB; brute-force cosine
  is exact and microseconds. `docs/NOTES.md` §6 lists what was considered and rejected.

## Deliverables

| | |
|---|---|
| `docs/CHUNK_STATS.md` | chunk counts per chapter, lengths, duplicate links — generated |
| `docs/EVAL.md` | the 10-question table — generated |
| `docs/NOTES.md` | chunking rationale, two diagnosed failures, the one next fix |
| `agent_docs/` | the working notes the implementation was driven from |

## Layout

Follows the `app/core` + `app/models` + `app/rag` + `app/agents` + `app/api` split, with
`*Agent` reserved for the one class that calls an LLM. See `CLAUDE.md`.
