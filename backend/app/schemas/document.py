from datetime import datetime
from pydantic import BaseModel, ConfigDict


class DocumentBase(BaseModel):
    original_filename: str
    stored_filename: str
    file_size: int | None = None
    page_count: int | None = None
    status: str = "uploaded"


class DocumentResponse(DocumentBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class DocumentUploadResponse(BaseModel):
    message: str
    document: DocumentResponse
