"""Chunk persistence and the two search indexes.

`Index` owns three pieces of state that must stay aligned — the chunks, the embedding
matrix, and the id list naming its rows. If the row order and the ids drift apart the
system cites the wrong chunk while looking perfectly healthy, so they are built, saved,
and loaded together, and `load()` checks the alignment.
"""

import json
import pickle
from pathlib import Path
from typing import Any, Protocol

import numpy as np
from rank_bm25 import BM25Okapi

from app.core.config import settings
from app.models.chunk import Chunk
from app.rag.text import doc_for, tokenize

BM25_FILE = "bm25.pkl"
EMBEDDINGS_FILE = "embeddings.npy"
IDS_FILE = "chunk_ids.json"


def save_chunks(chunks: list[Chunk], path: Path = settings.chunks_path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for chunk in chunks:
            fh.write(chunk.model_dump_json() + "\n")


def load_chunks(path: Path = settings.chunks_path) -> list[Chunk]:
    if not path.exists():
        raise FileNotFoundError(f"{path} is missing — run: python -m scripts.ingest data/book.pdf")
    with path.open(encoding="utf-8") as fh:
        return [Chunk.model_validate_json(line) for line in fh if line.strip()]


class EmbeddingModel(Protocol):
    """The slice of sentence-transformers this project uses. Tests inject a fake."""

    def encode(self, sentences: list[str], normalize_embeddings: bool) -> Any: ...


class Embedder:
    """bge-small-en-v1.5. The only place the query prefix is applied.

    bge asks for an instruction prefix on the query side and none on the passage side;
    applying it to both, or neither, quietly degrades retrieval. Keeping the asymmetry in
    one class is what stops that from drifting.
    """

    def __init__(self, model: EmbeddingModel | None = None) -> None:
        self._model = model or _load_default_model()

    def embed_passages(self, texts: list[str]) -> np.ndarray:
        return self._encode(texts)

    def embed_query(self, text: str) -> np.ndarray:
        return self._encode([settings.query_prefix + text])[0]

    def _encode(self, texts: list[str]) -> np.ndarray:
        vectors = self._model.encode(texts, normalize_embeddings=True)
        return np.asarray(vectors, dtype=np.float32)


def _load_default_model() -> EmbeddingModel:
    # Imported lazily so that importing this module — which tests and the ingest script
    # both do — never pulls in torch or downloads a model.
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(settings.embed_model)


class Index:
    def __init__(
        self, chunks: list[Chunk], bm25: BM25Okapi, embeddings: np.ndarray, ids: list[str]
    ) -> None:
        if len(ids) != embeddings.shape[0]:
            raise ValueError(f"{len(ids)} ids but {embeddings.shape[0]} embedding rows")
        self.chunks = chunks
        self.by_id = {c.id: c for c in chunks}
        self._bm25 = bm25
        self._embeddings = embeddings
        self._ids = ids

    @classmethod
    def build(cls, chunks: list[Chunk], embedder: Embedder | None = None) -> "Index":
        if not chunks:
            raise ValueError("cannot build an index from zero chunks")
        embedder = embedder or Embedder()
        docs = [doc_for(c) for c in chunks]
        return cls(
            chunks=chunks,
            bm25=BM25Okapi([tokenize(d) for d in docs]),
            embeddings=embedder.embed_passages(docs),
            ids=[c.id for c in chunks],
        )

    def save(self, directory: Path = settings.index_dir) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        (directory / BM25_FILE).write_bytes(pickle.dumps(self._bm25))
        np.save(directory / EMBEDDINGS_FILE, self._embeddings)
        (directory / IDS_FILE).write_text(json.dumps(self._ids), encoding="utf-8")

    @classmethod
    def load(
        cls, directory: Path = settings.index_dir, chunks_path: Path = settings.chunks_path
    ) -> "Index":
        missing = [f for f in (BM25_FILE, EMBEDDINGS_FILE, IDS_FILE) if not (directory / f).exists()]
        if missing:
            raise FileNotFoundError(
                f"{directory} is missing {missing} — run: python -m scripts.ingest data/book.pdf"
            )
        chunks = load_chunks(chunks_path)
        ids = json.loads((directory / IDS_FILE).read_text(encoding="utf-8"))
        index = cls(
            chunks=chunks,
            bm25=pickle.loads((directory / BM25_FILE).read_bytes()),
            embeddings=np.load(directory / EMBEDDINGS_FILE),
            ids=ids,
        )
        unknown = [i for i in ids if i not in index.by_id]
        if unknown:
            raise ValueError(
                f"index names {len(unknown)} chunk ids absent from {chunks_path} "
                f"(first: {unknown[:3]}) — the index and the chunks are from different runs"
            )
        return index

    def search_bm25(self, question: str, n: int) -> list[str]:
        # A zero BM25 score means the question shares no token with the chunk, so it is
        # not a candidate at all — unlike a merely weak dense score.
        scores = self._bm25.get_scores(tokenize(question))
        order = np.argsort(scores)[::-1][:n]
        return [self._ids[i] for i in order if scores[i] > 0]

    def search_dense(self, query_vector: np.ndarray, n: int) -> list[str]:
        """Takes a vector, not text — the embedder belongs to the caller.

        Embeddings are L2-normalised, so a dot product *is* cosine similarity and the
        whole search is one matrix-vector product.

        ponytail: brute force over 187 rows (287KB) — microseconds, and exact. An ANN
        index would trade recall for speed on the part that is not the bottleneck (query
        embedding costs ~10-20ms, the search ~1000x less); revisit past ~100k chunks.
        """
        order = np.argsort(self._embeddings @ query_vector)[::-1][:n]
        return [self._ids[i] for i in order]
