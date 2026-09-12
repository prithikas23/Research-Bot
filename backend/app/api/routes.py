from fastapi import APIRouter
from pydantic import BaseModel, Field
from app.services.vector_service import add_documents, search_documents, collection_count

router = APIRouter()


class AddDocumentsRequest(BaseModel):
    ids: list[str] = Field(min_length=1)
    documents: list[str] = Field(min_length=1)
    metadatas: list[dict] = Field(min_length=1)
    embeddings: list[list[float]] | None = None


class SearchRequest(BaseModel):
    query_embedding: list[float]
    top_k: int = Field(default=5, ge=1, le=20)


@router.get("/chroma/status")
def chroma_status():
    return {
        "collection": "research_papers",
        "document_count": collection_count()
    }


@router.post("/chroma/documents")
def add_to_chroma(payload: AddDocumentsRequest):
    add_documents(
        ids=payload.ids,
        documents=payload.documents,
        metadatas=payload.metadatas,
        embeddings=payload.embeddings
    )
    return {
        "message": "Documents added successfully",
        "document_count": collection_count()
    }


@router.post("/chroma/search")
def search(payload: SearchRequest):
    return search_documents(
        query_embedding=payload.query_embedding,
        top_k=payload.top_k
    )
