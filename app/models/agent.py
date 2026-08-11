"""Types the *model* fills in. Nothing here carries a page number or a title.

Citations are built in two steps on purpose: the model names which excerpt and which
sentence it used, and the code looks the title and page up from the `Chunk` record. A
model that were asked for page numbers could invent them.
"""

from pydantic import BaseModel, Field


class Citation(BaseModel):
    chunk_id: str = Field(description="id of the excerpt this claim rests on")
    quote: str = Field(description="the sentence from that excerpt, copied verbatim")


class AnswerOut(BaseModel):
    text: str = Field(description="the answer, or the refusal sentence")
    citations: list[Citation] = Field(default_factory=list)
