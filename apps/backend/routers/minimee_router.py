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
from services.action_logger import log_action, generate_request_id

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
    request_id = generate_request_id()
    
    try:
        # Store message first
        message = Message(**message_data.model_dump())
        db.add(message)
        db.commit()
        db.refresh(message)
        
        # 1. Log message arrival
        log_action(
            db=db,
            action_type="message_arrived",
            input_data={
                "content": message_data.content[:500],  # Limiter la taille
                "sender": message_data.sender,
                "source": message_data.source
            },
            message_id=message.id,
            conversation_id=message_data.conversation_id,
            request_id=request_id,
            user_id=message_data.user_id,
            source=message_data.source,
            status="success"
        )
        
        # 2. Generate embedding (sera loggé dans embeddings.py)
        store_embedding(db, message.content, message_id=message.id, request_id=request_id, user_id=message_data.user_id)
        db.commit()  # Commit embedding before generating options
        
        # 3-7. Generate response options (sera loggé dans approval_flow.py et rag.py)
        options = await generate_response_options(db, message, request_id=request_id)
        
        # 7. Log presentation to user
        log_action(
            db=db,
            action_type="user_presentation",
            input_data={
                "message_id": message.id,
                "options_count": len(options.options)
            },
            output_data={
                "options": options.options,  # Les propositions
                "message_id": options.message_id,
                "conversation_id": options.conversation_id
            },
            message_id=message.id,
            conversation_id=message.conversation_id,
            request_id=request_id,
            user_id=message_data.user_id,
            source=message_data.source,
            status="success"
        )
        
        log_to_db(db, "INFO", f"Processed message {message.id}, generated {len(options.options)} options", service="minimee")
        
        return options
    
    except Exception as e:
        db.rollback()
        log_action(
            db=db,
            action_type="message_arrived",
            input_data={
                "content": message_data.content[:500] if message_data else "N/A",
                "sender": message_data.sender if message_data else "N/A",
                "source": message_data.source if message_data else "N/A"
            },
            request_id=request_id,
            user_id=message_data.user_id if message_data else None,
            source=message_data.source if message_data else None,
            status="error",
            error_message=str(e)
        )
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
        # 8. Log user response
        message = db.query(Message).filter(Message.id == approval_request.message_id).first()
        request_id = generate_request_id()
        
        log_action(
            db=db,
            action_type="user_response",
            input_data={
                "message_id": approval_request.message_id,
                "action": approval_request.action,
                "option_index": approval_request.option_index,
                "type": approval_request.type
            },
            message_id=approval_request.message_id,
            conversation_id=message.conversation_id if message else None,
            request_id=request_id,
            user_id=message.user_id if message else None,
            source=message.source if message else None,
            status="success"
        )
        
        result = process_approval(db, approval_request)
        
        # 9. Log action executed
        log_action(
            db=db,
            action_type="action_executed",
            input_data={
                "message_id": approval_request.message_id,
                "action": approval_request.action,
                "option_index": approval_request.option_index
            },
            output_data={
                "status": result.get("status"),
                "sent": result.get("sent", False),
                "selected_option": result.get("selected_option") or result.get("selected_draft")
            },
            message_id=approval_request.message_id,
            conversation_id=message.conversation_id if message else None,
            request_id=request_id,
            user_id=message.user_id if message else None,
            source=message.source if message else None,
            status="success" if result.get("status") != "error" else "error",
            error_message=result.get("message") if result.get("status") == "error" else None
        )
        
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

