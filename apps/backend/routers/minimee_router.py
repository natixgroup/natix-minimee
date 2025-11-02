"""
Core Minimee messaging endpoints
"""
import json
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from datetime import datetime
from db.database import get_db
from models import Message
from schemas import MessageCreate, MessageOptions, ApprovalRequest, ApprovalResponse, ChatMessageRequest, ChatMessageResponse
from services.approval_flow import generate_response_options, process_approval, store_email_draft_proposals, send_approval_request_notification, send_pending_approval_reminders
from models import PendingApproval
from services.embeddings import store_embedding
from services.logs_service import log_to_db
from services.action_logger import log_action, generate_request_id
from services.rag import retrieve_context, build_prompt_with_context
from services.agent_manager import select_agent_for_context
from services.llm_router import generate_llm_response_stream, generate_llm_response
from services.websocket_manager import websocket_manager
from config import settings

router = APIRouter()


@router.post("/minimee/message/display-only")
async def display_message_only(
    message_data: MessageCreate,
    db: Session = Depends(get_db)
):
    """
    Store message in DB and broadcast via WebSocket for display only
    Does not generate response options - used for user's own messages in Minimee TEAM group
    """
    try:
        # Store message in DB
        message = Message(**message_data.model_dump())
        db.add(message)
        db.commit()
        db.refresh(message)
        
        # Don't generate embedding for display-only messages to avoid duplicates
        # Embeddings are already created when messages are processed normally
        # (via /minimee/chat/direct or /minimee/message endpoints)
        
        # Broadcast WhatsApp message via WebSocket if source is whatsapp
        if message_data.source == "whatsapp":
            await websocket_manager.broadcast_whatsapp_message({
                "id": message.id,
                "content": message.content,
                "sender": message.sender,
                "timestamp": message.timestamp.isoformat(),
                "source": message.source,
                "conversation_id": message.conversation_id,
            })
        
        return {
            "message_id": message.id,
            "status": "displayed"
        }
    
    except Exception as e:
        db.rollback()
        log_to_db(db, "ERROR", f"Display-only message error: {str(e)}", service="minimee")
        raise HTTPException(status_code=500, detail=str(e))


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
        # Include sender in text for better RAG search (helps find conversations by person name)
        text_with_sender = f"{message.sender}: {message.content}" if message.sender else message.content
        store_embedding(db, text_with_sender, message_id=message.id, request_id=request_id, user_id=message_data.user_id)
        db.commit()  # Commit embedding before generating options
        
        # 3-7. Generate response options (sera loggé dans approval_flow.py et rag.py)
        options = await generate_response_options(db, message, request_id=request_id)
        
        # Get pending approval to send notification
        pending_approval = db.query(PendingApproval).filter(
            PendingApproval.message_id == message.id,
            PendingApproval.status == 'pending'
        ).first()
        
        # Send approval request to WhatsApp group via bridge
        if pending_approval:
            try:
                await send_approval_request_notification(db, pending_approval, request_id=request_id)
            except Exception as e:
                log_to_db(
                    db,
                    "WARNING",
                    f"Failed to send approval notification to bridge: {str(e)}",
                    service="minimee",
                    request_id=request_id,
                    metadata={"message_id": message.id, "error": str(e)}
                )
        
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
        
        # Broadcast WhatsApp message via WebSocket if source is whatsapp
        if message_data.source == "whatsapp":
            await websocket_manager.broadcast_whatsapp_message({
                "id": message.id,
                "content": message.content,
                "sender": message.sender,
                "timestamp": message.timestamp.isoformat(),
                "source": message.source,
                "conversation_id": message.conversation_id,
            })
        
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
        
        # Log approval response received (from bridge/group)
        log_action(
            db=db,
            action_type="approval_response_received",
            input_data={
                "message_id": approval_request.message_id,
                "action": approval_request.action,
                "option_index": approval_request.option_index,
                "type": approval_request.type
            },
            output_data={
                "parsed_choice": f"{approval_request.option_index}" if approval_request.option_index is not None else approval_request.action,
                "validation_status": "valid"
            },
            message_id=approval_request.message_id,
            conversation_id=message.conversation_id if message else None,
            request_id=request_id,
            user_id=message.user_id if message else None,
            source=message.source if message else None,
            status="success"
        )
        
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
        
        result = await process_approval(db, approval_request)
        
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


@router.get("/minimee/pending-approval/by-group-message-id/{group_message_id}")
async def get_pending_approval_by_group_message_id(
    group_message_id: str,
    db: Session = Depends(get_db)
):
    """
    Get pending approval by group_message_id (WhatsApp message ID in group)
    """
    try:
        from models import PendingApproval
        
        pending_approval = db.query(PendingApproval).filter(
            PendingApproval.group_message_id == group_message_id,
            PendingApproval.status == 'pending'
        ).first()
        
        if not pending_approval:
            raise HTTPException(status_code=404, detail="Pending approval not found")
        
        return {
            "message_id": pending_approval.message_id,
            "approval_id": pending_approval.id,
            "status": pending_approval.status,
            "conversation_id": pending_approval.conversation_id,  # For email drafts (thread_id)
            "source": pending_approval.source  # 'whatsapp' or 'gmail'
        }
    except HTTPException:
        raise
    except Exception as e:
        log_to_db(db, "ERROR", f"Error getting pending approval: {str(e)}", service="minimee")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/minimee/email-draft", response_model=MessageOptions)
async def propose_email_draft(
    thread_id: str,
    user_id: int = 1,  # TODO: Get from auth
    db: Session = Depends(get_db)
):
    """
    Generate and propose email draft options for a Gmail thread
    Stores proposals for approval and sends via WhatsApp group
    """
    from datetime import datetime, timedelta
    from models import GmailThread, Message
    from services.email_draft import generate_email_drafts_sync
    # log_to_db is already imported at the top of the file
    from services.action_logger import generate_request_id
    
    request_id = generate_request_id()
    
    try:
        # Get thread information
        thread = db.query(GmailThread).filter(
            GmailThread.thread_id == thread_id,
            GmailThread.user_id == user_id
        ).first()
        
        if not thread:
            raise ValueError(f"Thread {thread_id} not found")
        
        # Get the last message in thread for context
        last_message = db.query(Message).filter(
            Message.conversation_id == thread_id,
            Message.source == "gmail"
        ).order_by(Message.timestamp.desc()).first()
        
        if not last_message:
            raise ValueError(f"No messages found in thread {thread_id}")
        
        # Generate draft options
        drafts = generate_email_drafts_sync(db, thread_id, user_id, num_options=3)
        
        # Get recipient (sender of last message, since we're replying)
        sender_email = last_message.sender
        
        # Prepare context summary (get from last message or RAG)
        context_summary = last_message.content[:500] if last_message.content else None
        
        # Calculate expiration
        expires_at = datetime.utcnow() + timedelta(minutes=settings.approval_expiration_minutes)
        
        # Create PendingApproval for email draft
        # Use message_id=NULL since email drafts are for threads, not specific messages
        pending_approval = PendingApproval(
            message_id=None,  # NULL for email drafts (thread-based)
            conversation_id=thread_id,
            sender=sender_email,
            source='gmail',
            recipient_jid=None,
            recipient_email=sender_email,
            option_a=drafts[0] if len(drafts) > 0 else "",
            option_b=drafts[1] if len(drafts) > 1 else "",
            option_c=drafts[2] if len(drafts) > 2 else "",
            context_summary=context_summary,
            original_content_preview=last_message.content[:300] if last_message.content else "",
            email_subject=thread.subject,
            user_id=user_id,
            status='pending',
            expires_at=expires_at
        )
        db.add(pending_approval)
        db.commit()
        db.refresh(pending_approval)
        
        # Send approval request to WhatsApp group via bridge
        try:
            await send_approval_request_notification(db, pending_approval, request_id=request_id)
        except Exception as e:
            log_to_db(
                db,
                "WARNING",
                f"Failed to send email draft approval notification to bridge: {str(e)}",
                service="minimee",
                request_id=request_id,
                metadata={"thread_id": thread_id, "error": str(e)}
            )
        
        # Create MessageOptions for response
        message_options = MessageOptions(
            options=drafts,
            message_id=0,  # Placeholder for email drafts
            conversation_id=thread_id
        )
        
        # Also store in old format for backward compatibility
        store_email_draft_proposals(thread_id, message_options)
        
        log_to_db(
            db,
            "INFO",
            f"Proposed {len(drafts)} email draft options for thread {thread_id}",
            service="minimee",
            request_id=request_id,
            metadata={
                "thread_id": thread_id,
                "approval_id": pending_approval.id,
                "subject": thread.subject
            }
        )
        
        return message_options
    
    except ValueError as e:
        log_to_db(db, "ERROR", f"Email draft error: {str(e)}", service="minimee", request_id=request_id)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log_to_db(db, "ERROR", f"Email draft error: {str(e)}", service="minimee", request_id=request_id)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/minimee/send-reminders")
async def send_reminders(
    db: Session = Depends(get_db)
):
    """
    Send reminders for pending approvals that are older than reminder threshold
    Can be called periodically or manually
    """
    try:
        results = await send_pending_approval_reminders(db)
        
        log_to_db(
            db,
            "INFO",
            f"Reminder check completed: {results['reminders_sent']} reminders sent, {results['checked']} checked",
            service="minimee",
            metadata=results
        )
        
        return results
    except Exception as e:
        log_to_db(db, "ERROR", f"Error sending reminders: {str(e)}", service="minimee")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/minimee/chat/stream")
async def chat_stream(
    chat_request: ChatMessageRequest,
    db: Session = Depends(get_db)
):
    """
    Chat endpoint with streaming response
    Uses RAG for context and streams LLM response token by token
    """
    request_id = generate_request_id()
    conversation_id = chat_request.conversation_id or f"dashboard-user-{chat_request.user_id}"
    
    async def event_generator():
        try:
            # 1. Store user message in DB
            user_message = Message(
                content=chat_request.content,
                sender="User",
                timestamp=datetime.utcnow(),
                source="dashboard",
                conversation_id=conversation_id,
                user_id=chat_request.user_id
            )
            db.add(user_message)
            db.commit()
            db.refresh(user_message)
            
            # 2. Generate embedding for user message
            # Include sender in text for better RAG search
            text_with_sender = f"{user_message.sender}: {user_message.content}" if user_message.sender else user_message.content
            store_embedding(db, text_with_sender, message_id=user_message.id, request_id=request_id, user_id=chat_request.user_id)
            db.commit()
            
            # 3. Retrieve context using RAG
            context, rag_details = retrieve_context(
                db,
                chat_request.content,
                chat_request.user_id,
                request_id=request_id,
                return_details=True
            )
            
            # 4. Select appropriate agent
            agent = select_agent_for_context(db, chat_request.content, chat_request.user_id)
            
            # 5. Build prompt
            if agent:
                system_prompt = f"You are {agent.name}, {agent.role}. {agent.prompt}"
                if agent.style:
                    system_prompt += f"\nCommunication style: {agent.style}"
            else:
                system_prompt = "You are Minimee, a personal AI assistant."
            
            full_prompt = build_prompt_with_context(chat_request.content, context, user_style=None)
            full_prompt = f"{system_prompt}\n\n{full_prompt}"
            
            # 6. Get LLM provider info from DB settings
            from services.llm_router import get_llm_provider_from_db
            llm_provider, llm_model_from_db = get_llm_provider_from_db(db)
            llm_model = llm_model_from_db
            if not llm_model:
                if llm_provider == "ollama":
                    llm_model = settings.ollama_model or "llama3.2:1b"
                elif llm_provider == "vllm":
                    llm_model = "vLLM (RunPod)"
                elif llm_provider == "openai":
                    llm_model = "gpt-4o"
            
            # 6. Stream LLM response
            full_response = ""
            async for token_data in generate_llm_response_stream(
                full_prompt,
                temperature=0.7,
                max_tokens=512,
                db=db,
                request_id=request_id,
                message_id=user_message.id,
                user_id=chat_request.user_id
            ):
                if "error" in token_data:
                    yield f"data: {json.dumps({'type': 'error', 'message': token_data['error']})}\n\n"
                    return
                
                if not token_data.get("done", False):
                    token = token_data.get("token", "")
                    full_response += token
                    yield f"data: {json.dumps({'type': 'token', 'token': token})}\n\n"
                else:
                    # Response complete
                    final_response = token_data.get("response", full_response)
                    actions = token_data.get("actions", [])
                    
                    # 7. Store Minimee response in DB
                    minimee_message = Message(
                        content=final_response,
                        sender="Minimee",
                        timestamp=datetime.utcnow(),
                        source="minimee",
                        conversation_id=conversation_id,
                        user_id=chat_request.user_id
                    )
                    db.add(minimee_message)
                    db.commit()
                    db.refresh(minimee_message)
                    
                    # 8. Generate embedding for Minimee response
                    store_embedding(db, minimee_message.content, message_id=minimee_message.id, request_id=request_id, user_id=chat_request.user_id)
                    db.commit()
                    
                    # 9. Send final event with debug info
                    yield f"data: {json.dumps({'type': 'done', 'response': final_response, 'actions': actions, 'message_id': minimee_message.id, 'debug': {'llm_provider': llm_provider, 'llm_model': llm_model, 'rag_context': context, 'rag_details': rag_details}})}\n\n"
                    break
                    
        except Exception as e:
            log_to_db(db, "ERROR", f"Chat stream error: {str(e)}", service="minimee", request_id=request_id)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/minimee/chat/direct")
async def chat_direct(
    chat_request: ChatMessageRequest,
    db: Session = Depends(get_db)
):
    """
    Direct chat endpoint for WhatsApp messages from Minimee TEAM group
    Returns a direct response without generating approval options
    Similar to /minimee/chat/stream but synchronous and non-streaming
    """
    request_id = generate_request_id()
    conversation_id = chat_request.conversation_id or f"minimee-team-{chat_request.user_id}"
    
    try:
        # 1. Store user message in DB
        message_timestamp = datetime.fromisoformat(chat_request.timestamp.replace('Z', '+00:00')) if chat_request.timestamp else datetime.utcnow()
        user_message = Message(
            content=chat_request.content,
            sender=chat_request.sender or "User",
            timestamp=message_timestamp,
            source=chat_request.source or "whatsapp",
            conversation_id=conversation_id,
            user_id=chat_request.user_id
        )
        db.add(user_message)
        db.commit()
        db.refresh(user_message)
        
        # 2. Generate embedding for user message
        store_embedding(db, user_message.content, message_id=user_message.id, request_id=request_id, user_id=chat_request.user_id)
        db.commit()
        
        # 3. Retrieve context using RAG
        context, rag_details = retrieve_context(
            db,
            chat_request.content,
            chat_request.user_id,
            request_id=request_id,
            return_details=True
        )
        
        # 4. Select appropriate agent
        agent = select_agent_for_context(db, chat_request.content, chat_request.user_id)
        
        # 5. Build prompt
        if agent:
            system_prompt = f"You are {agent.name}, {agent.role}. {agent.prompt}"
            if agent.style:
                system_prompt += f"\nCommunication style: {agent.style}"
        else:
            system_prompt = "You are Minimee, a personal AI assistant."
        
        full_prompt = build_prompt_with_context(chat_request.content, context, user_style=None)
        full_prompt = f"{system_prompt}\n\n{full_prompt}"
        
        # 6. Generate LLM response (non-streaming, synchronous)
        response = await generate_llm_response(
            full_prompt,
            temperature=0.7,
            max_tokens=512,
            db=db,
            request_id=request_id,
            message_id=user_message.id,
            user_id=chat_request.user_id
        )
        
        # 7. Store Minimee response in DB
        minimee_message = Message(
            content=response,
            sender="Minimee",
            timestamp=datetime.utcnow(),
            source="minimee",
            conversation_id=conversation_id,
            user_id=chat_request.user_id
        )
        db.add(minimee_message)
        db.commit()
        db.refresh(minimee_message)
        
        # 8. Generate embedding for Minimee response
        store_embedding(db, minimee_message.content, message_id=minimee_message.id, request_id=request_id, user_id=chat_request.user_id)
        db.commit()
        
        # 9. Broadcast to WebSocket if source is whatsapp
        if chat_request.source == "whatsapp":
            await websocket_manager.broadcast_whatsapp_message({
                "id": user_message.id,
                "content": user_message.content,
                "sender": user_message.sender,
                "timestamp": user_message.timestamp.isoformat(),
                "source": user_message.source,
                "conversation_id": user_message.conversation_id,
            })
            
            # Also broadcast Minimee's response (keep source as "whatsapp" to show badge)
            await websocket_manager.broadcast_whatsapp_message({
                "id": minimee_message.id,
                "content": minimee_message.content,
                "sender": "Minimee",
                "timestamp": minimee_message.timestamp.isoformat(),
                "source": "whatsapp",  # Keep as whatsapp to show badge in dashboard
                "conversation_id": minimee_message.conversation_id,
            })
        
        return {
            "response": response,
            "message_id": minimee_message.id,
            "conversation_id": conversation_id
        }
        
    except Exception as e:
        log_to_db(db, "ERROR", f"Direct chat error: {str(e)}", service="minimee", request_id=request_id)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/minimee/conversations/{conversation_id}/messages", response_model=list[ChatMessageResponse])
async def get_conversation_messages(
    conversation_id: str,
    user_id: int = Query(1, description="User ID"),  # TODO: Get from auth
    db: Session = Depends(get_db)
):
    """
    Get conversation history
    Returns all messages for a given conversation_id
    """
    try:
        messages = db.query(Message).filter(
            Message.conversation_id == conversation_id,
            Message.user_id == user_id
        ).order_by(Message.timestamp.asc()).all()
        
        return [
            ChatMessageResponse(
                id=msg.id,
                content=msg.content,
                sender=msg.sender,
                timestamp=msg.timestamp,
                source=msg.source,
                conversation_id=msg.conversation_id
            )
            for msg in messages
        ]
    except Exception as e:
        log_to_db(db, "ERROR", f"Error fetching conversation messages: {str(e)}", service="minimee")
        raise HTTPException(status_code=500, detail=str(e))


@router.websocket("/minimee/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time WhatsApp message updates
    Clients connect to receive WhatsApp messages as they arrive
    """
    await websocket_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive and wait for client messages if needed
            data = await websocket.receive_text()
            # Client can send ping/pong for keepalive
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        websocket_manager.disconnect(websocket)
    except Exception as e:
        # Log error (without DB since we might not have a session)
        print(f"WebSocket error: {str(e)}")
        websocket_manager.disconnect(websocket)

