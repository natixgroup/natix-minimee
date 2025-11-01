"""
Core Minimee messaging endpoints
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from db.database import get_db
from models import Message
from schemas import MessageCreate, MessageOptions, ApprovalRequest, ApprovalResponse
from services.approval_flow import generate_response_options, process_approval, store_email_draft_proposals
from services.embeddings import store_embedding
from services.logs_service import log_to_db

router = APIRouter()


@router.post("/minimee/message", response_model=MessageOptions)
async def process_message(
    message_data: MessageCreate,
    db: Session = Depends(get_db)
):
    """
    Process incoming message
    - Store message in DB
    - Generate embedding
    - Use RAG to find context
    - Generate multiple response options
    """
    try:
        # Store message
        message = Message(**message_data.model_dump())
        db.add(message)
        db.commit()
        db.refresh(message)
        
        # Generate embedding
        store_embedding(db, message.content, message_id=message.id)
        
        # Generate response options
        options = generate_response_options(db, message)
        
        log_to_db(db, "INFO", f"Processed message {message.id}, generated {len(options.options)} options", service="minimee")
        
        return options
    
    except Exception as e:
        db.rollback()
        log_to_db(db, "ERROR", f"Message processing error: {str(e)}", service="minimee")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/minimee/approve", response_model=ApprovalResponse)
async def approve_response(
    approval_request: ApprovalRequest,
    db: Session = Depends(get_db)
):
    """
    Process user approval decision
    Actions: "yes", "no", "maybe", "reformulate"
    """
    try:
        result = process_approval(db, approval_request)
        
        log_to_db(
            db,
            "INFO",
            f"Approval processed: {approval_request.action} for message {approval_request.message_id}",
            service="minimee"
        )
        
        return ApprovalResponse(**result)
    
    except Exception as e:
        log_to_db(db, "ERROR", f"Approval error: {str(e)}", service="minimee")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/minimee/email-draft", response_model=MessageOptions)
async def propose_email_draft(
    thread_id: str,
    user_id: int = 1,  # TODO: Get from auth
    db: Session = Depends(get_db)
):
    """
    Generate and propose email draft options for a Gmail thread
    Stores proposals for approval and can send via WhatsApp
    """
    try:
        from services.email_draft import generate_email_drafts_sync
        from services.logs_service import log_to_db
        
        # Generate draft options
        drafts = generate_email_drafts_sync(db, thread_id, user_id, num_options=3)
        
        # Create MessageOptions
        message_options = MessageOptions(
            options=drafts,
            message_id=0,  # Placeholder for email drafts
            conversation_id=thread_id
        )
        
        # Store for approval
        store_email_draft_proposals(thread_id, message_options)
        
        log_to_db(
            db,
            "INFO",
            f"Proposed {len(drafts)} email draft options for thread {thread_id}",
            service="minimee"
        )
        
        # TODO: Send proposals via WhatsApp bridge
        # Format: "📧 Email draft for [subject]:\nA) [draft1]\nB) [draft2]\nC) [draft3]"
        
        return message_options
    
    except ValueError as e:
        log_to_db(db, "ERROR", f"Email draft error: {str(e)}", service="minimee")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log_to_db(db, "ERROR", f"Email draft error: {str(e)}", service="minimee")
        raise HTTPException(status_code=500, detail=str(e))

