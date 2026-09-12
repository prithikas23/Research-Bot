from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    conversation_id: int | None = Field(default=None, description="Optional existing conversation ID")
    question: str = Field(min_length=1, description="User question about uploaded research papers")


class SourceItem(BaseModel):
    paper_title: str
    page_number: int
    score: float
    rank: int


class ChatResponse(BaseModel):
    conversation_id: int
    answer: str
    sources: list[SourceItem] = []
