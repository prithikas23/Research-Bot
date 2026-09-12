from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import get_db
from app.models.conversation import Conversation
from app.models.message import Message
from app.schemas.conversation import (
    ConversationCreate,
    ConversationResponse,
    ConversationDetailResponse,
    MessageResponse,
    SourceResponse,
)

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
def create_conversation(
    payload: ConversationCreate | None = None,
    db: Session = Depends(get_db),
):
    title = payload.title if payload and payload.title else "New Conversation"
    conv = Conversation(title=title)
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


@router.get("", response_model=list[ConversationResponse])
def get_conversations(db: Session = Depends(get_db)):
    """List all conversations with message count."""
    conversations = db.query(Conversation).order_by(Conversation.updated_at.desc()).all()
    results = []
    for conv in conversations:
        msg_count = db.query(func.count(Message.id)).filter(Message.conversation_id == conv.id).scalar()
        results.append(
            ConversationResponse(
                id=conv.id,
                title=conv.title,
                created_at=conv.created_at,
                updated_at=conv.updated_at,
                message_count=msg_count or 0,
            )
        )
    return results


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
def get_conversation(conversation_id: int, db: Session = Depends(get_db)):
    """Get single conversation along with its full messages and sources."""
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")

    formatted_messages = []
    for msg in conv.messages:
        sources = [
            SourceResponse(
                id=s.id,
                message_id=s.message_id,
                document_id=s.document_id,
                page_number=s.page_number,
                relevance_score=s.relevance_score,
                rank=s.rank,
                paper_title=s.document.original_filename if s.document else None,
            )
            for s in msg.sources
        ]
        formatted_messages.append(
            MessageResponse(
                id=msg.id,
                conversation_id=msg.conversation_id,
                role=msg.role,
                content=msg.content,
                created_at=msg.created_at,
                sources=sources,
            )
        )

    return ConversationDetailResponse(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        messages=formatted_messages,
    )


@router.delete("/{conversation_id}", status_code=status.HTTP_200_OK)
def delete_conversation(conversation_id: int, db: Session = Depends(get_db)):
    """Delete conversation and cascade delete its messages and sources."""
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")

    db.delete(conv)
    db.commit()
    return {"message": f"Conversation {conversation_id} deleted successfully."}


@router.get("/{conversation_id}/messages", response_model=list[MessageResponse])
def get_conversation_messages(conversation_id: int, db: Session = Depends(get_db)):
    """Get all messages for a specific conversation."""
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")

    results = []
    for msg in conv.messages:
        sources = [
            SourceResponse(
                id=s.id,
                message_id=s.message_id,
                document_id=s.document_id,
                page_number=s.page_number,
                relevance_score=s.relevance_score,
                rank=s.rank,
                paper_title=s.document.original_filename if s.document else None,
            )
            for s in msg.sources
        ]
        results.append(
            MessageResponse(
                id=msg.id,
                conversation_id=msg.conversation_id,
                role=msg.role,
                content=msg.content,
                created_at=msg.created_at,
                sources=sources,
            )
        )
    return results
