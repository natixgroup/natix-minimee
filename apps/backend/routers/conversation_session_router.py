"""
Conversation Session Router
Handles CRUD operations for conversation sessions and getting-to-know sessions
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime
from db.database import get_db
from models import ConversationSession, Message, Embedding
from schemas import (
    ConversationSessionCreate, ConversationSessionUpdate, ConversationSessionResponse,
    GettingToKnowAnswer, GettingToKnowQuestionResponse
)
from services.getting_to_know_session import (
    create_getting_to_know_session,
    get_next_question,
    save_answer_to_user_info
)
from services.logs_service import log_to_db
import uuid

router = APIRouter(prefix="/conversation-sessions", tags=["conversation-sessions"])


@router.get("", response_model=List[ConversationSessionResponse])
async def get_conversation_sessions(
    user_id: int = Query(...),
    session_type: Optional[str] = Query(None),
    include_deleted: bool = Query(False),
    db: Session = Depends(get_db)
):
    """
    Get all conversation sessions for a user
    """
    query = db.query(ConversationSession).filter(ConversationSession.user_id == user_id)
    
    if not include_deleted:
        query = query.filter(ConversationSession.deleted_at.is_(None))
    
    if session_type:
        query = query.filter(ConversationSession.session_type == session_type)
    
    sessions = query.order_by(ConversationSession.created_at.desc()).all()
    return sessions


@router.get("/{session_id}", response_model=ConversationSessionResponse)
async def get_conversation_session(
    session_id: int,
    user_id: int = Query(...),
    db: Session = Depends(get_db)
):
    """
    Get a specific conversation session
    """
    session = db.query(ConversationSession).filter(
        ConversationSession.id == session_id,
        ConversationSession.user_id == user_id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Conversation session not found")
    
    return session


@router.post("", response_model=ConversationSessionResponse)
async def create_conversation_session(
    session_data: ConversationSessionCreate,
    user_id: int = Query(...),
    db: Session = Depends(get_db)
):
    """
    Create a new conversation session
    """
    # Generate conversation_id if not provided
    conversation_id = session_data.conversation_id
    if not conversation_id:
        conversation_id = f"session-{user_id}-{uuid.uuid4().hex[:8]}"
    
    session = ConversationSession(
        user_id=user_id,
        session_type=session_data.session_type,
        title=session_data.title or f"Session {session_data.session_type}",
        conversation_id=conversation_id
    )
    
    db.add(session)
    db.commit()
    db.refresh(session)
    
    log_to_db(
        db,
        "INFO",
        f"Created conversation session {session.id} for user {user_id}",
        service="conversation_session_router",
        user_id=user_id,
        metadata={"session_id": session.id, "session_type": session_data.session_type}
    )
    
    return session


@router.put("/{session_id}", response_model=ConversationSessionResponse)
async def update_conversation_session(
    session_id: int,
    session_data: ConversationSessionUpdate,
    user_id: int = Query(...),
    db: Session = Depends(get_db)
):
    """
    Update a conversation session (title, soft delete)
    """
    session = db.query(ConversationSession).filter(
        ConversationSession.id == session_id,
        ConversationSession.user_id == user_id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Conversation session not found")
    
    if session_data.title is not None:
        session.title = session_data.title
    if session_data.deleted_at is not None:
        session.deleted_at = session_data.deleted_at
    
    session.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(session)
    
    return session


@router.delete("/{session_id}")
async def delete_conversation_session(
    session_id: int,
    user_id: int = Query(...),
    delete_embeddings: bool = Query(False),
    db: Session = Depends(get_db)
):
    """
    Delete a conversation session (soft delete)
    Optionally delete associated embeddings
    """
    session = db.query(ConversationSession).filter(
        ConversationSession.id == session_id,
        ConversationSession.user_id == user_id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Conversation session not found")
    
    # Soft delete
    session.deleted_at = datetime.utcnow()
    
    # Optionally delete embeddings
    if delete_embeddings:
        # Get all messages for this conversation
        messages = db.query(Message).filter(
            Message.conversation_id == session.conversation_id,
            Message.user_id == user_id
        ).all()
        
        message_ids = [msg.id for msg in messages]
        
        if message_ids:
            # Delete embeddings for these messages
            deleted_count = db.query(Embedding).filter(
                Embedding.message_id.in_(message_ids)
            ).delete(synchronize_session=False)
            
            log_to_db(
                db,
                "INFO",
                f"Deleted {deleted_count} embeddings for session {session_id}",
                service="conversation_session_router",
                user_id=user_id,
                metadata={"session_id": session_id, "embeddings_deleted": deleted_count}
            )
    
    db.commit()
    
    log_to_db(
        db,
        "INFO",
        f"Deleted conversation session {session_id} for user {user_id}",
        service="conversation_session_router",
        user_id=user_id,
        metadata={"session_id": session_id, "embeddings_deleted": delete_embeddings}
    )
    
    return {
        "message": "Conversation session deleted successfully",
        "embeddings_deleted": delete_embeddings
    }


@router.get("/{session_id}/messages")
async def get_session_messages(
    session_id: int,
    user_id: int = Query(...),
    limit: int = Query(100),
    db: Session = Depends(get_db)
):
    """
    Get messages for a conversation session
    """
    session = db.query(ConversationSession).filter(
        ConversationSession.id == session_id,
        ConversationSession.user_id == user_id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Conversation session not found")
    
    messages = db.query(Message).filter(
        Message.conversation_id == session.conversation_id,
        Message.user_id == user_id
    ).order_by(Message.timestamp.asc()).limit(limit).all()
    
    return [
        {
            "id": msg.id,
            "content": msg.content,
            "sender": msg.sender,
            "timestamp": msg.timestamp.isoformat(),
            "source": msg.source
        }
        for msg in messages
    ]


# Getting to Know endpoints
@router.post("/getting-to-know/start", response_model=ConversationSessionResponse)
async def start_getting_to_know_session(
    user_id: int = Query(...),
    db: Session = Depends(get_db)
):
    """
    Start a new "getting to know" session
    """
    session = create_getting_to_know_session(db, user_id)
    return session


@router.post("/getting-to-know/{session_id}/answer", response_model=GettingToKnowQuestionResponse)
async def answer_getting_to_know_question(
    session_id: int,
    answer_data: GettingToKnowAnswer,
    user_id: int = Query(...),
    db: Session = Depends(get_db)
):
    """
    Submit an answer to a getting-to-know question and get the next question
    """
    # Verify session belongs to user
    session = db.query(ConversationSession).filter(
        ConversationSession.id == session_id,
        ConversationSession.user_id == user_id,
        ConversationSession.session_type == 'getting_to_know'
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Getting-to-know session not found")
    
    # Save answer
    if answer_data.answer and answer_data.question_type:
        save_answer_to_user_info(db, session_id, answer_data.question_type, answer_data.answer)
    
    # Get next question
    next_question = get_next_question(
        db,
        session_id,
        last_answer=answer_data.answer,
        last_question_type=answer_data.question_type
    )
    
    return next_question


@router.get("/getting-to-know/{session_id}/question", response_model=GettingToKnowQuestionResponse)
async def get_current_question(
    session_id: int,
    user_id: int = Query(...),
    db: Session = Depends(get_db)
):
    """
    Get the current question for a getting-to-know session (without submitting an answer)
    """
    # Verify session belongs to user
    session = db.query(ConversationSession).filter(
        ConversationSession.id == session_id,
        ConversationSession.user_id == user_id,
        ConversationSession.session_type == 'getting_to_know'
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Getting-to-know session not found")
    
    # Get next question (without saving answer)
    question = get_next_question(db, session_id)
    
    return question


