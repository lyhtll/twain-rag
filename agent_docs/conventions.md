# Conventions

## Commits

Format: `<type>(<scope>): <subject>`

Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`
Scopes: `rag`, `agents`, `api`, `models`, `core`, `eval`, `docs`

Examples:
- `feat(rag): split chunks at bold anecdote headings`
- `fix(rag): keep the page-number header out of chunk text`
- `test(agents): cover the empty-retrieval refusal path`
- `docs(eval): freeze the 10-question set`

One logical change per commit. Do not bundle unrelated changes. Never `--amend`,
never `--no-verify`.

**`eval/questions.yaml` gets its own commit, made before retrieval and answer code
works.** That commit is the freeze point (see `agent_docs/eval.md`) — bundling it with
implementation code destroys the evidence that the questions came first.

## Layout

Follows agora-backend, sized for this project. See `CLAUDE.md` for the tree.

- `app/rag/` — pipeline stages that do **not** call an LLM.
- `app/agents/` — the only place an LLM is called. `*Agent` in the class name means it
  calls Claude; anything without that suffix must not.
- `app/models/agent.py` — types the *model* fills (`AnswerOut`, `Citation`).
  `app/models/schemas/` — types we emit over HTTP (`AskResponse`, `Source`).
  A type's file says which trust boundary it belongs to; keep that split.
- `scripts/` — operational entry points, not application code.
- `docs/` — deliverables. `EVAL.md` and `CHUNK_STATS.md` are generated; `NOTES.md` is
  hand-written **in Korean** (it is submitted to a Korean-language grader).
- `data/`, `index/`, `runs/` — gitignored. Nothing in the repo may require them to import.

## Dependency injection

Constructor injection with a real default, as in agora's
`Embedder(model: EmbeddingModel | None = None)`:

```python
class AnswerAgent:
    def __init__(self, client: LLMClient | None = None) -> None:
        self._client = client or anthropic.Anthropic(api_key=settings.anthropic_api_key)
```

- Declare the injected dependency as a `Protocol`, not a concrete class. Tests pass a
  fake without importing `sentence_transformers` or `anthropic`.
- Build the real default **lazily inside** the constructor, so importing the module
  never loads a model or requires a key.
- FastAPI wiring lives in `app/core/dependencies.py`. `get_index()` is
  `lru_cache`d — the index is loaded once per process, not once per request.
- API tests use `app.dependency_overrides`, not monkeypatching.

## Tests

- `pytest`, one file: `tests/test_pipeline.py`. Fixtures are built inline in the test.
- **The whole suite must pass with no API key, no PDF, and no embedding model.**
  That is the point of the injection rules above.
- No test code in `app/` — no `if __name__ == "__main__"` self-checks, no `_demo`.
- A test that needs chunk data builds it inline. Do not read `data/chunks.jsonl` from a
  test — it is gitignored, so the test would pass locally and fail everywhere else.
- Tests that hit the Anthropic API are marked `@pytest.mark.llm` and excluded from the
  default run.

## Naming

- `Chunk` is always the record from `app/models/chunk.py`, never a bare text string.
  If a function takes only the text, name the parameter `text`.
- `printed` always means the page number printed in the book; `pdf_index` is the
  1-based PDF page. They differ by 3 in this book — never use one for the other.

## Error handling

Fail loudly on setup problems, quietly on nothing.

- Missing PDF, missing index, empty chunk list: raise with the path in the message.
  These are the reproduction path — a silent fallback here is how "it works on my
  machine" happens.
- Do not catch exceptions around the Anthropic call to return a placeholder answer.
  A failed API call must not look like a refusal — the eval would score it as one.
- A citation that fails verification is dropped and logged, not raised — that is a
  finding for the failure analysis. But zero surviving citations with a non-empty
  retrieval is a bug: raise.

## Comments

Mark deliberate simplifications with `ponytail:` and name what would justify the
upgrade, as agora does:

```python
# ponytail: brute-force cosine over ~200 chunks (297KB). Swap for an ANN index
# when the corpus passes ~100k vectors and search stops being a rounding error
# next to query embedding.
```
