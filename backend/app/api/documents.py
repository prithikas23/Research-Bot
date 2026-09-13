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

# Router defined without fixed prefix so it can be mounted under both /documents and /files
router = APIRouter(tags=["documents"])


@router.post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Upload PDF document:
    - Validates file format and size.
    - Saves locally to disk.
    - Inspects page count.
    - Creates database record with status 'not_refreshed'.
    - Does NOT index into ChromaDB until explicitly refreshed.
    """
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

    # 5. Extract page count from PDF
    page_count = 0
    try:
        meta = pdf_service.get_pdf_metadata(file_path)
        page_count = meta.get("page_count", 0)
    except Exception as e:
        logger.warning(f"Could not read PDF metadata for {file.filename}: {e}")

    # 6. Create document DB record with status 'not_refreshed'
    db_document = Document(
        original_filename=file.filename,
        stored_filename=stored_filename,
        file_path=str(file_path),
        file_size=file_size,
        page_count=page_count,
        status="not_refreshed",
    )
    db.add(db_document)
    db.commit()
    db.refresh(db_document)

    return DocumentUploadResponse(
        message="File uploaded successfully. Click Refresh to index it for chat.",
        document=db_document,
    )


@router.post("/{document_id}/refresh", response_model=DocumentUploadResponse, status_code=status.HTTP_200_OK)
def refresh_document(
    document_id: int,
    db: Session = Depends(get_db),
):
    """
    Explicitly chunk, embed, and index a document into ChromaDB.
    Updates document status to 'refreshed'.
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    local_path = Path(doc.file_path)
    if not local_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PDF file not found on disk.")

    doc.status = "refreshing"
    db.commit()
    db.refresh(doc)

    try:
        # Extract metadata and pages
        meta = pdf_service.get_pdf_metadata(local_path)
        page_count = meta.get("page_count", 0)
        paper_title = meta.get("title") or Path(doc.original_filename).stem

        pages_data = pdf_service.extract_pages(local_path)
        actual_pages = len(pages_data) if pages_data else page_count

        # Create page-aware chunks
        chunks = chunking_service.create_page_aware_chunks(
            pages_data=pages_data,
            document_id=doc.id,
            paper_title=paper_title,
            source_file=doc.original_filename,
        )

        # Remove existing vectors in ChromaDB for this document to avoid duplication
        delete_document_chunks(doc.id)

        # Generate embeddings and store in ChromaDB
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

        # Update DB record to 'refreshed'
        doc.page_count = actual_pages
        doc.status = "refreshed"
        db.commit()
        db.refresh(doc)

        return DocumentUploadResponse(
            message=f"Successfully indexed {actual_pages} pages ({len(chunks)} chunks).",
            document=doc,
        )

    except Exception as e:
        logger.error(f"Failed to refresh document {doc.id}: {e}", exc_info=True)
        doc.status = "failed"
        db.commit()
        db.refresh(doc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to refresh and index document: {str(e)}",
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
