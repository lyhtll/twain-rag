from functools import lru_cache

from fastapi import Depends

from app.agents.answer_agent import AnswerAgent
from app.rag.indexer import Embedder, Index
from app.rag.retriever import HybridRetriever


@lru_cache(maxsize=1)
def get_index() -> Index:
    """One index per process. Loading it per request would reload a 133MB model."""
    return Index.load()


@lru_cache(maxsize=1)
def get_embedder() -> Embedder:
    return Embedder()


def get_retriever(index: Index = Depends(get_index)) -> HybridRetriever:
    return HybridRetriever(index, embedder=get_embedder())


@lru_cache(maxsize=1)
def get_answer_agent() -> AnswerAgent:
    return AnswerAgent()
