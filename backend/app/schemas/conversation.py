from datetime import datetime
from pydantic import BaseModel, ConfigDict


class SourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    message_id: int
    document_id: int
    page_number: int
    relevance_score: float | None = None
    rank: int
    paper_title: str | None = None


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: int
    role: str
    content: str
    created_at: datetime
    sources: list[SourceResponse] = []


class ConversationCreate(BaseModel):
    title: str | None = None


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str | None = None
    created_at: datetime
    updated_at: datetime
    message_count: int | None = None


class ConversationDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str | None = None
    created_at: datetime
    updated_at: datetime
    messages: list[MessageResponse] = []
