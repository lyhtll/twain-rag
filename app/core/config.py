from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str = ""
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

    refusal_text: str = "이 책에는 없습니다"


settings = Settings()
