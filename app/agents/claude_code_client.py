"""`MessagesAPI` over `claude -p`, billed to a Claude Pro/Max subscription.

Implements the same `parse(**kwargs)` surface as `anthropic.Anthropic().messages`, so
`AnswerAgent` does not change at all — that is what the Protocol was for.

Two things differ from the Messages API and both are handled here rather than leaking
into the agent:

**No schema enforcement.** `claude -p` returns text, not a validated object, so the JSON
shape is requested in the prompt (generated from the same pydantic model the API path
passes as `output_format`) and validated on the way back. The citation checks in
`AnswerAgent.format_answer` are unaffected: they were never relying on the SDK's schema,
only on chunk-id membership and the quote substring.

**The harness has tools.** `claude -p` runs the Claude Code agent, which can read files
and search the web. Left alone in this repository it could open `data/chunks.jsonl` or the
PDF and answer from the whole book, which would silently invalidate the one claim this
project makes — that the answer comes only from the retrieved excerpts. Two guards, the
first load-bearing:

1. the subprocess runs in an **empty temporary directory**, so the filesystem tools have
   nothing to find no matter what is enabled;
2. the network and filesystem tools are denied by name, which covers the tools an empty
   cwd cannot (WebSearch, WebFetch).
"""

import json
import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol

from app.core.config import settings

# Denied by name in addition to the empty cwd. WebSearch/WebFetch are the ones an empty
# working directory does not protect against.
DENIED_TOOLS = [
    "Bash",
    "Read",
    "Write",
    "Edit",
    "Glob",
    "Grep",
    "NotebookEdit",
    "Task",
    "WebFetch",
    "WebSearch",
]

SHAPE_INSTRUCTION = """
Reply with a single JSON object and nothing else — no prose, no markdown fences.
It must match this JSON schema:

{schema}
"""


class Runner(Protocol):
    def __call__(self, argv: list[str], *, cwd: str, env: dict[str, str], timeout: float) -> str: ...


@dataclass
class ParsedResponse:
    """Mimics the shape `AnswerAgent` reads off an SDK response."""

    parsed_output: Any
    stop_reason: str
    # Non-empty when the model tried to use a tool we denied — i.e. tried to look outside
    # the excerpts. Empty on every run so far. ponytail: not threaded into the run log
    # yet; do that if a live run ever shows a denial.
    permission_denials: list[Any] = field(default_factory=list)


class ClaudeCodeMessages:
    def __init__(self, runner: Runner | None = None) -> None:
        self._run = runner or _run_claude

    def parse(self, **kwargs: Any) -> ParsedResponse:
        output_format = kwargs["output_format"]
        prompt = kwargs["messages"][-1]["content"]
        system = kwargs["system"] + SHAPE_INSTRUCTION.format(
            schema=json.dumps(output_format.model_json_schema(), indent=2)
        )

        argv = [
            settings.claude_bin,
            "-p",
            prompt,
            "--output-format",
            "json",
            "--system-prompt",
            system,
            "--model",
            kwargs["model"],
            "--disallowed-tools",
            *DENIED_TOOLS,
        ]
        effort = (kwargs.get("output_config") or {}).get("effort")
        if effort:
            argv += ["--effort", effort]

        with tempfile.TemporaryDirectory() as sandbox:
            raw = self._run(argv, cwd=sandbox, env=_subprocess_env(), timeout=settings.claude_timeout)

        envelope = _envelope(raw)
        return ParsedResponse(
            parsed_output=output_format.model_validate_json(_json_span(str(envelope["result"]))),
            stop_reason=str(envelope.get("stop_reason") or "end_turn"),
            permission_denials=list(envelope.get("permission_denials") or []),
        )


def _subprocess_env() -> dict[str, str]:
    """ANTHROPIC_API_KEY outranks the OAuth token, so it must not reach the subprocess.

    Leaving it set would silently bill the request to the API instead of the subscription
    — the whole point of this path.
    """
    env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
    token = settings.claude_code_oauth_token or os.environ.get("CLAUDE_CODE_OAUTHTOKEN", "")
    if not token:
        raise RuntimeError(
            "no subscription token — run `claude setup-token` and put the result in .env "
            "as CLAUDE_CODE_OAUTHTOKEN, or set answer_provider=api and use an API key"
        )
    env["CLAUDE_CODE_OAUTHTOKEN"] = token
    return env


def _run_claude(argv: list[str], *, cwd: str, env: dict[str, str], timeout: float) -> str:
    result = subprocess.run(
        argv, cwd=cwd, env=env, timeout=timeout, capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude exited {result.returncode}: {result.stderr.strip()[:400]}")
    return result.stdout


def _envelope(raw: str) -> dict[str, Any]:
    """The CLI's own `--output-format json` object.

    Verified live: {"type": "result", "subtype": "success", "is_error": false,
    "result": "<text>", "stop_reason": ..., "permission_denials": [...], "usage": {...}}.
    """
    envelope = json.loads(raw)
    if not isinstance(envelope, dict) or "result" not in envelope:
        raise RuntimeError(f"unexpected --output-format json envelope: {raw[:200]}")
    if envelope.get("is_error"):
        raise RuntimeError(f"claude reported an error: {str(envelope.get('result'))[:400]}")
    return envelope


def _json_span(text: str) -> str:
    """The object the model was asked for, even if it arrived wrapped.

    The prompt asks for bare JSON, but without schema enforcement that is a request, not
    a guarantee — markdown fences and a leading sentence both happen.
    """
    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped
    start, end = stripped.find("{"), stripped.rfind("}")
    if start == -1 or end <= start:
        raise ValueError(f"no JSON object in model output: {stripped[:200]}")
    return stripped[start : end + 1]


def sandbox_is_empty(path: Path) -> bool:
    """Exposed for the test that pins the load-bearing guard."""
    return not any(path.iterdir())
