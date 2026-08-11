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
    dup_min_words: int = 25  # Ch1<->Ch3 near-duplicate threshold
    ch2_title_chars: int = 40  # derived title length for untitled quotations

    refusal_text: str = "이 책에는 없습니다"


settings = Settings()
