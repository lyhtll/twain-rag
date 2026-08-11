from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    text: str = Field(min_length=1, description="an English question about Mark Twain")
