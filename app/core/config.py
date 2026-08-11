from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # "claude_code" bills answer generation to a Claude Pro/Max subscription by shelling
    # out to `claude -p`; "api" uses the Messages API with an API key. See
    # app/agents/claude_code_client.py for what differs.
    answer_provider: str = "claude_code"

    anthropic_api_key: str = ""  # answer_provider="api"
    claude_code_oauth_token: str = ""  # answer_provider="claude_code"; `claude setup-token`
    claude_bin: str = "claude"
    claude_timeout: float = 180.0

    llm_model: str = "claude-opus-5"
    max_tokens: int = 4096

    embed_model: str = "BAAI/bge-small-en-v1.5"
    # bge asks for this prefix on the *query* side only; passages go in bare.
    query_prefix: str = "Represent this sentence for searching relevant passages: "

    book_path: Path = Path("data/book.pdf")
    chunks_path: Path = Path("data/chunks.jsonl")
    index_dir: Path = Path("index")
    runs_dir: Path = Path("runs")

    top_k: int = 3
    candidates: int = 10  # per retriever, before fusion
    rrf_k: int = 60
    # Near-duplicate detection (Ch1 <-> Ch3). Measured longest-match sizes on this book
    # fall in a clean band: genuine retellings are >= 23 words, coincidence tops out at
    # 8, and nothing lands in between — so any absolute threshold in 9..23 yields the
    # same pairs. 20 sits in the middle of that band.
    dup_min_words: int = 20
    # A short chunk can never reach the absolute threshold: Ch3's "real name" answer is
    # 8 words long and is verbatim the first sentence of Ch1 'Name'. The relative rule
    # catches those.
    dup_min_ratio: float = 0.8
    ch2_title_chars: int = 40  # derived title length for untitled quotations
    # Ch2 quotations are indexed with an attribution frame. Measured: it moves the median
    # dense rank of a Ch2 answer from 2 to 1 and rescues the worst cases (96 -> 1, 21 -> 3,
    # 9 -> 1), with no change to Ch1/Ch3 ranks. See agent_docs/rag.md.
    ch2_index_prefix: str = "Mark Twain said: "

    refusal_text: str = "이 책에는 없습니다"


settings = Settings()
