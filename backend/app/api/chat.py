import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import get_db
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.source import MessageSource
from app.models.document import Document
from app.schemas.chat import ChatRequest, ChatResponse, SourceItem
from app.services.retrieval_service import retrieval_service
from app.services.llm_service import llm_service
from app.services.greeting_service import detect_greeting

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def chat(payload: ChatRequest, db: Session = Depends(get_db)):
    """
    RAG chat endpoint:
    1. Resolve/create conversation in PostgreSQL.
    2. Save user message.
    3. Retrieve recent conversation history.
    4. Retrieve relevant chunks from ChromaDB with page metadata.
    5. Generate grounded response with Groq LLM.
    6. Save assistant message and message sources in PostgreSQL.
    7. Return response with top-3 sources.
    """
    question = payload.question.strip()
    if not question:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question cannot be empty.",
        )

    # 1. Resolve conversation
    conv = None
    if payload.conversation_id is not None:
        conv = db.query(Conversation).filter(Conversation.id == payload.conversation_id).first()

    if conv is None:
        # Create a new conversation using first 40 chars of question as title
        title = (question[:40] + "...") if len(question) > 40 else question
        conv = Conversation(title=title)
        db.add(conv)
        db.commit()
        db.refresh(conv)

    # 2. Save user message
    user_msg = Message(
        conversation_id=conv.id,
        role="user",
        content=question,
    )
    db.add(user_msg)
    db.commit()

    # 3. Retrieve recent conversation history (excluding the current user message)
    recent_messages = (
        db.query(Message)
        .filter(Message.conversation_id == conv.id, Message.id != user_msg.id)
        .order_by(Message.created_at.asc())
        .limit(6)
        .all()
    )
    conversation_history = [{"role": m.role, "content": m.content} for m in recent_messages]

    # 4. Check for greeting-only or identity queries first (no RAG, no ChromaDB)
    greeting_answer = detect_greeting(question)
    if greeting_answer:
        answer = greeting_answer
        raw_sources = []
    else:
        # Check for refreshed/completed documents
        refreshed_docs = (
            db.query(Document.id)
            .filter(Document.status.in_(["refreshed", "completed"]))
            .all()
        )
        refreshed_ids = {d[0] for d in refreshed_docs}

        if not refreshed_ids:
            context_chunks, raw_sources = [], []
            answer = (
                "No refreshed documents are currently indexed for search. "
                "Please go to the **Files** tab, upload a PDF, and click **Refresh** to make it searchable."
            )
        else:
            # Retrieve research paper context strictly from refreshed documents
            try:
                context_chunks, raw_sources = retrieval_service.retrieve(
                    query=question,
                    allowed_document_ids=refreshed_ids,
                )
            except Exception as e:
                logger.error(f"Retrieval error: {e}", exc_info=True)
                context_chunks, raw_sources = [], []

            # 5. Generate grounded answer with Groq LLM
            try:
                answer = llm_service.generate_answer(
                    query=question,
                    context_chunks=context_chunks,
                    conversation_history=conversation_history,
                )
            except Exception as e:
                logger.error(f"LLM generation error: {e}", exc_info=True)
                answer = "An error occurred while generating the answer from the research papers. Please try again."

    # 6. Save assistant message
    assistant_msg = Message(
        conversation_id=conv.id,
        role="assistant",
        content=answer,
    )
    db.add(assistant_msg)
    db.commit()
    db.refresh(assistant_msg)

    # 7. Save top sources to message_sources table
    top_sources = raw_sources[:3]
    for s in top_sources:
        doc_id = s.get("document_id")
        # Ensure document exists before adding foreign key
        if doc_id and db.query(Document.id).filter(Document.id == doc_id).first():
            src_record = MessageSource(
                message_id=assistant_msg.id,
                document_id=doc_id,
                page_number=int(s["page_number"]),
                relevance_score=float(s["score"]),
                rank=int(s["rank"]),
            )
            db.add(src_record)

    # Update conversation timestamp
    conv.updated_at = func.now()
    db.commit()

    # 8. Return formatted response
    response_sources = [
        SourceItem(
            paper_title=s["paper_title"],
            page_number=int(s["page_number"]),
            score=float(s["score"]),
            rank=int(s["rank"]),
        )
        for s in top_sources
    ]

    return ChatResponse(
        conversation_id=conv.id,
        answer=answer,
        sources=response_sources,
    )
