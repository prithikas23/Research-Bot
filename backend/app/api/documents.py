import os
import shutil
import uuid
import logging
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.document import Document
from app.schemas.document import DocumentResponse, DocumentUploadResponse
from app.services.pdf_service import pdf_service
from app.services.chunking_service import chunking_service
from app.services.embedding_service import embedding_service
from app.services.vector_service import add_documents, delete_document_chunks

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    # 1. Validate PDF file type
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are supported.",
        )

    # 2. Ensure target upload directory exists
    upload_dir = settings.resolved_upload_dir
    upload_dir.mkdir(parents=True, exist_ok=True)

    # 3. Read content and validate file size
    contents = await file.read()
    file_size = len(contents)
    max_size_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    if file_size > max_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File exceeds maximum allowed size of {settings.MAX_FILE_SIZE_MB}MB.",
        )

    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    # 4. Generate unique stored filename to prevent collisions
    safe_basename = Path(file.filename).stem.replace(" ", "_")
    unique_suffix = uuid.uuid4().hex[:8]
    stored_filename = f"{unique_suffix}_{safe_basename}.pdf"
    file_path = upload_dir / stored_filename

    # Save PDF locally
    with open(file_path, "wb") as f:
        f.write(contents)

    # 5. Create document DB record with status 'processing'
    db_document = Document(
        original_filename=file.filename,
        stored_filename=stored_filename,
        file_path=str(file_path),
        file_size=file_size,
        status="processing",
    )
    db.add(db_document)
    db.commit()
    db.refresh(db_document)

    try:
        # 6. Extract PDF pages and metadata
        meta = pdf_service.get_pdf_metadata(file_path)
        page_count = meta.get("page_count", 0)
        paper_title = meta.get("title") or Path(file.filename).stem

        pages_data = pdf_service.extract_pages(file_path)

        # 7. Create page-aware chunks
        chunks = chunking_service.create_page_aware_chunks(
            pages_data=pages_data,
            document_id=db_document.id,
            paper_title=paper_title,
            source_file=file.filename,
        )

        # 8. Generate embeddings and store in ChromaDB
        if chunks:
            chunk_texts = [c["text"] for c in chunks]
            chunk_ids = [c["id"] for c in chunks]
            chunk_metas = [c["metadata"] for c in chunks]

            embeddings = embedding_service.embed_texts(chunk_texts)
            add_documents(
                ids=chunk_ids,
                documents=chunk_texts,
                metadatas=chunk_metas,
                embeddings=embeddings,
            )

        # 9. Update DB record to completed
        db_document.page_count = page_count
        db_document.status = "completed"
        db.commit()
        db.refresh(db_document)

        return DocumentUploadResponse(
            message=f"Successfully processed and indexed {page_count} pages ({len(chunks)} chunks).",
            document=db_document,
        )

    except Exception as e:
        logger.error(f"Failed to process document {db_document.id}: {e}", exc_info=True)
        db_document.status = "failed"
        db.commit()
        db.refresh(db_document)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process research paper PDF: {str(e)}",
        )


@router.get("", response_model=list[DocumentResponse])
def get_documents(db: Session = Depends(get_db)):
    """List all documents."""
    return db.query(Document).order_by(Document.created_at.desc()).all()


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(document_id: int, db: Session = Depends(get_db)):
    """Get single document details."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    return doc


@router.delete("/{document_id}", status_code=status.HTTP_200_OK)
def delete_document(document_id: int, db: Session = Depends(get_db)):
    """
    Delete document:
    1. Remove local PDF file.
    2. Remove ChromaDB chunks.
    3. Remove PostgreSQL document record.
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    # 1. Remove local PDF
    try:
        local_path = Path(doc.file_path)
        if local_path.exists():
            local_path.unlink()
    except Exception as e:
        logger.warning(f"Could not delete local file {doc.file_path}: {e}")

    # 2. Remove ChromaDB chunks
    try:
        delete_document_chunks(doc.id)
    except Exception as e:
        logger.warning(f"Could not delete Chroma chunks for doc {doc.id}: {e}")

    # 3. Delete PostgreSQL record (cascades to message_sources)
    db.delete(doc)
    db.commit()

    return {"message": f"Document {document_id} and associated embeddings deleted successfully."}
