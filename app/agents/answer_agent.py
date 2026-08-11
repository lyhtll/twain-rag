"""The only place Claude is called.

The prompt states the grounding rule, and `format_answer` enforces it: a citation is
kept only if it names an excerpt we actually supplied *and* quotes a sentence that is
really in it. The second check is the one that matters — the first only proves the model
looked at a chunk, not that it quoted rather than paraphrased or invented.
"""

from typing import Any, Protocol

from app.core.config import settings
from app.models.agent import AnswerOut, Citation
from app.models.chunk import Hit
from app.models.schemas.ask import AskResponse, Source
from app.rag.text import norm

SYSTEM = """You answer questions about Mark Twain using ONLY the book excerpts provided in the user message.

Rules:
1. Use only the excerpts. Never use anything you know about Mark Twain from outside them, even if you are certain it is true.
2. If the excerpts do not contain the answer, set `text` to exactly "{refusal}" and return no citations. Do not hedge, do not add what you know, do not explain what the book does cover.
3. For every claim, add a citation naming the excerpt id and quoting the sentence you relied on. Copy the sentence verbatim from the excerpt — do not paraphrase it, do not fix its punctuation.
4. Answer in English, in two sentences or fewer."""


class MessagesAPI(Protocol):
    """The one method used from `anthropic.Anthropic().messages`. Tests inject a fake."""

    def parse(self, **kwargs: Any) -> Any: ...


class AnswerAgent:
    def __init__(self, messages: MessagesAPI | None = None) -> None:
        self._messages = messages or _default_messages()

    def build_prompt(self, question: str, hits: list[Hit]) -> dict[str, Any]:
        """Pure — no network. Returns the kwargs for `messages.parse`."""
        excerpts = "\n\n".join(self._render(hit) for hit in hits)
        return {
            "model": settings.llm_model,
            "max_tokens": settings.max_tokens,
            "system": SYSTEM.format(refusal=settings.refusal_text),
            "messages": [
                {"role": "user", "content": f"{excerpts}\n\nQuestion: {question}"},
            ],
            "output_format": AnswerOut,
            # parse() merges output_format into output_config as its "format" key, so
            # effort survives alongside it (verified against the SDK source).
            "output_config": {"effort": "low"},
        }

    def _render(self, hit: Hit) -> str:
        chunk = hit.chunk
        # Ch2 quotations have no printed title — the one on the record is a slice of the
        # text itself, so repeating it here would just be noise in the prompt.
        title = f' title="{chunk.title}"' if chunk.chapter != 2 else ""
        return (
            f'<excerpt id="{chunk.id}"{title} pages="{chunk.page_label}">\n'
            f"{chunk.text}\n"
            f"</excerpt>"
        )

    def format_answer(self, out: AnswerOut, hits: list[Hit]) -> tuple[AskResponse, list[Citation]]:
        """Pure — verifies citations. Returns the response and the citations it dropped."""
        given = {hit.chunk.id: hit.chunk for hit in hits}
        refused = norm(out.text) == norm(settings.refusal_text)

        sources: list[Source] = []
        rejected: list[Citation] = []
        for citation in out.citations:
            chunk = given.get(citation.chunk_id)
            if chunk is None:
                rejected.append(citation)  # names an excerpt we never supplied
                continue
            if norm(citation.quote) not in norm(chunk.text):
                rejected.append(citation)  # a sentence that is not in that excerpt
                continue
            sources.append(
                Source(
                    chunk_id=chunk.id,
                    title=chunk.title,
                    page=chunk.page_label,
                    quote=citation.quote,
                )
            )

        if not refused and hits and not sources:
            # An answer with no verifiable citation is not an answer. Loud on purpose:
            # the run log records the rejected citations, which is a generation-stage
            # finding for the failure analysis.
            raise ValueError(
                f"model answered with {len(out.citations)} citations, none of which "
                f"survived verification (excerpts offered: {sorted(given)})"
            )

        return AskResponse(text=out.text, sources=sources, refused=refused), rejected

    def answer(self, question: str, hits: list[Hit]) -> tuple[AskResponse, list[Citation]]:
        response = self._messages.parse(**self.build_prompt(question, hits))
        parsed: AnswerOut | None = getattr(response, "parsed_output", None)
        if parsed is None:
            raise ValueError(f"model returned no parsed output (stop_reason={response.stop_reason!r})")
        return self.format_answer(parsed, hits)


def _default_messages() -> MessagesAPI:
    """Pick the credential path. Imports are local so neither is required to import this."""
    if settings.answer_provider == "claude_code":
        from app.agents.claude_code_client import ClaudeCodeMessages

        return ClaudeCodeMessages()

    if settings.answer_provider != "api":
        raise ValueError(f"unknown answer_provider {settings.answer_provider!r} (api | claude_code)")

    import anthropic

    if not settings.anthropic_api_key:
        raise RuntimeError(
            "no API key configured — copy .env.example to .env and fill in "
            "ANTHROPIC_API_KEY (or export it). Ingest, retrieval and the tests do not "
            "need one; only answer generation does."
        )
    return anthropic.Anthropic(api_key=settings.anthropic_api_key).messages
