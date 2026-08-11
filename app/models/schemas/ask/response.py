from pydantic import BaseModel


class Source(BaseModel):
    """One verified citation. Title and page come from the chunk, never from the model."""

    chunk_id: str
    title: str
    page: str  # "Ch.1, p.1" or "Ch.1, p.1-2"
    quote: str


class AskResponse(BaseModel):
    text: str
    sources: list[Source] = []
    refused: bool = False
