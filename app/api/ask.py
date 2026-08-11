from fastapi import APIRouter, Depends

from app.agents.answer_agent import AnswerAgent
from app.core.dependencies import get_answer_agent, get_retriever
from app.models.schemas.ask import AskRequest, AskResponse
from app.observability import log_run
from app.rag.retriever import HybridRetriever

router = APIRouter(tags=["ask"])


@router.post("/ask", response_model=AskResponse)
def ask(
    request: AskRequest,
    retriever: HybridRetriever = Depends(get_retriever),
    agent: AnswerAgent = Depends(get_answer_agent),
) -> AskResponse:
    hits = retriever.search(request.text)
    response, rejected = agent.answer(request.text, hits)
    log_run(request.text, hits, response, rejected)
    return response
