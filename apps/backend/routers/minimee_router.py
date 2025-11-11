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
# Archived: from services.rag_llamaindex import retrieve_context, build_prompt_with_context
# Now using LangChain-based RAG in services/minimee_agent/
from services.agent_manager import select_agent_for_context, get_agent_by_whatsapp_name, get_minimee_leader
from services.minimee_agent.agent_factory import get_or_create_agent, get_minimee_leader_agent, get_agent_by_whatsapp_name as get_agent_by_whatsapp_name_factory
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
    
    # Log the incoming POST request with full details
    from services.logs_service import log_to_db
    log_to_db(
        db,
        "INFO",
        f"POST /minimee/message - Received message",
        service="api",
        request_id=request_id,
        metadata={
            "content": message_data.content,
            "sender": message_data.sender,
            "source": message_data.source,
            "conversation_id": message_data.conversation_id,
            "user_id": message_data.user_id,
            "timestamp": message_data.timestamp,
        }
    )
    
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
        store_embedding(db, text_with_sender, message_id=message.id, request_id=request_id, user_id=message_data.user_id, message=message)
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
        
        # Ensure options are available before logging
        options_list = options.options if hasattr(options, 'options') else []
        log_to_db(
            db, 
            "INFO", 
            f"Processed message {message.id}, generated {len(options_list)} options", 
            service="minimee",
            request_id=request_id,
            metadata={
                "message_id": message.id,
                "message_content": message.content,
                "sender": message.sender,
                "source": message.source,
                "conversation_id": message.conversation_id,
                "options_count": len(options_list),
                "options": options_list,  # Les options complètes
                "option_1": options_list[0] if len(options_list) > 0 else None,
                "option_2": options_list[1] if len(options_list) > 1 else None,
                "option_3": options_list[2] if len(options_list) > 2 else None,
            }
        )
        
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
    Now uses LangChain MinimeeAgent with intelligent RAG and streaming
    """
    request_id = generate_request_id()
    conversation_id = chat_request.conversation_id or f"dashboard-minimee-{chat_request.user_id}"
    
    log_to_db(db, "INFO", 
        f"Chat stream request received: user_id={chat_request.user_id}, conversation_id={conversation_id}, "
        f"agent_name={chat_request.agent_name}, content_preview={chat_request.content[:100]}",
        service="minimee_router",
        request_id=request_id,
        user_id=chat_request.user_id,
        metadata={"agent_name": chat_request.agent_name, "source": chat_request.source}
    )
    
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
            
            log_to_db(db, "INFO", 
                f"User message stored: message_id={user_message.id}, content_length={len(chat_request.content)}",
                service="minimee_router",
                request_id=request_id,
                user_id=chat_request.user_id,
                metadata={"message_id": user_message.id}
            )
            
            # 2. Generate embedding for user message
            text_with_sender = f"{user_message.sender}: {user_message.content}" if user_message.sender else user_message.content
            store_embedding(db, text_with_sender, message_id=user_message.id, request_id=request_id, user_id=chat_request.user_id, message=user_message)
            db.commit()
            
            log_to_db(db, "INFO", 
                f"Embedding generated for user message: message_id={user_message.id}",
                service="minimee_router",
                request_id=request_id,
                user_id=chat_request.user_id
            )
            
            # 3. Route to appropriate agent based on agent_name or use leader
            minimee_agent = None
            agent_model = None
            
            if chat_request.agent_name:
                log_to_db(db, "INFO", 
                    f"Routing to agent by name: {chat_request.agent_name}",
                    service="minimee_router",
                    request_id=request_id,
                    user_id=chat_request.user_id
                )
                agent_model = get_agent_by_whatsapp_name(db, chat_request.agent_name, chat_request.user_id)
                if agent_model:
                    minimee_agent = get_agent_by_whatsapp_name_factory(
                        whatsapp_name=chat_request.agent_name,
                        user_id=chat_request.user_id,
                        db=db,
                        conversation_id=conversation_id
                    )
                    log_to_db(db, "INFO", 
                        f"Agent found by WhatsApp name: agent_id={agent_model.id}, name={agent_model.name}",
                        service="minimee_router",
                        request_id=request_id,
                        user_id=chat_request.user_id,
                        metadata={"agent_id": agent_model.id, "agent_name": agent_model.name}
                    )
                else:
                    log_to_db(db, "WARNING", 
                        f"Agent not found by WhatsApp name: {chat_request.agent_name}, falling back to leader",
                        service="minimee_router",
                        request_id=request_id,
                        user_id=chat_request.user_id
                    )
            
            if not minimee_agent:
                log_to_db(db, "INFO", 
                    "Using Minimee leader agent",
                    service="minimee_router",
                    request_id=request_id,
                    user_id=chat_request.user_id
                )
                minimee_agent = get_minimee_leader_agent(
                    user_id=chat_request.user_id,
                    db=db,
                    conversation_id=conversation_id
                )
                if minimee_agent:
                    agent_model = minimee_agent.agent
                    log_to_db(db, "INFO", 
                        f"Leader agent loaded: agent_id={agent_model.id}, name={agent_model.name}",
                        service="minimee_router",
                        request_id=request_id,
                        user_id=chat_request.user_id,
                        metadata={"agent_id": agent_model.id, "agent_name": agent_model.name}
                    )
                else:
                    log_to_db(db, "ERROR", 
                        "No leader agent found and no agent specified. Cannot process request.",
                        service="minimee_router",
                        request_id=request_id,
                        user_id=chat_request.user_id
                    )
                    yield f"data: {json.dumps({'type': 'error', 'message': 'No agent available. Please set a Minimee leader agent.'})}\n\n"
                    return
            
            # 4. Stream agent response
            log_to_db(db, "INFO", 
                f"Invoking agent (streaming): agent_id={agent_model.id}, conversation_id={conversation_id}",
                service="minimee_router",
                request_id=request_id,
                user_id=chat_request.user_id,
                metadata={"agent_id": agent_model.id, "conversation_id": conversation_id}
            )
            
            full_response = ""
            async for token_data in minimee_agent.invoke_stream(
                user_message=chat_request.content,
                conversation_id=conversation_id
            ):
                if "error" in token_data:
                    log_to_db(db, "ERROR", 
                        f"Agent stream error: {token_data.get('error')}",
                        service="minimee_router",
                        request_id=request_id,
                        user_id=chat_request.user_id
                    )
                    yield f"data: {json.dumps({'type': 'error', 'message': token_data.get('error')})}\n\n"
                    return
                
                if not token_data.get("done", False):
                    token = token_data.get("token", "")
                    if token:
                        full_response += token
                        yield f"data: {json.dumps({'type': 'token', 'token': token})}\n\n"
                else:
                    # Response complete
                    final_response = token_data.get("response", full_response)
                    requires_approval = token_data.get("requires_approval", False)
                    
                    log_to_db(db, "INFO", 
                        f"Agent stream complete: response_length={len(final_response)}, requires_approval={requires_approval}",
                        service="minimee_router",
                        request_id=request_id,
                        user_id=chat_request.user_id,
                        metadata={
                            "agent_id": agent_model.id,
                            "requires_approval": requires_approval,
                            "response_preview": final_response[:100]
                        }
                    )
                    
                    # 5. Store Minimee response in DB
                    minimee_message = Message(
                        content=final_response,
                        sender=agent_model.name if agent_model else "Minimee",
                        timestamp=datetime.utcnow(),
                        source="minimee",
                        conversation_id=conversation_id,
                        user_id=chat_request.user_id
                    )
                    db.add(minimee_message)
                    db.commit()
                    db.refresh(minimee_message)
                    
                    log_to_db(db, "INFO", 
                        f"Minimee response stored: message_id={minimee_message.id}",
                        service="minimee_router",
                        request_id=request_id,
                        user_id=chat_request.user_id,
                        metadata={"message_id": minimee_message.id}
                    )
                    
                    # 6. Generate embedding for Minimee response
                    text_with_sender = f"{minimee_message.sender}: {minimee_message.content}" if minimee_message.sender else minimee_message.content
                    store_embedding(db, text_with_sender, message_id=minimee_message.id, request_id=request_id, user_id=chat_request.user_id, message=minimee_message)
                    db.commit()
                    
                    log_to_db(db, "INFO", 
                        f"Embedding generated for Minimee response: message_id={minimee_message.id}",
                        service="minimee_router",
                        request_id=request_id,
                        user_id=chat_request.user_id
                    )
                    
                    # 7. Send final event
                    final_data = {
                        'type': 'done', 
                        'response': final_response, 
                        'message_id': minimee_message.id,
                        'requires_approval': requires_approval,
                        'agent_name': agent_model.name if agent_model else 'Minimee'
                    }
                    yield f"data: {json.dumps(final_data)}\n\n"
                    
                    break
                    
        except Exception as e:
            log_to_db(db, "ERROR", 
                f"Chat stream error: {str(e)}, traceback={repr(e)}",
                service="minimee_router",
                request_id=request_id,
                user_id=chat_request.user_id,
                metadata={"error_type": type(e).__name__, "error_message": str(e)}
            )
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
    Now uses LangChain MinimeeAgent with intelligent RAG and approval decisions
    Returns a direct response or requires approval based on agent rules
    """
    request_id = generate_request_id()
    conversation_id = chat_request.conversation_id or f"minimee-team-{chat_request.user_id}"
    
    log_to_db(db, "INFO", 
        f"Chat direct request received: user_id={chat_request.user_id}, conversation_id={conversation_id}, "
        f"agent_name={chat_request.agent_name}, content_preview={chat_request.content[:100]}",
        service="minimee_router",
        request_id=request_id,
        user_id=chat_request.user_id,
        metadata={"agent_name": chat_request.agent_name, "source": chat_request.source}
    )
    
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
        
        log_to_db(db, "INFO", 
            f"User message stored: message_id={user_message.id}, content_length={len(chat_request.content)}",
            service="minimee_router",
            request_id=request_id,
            user_id=chat_request.user_id,
            metadata={"message_id": user_message.id}
        )
        
        # 2. Generate embedding for user message
        text_with_sender = f"{user_message.sender}: {user_message.content}" if user_message.sender else user_message.content
        store_embedding(db, text_with_sender, message_id=user_message.id, request_id=request_id, user_id=chat_request.user_id, message=user_message)
        db.commit()
        
        log_to_db(db, "INFO", 
            f"Embedding generated for user message: message_id={user_message.id}",
            service="minimee_router",
            request_id=request_id,
            user_id=chat_request.user_id
        )
        
        # 3. Route to appropriate agent based on agent_name or use leader
        minimee_agent = None
        agent_model = None
        
        if chat_request.agent_name:
            # Route to specific agent by WhatsApp name
            log_to_db(db, "INFO", 
                f"Routing to agent by name: {chat_request.agent_name}",
                service="minimee_router",
                request_id=request_id,
                user_id=chat_request.user_id
            )
            agent_model = get_agent_by_whatsapp_name(db, chat_request.agent_name, chat_request.user_id)
            if agent_model:
                minimee_agent = get_agent_by_whatsapp_name_factory(
                    whatsapp_name=chat_request.agent_name,
                    user_id=chat_request.user_id,
                    db=db,
                    conversation_id=conversation_id
                )
                log_to_db(db, "INFO", 
                    f"Agent found by WhatsApp name: agent_id={agent_model.id}, name={agent_model.name}",
                    service="minimee_router",
                    request_id=request_id,
                    user_id=chat_request.user_id,
                    metadata={"agent_id": agent_model.id, "agent_name": agent_model.name}
                )
            else:
                log_to_db(db, "WARNING", 
                    f"Agent not found by WhatsApp name: {chat_request.agent_name}, falling back to leader",
                    service="minimee_router",
                    request_id=request_id,
                    user_id=chat_request.user_id
                )
        
        if not minimee_agent:
            # Use leader agent
            log_to_db(db, "INFO", 
                "Using Minimee leader agent",
                service="minimee_router",
                request_id=request_id,
                user_id=chat_request.user_id
            )
            minimee_agent = get_minimee_leader_agent(
                user_id=chat_request.user_id,
                db=db,
                conversation_id=conversation_id
            )
            if minimee_agent:
                # Use stored attributes instead of agent model to avoid detached instance errors
                agent_id = minimee_agent.agent_id
                agent_name = minimee_agent.agent_name
                log_to_db(db, "INFO", 
                    f"Leader agent loaded: agent_id={agent_id}, name={agent_name}",
                    service="minimee_router",
                    request_id=request_id,
                    user_id=chat_request.user_id,
                    metadata={"agent_id": agent_id, "agent_name": agent_name}
                )
                # Create a simple object for compatibility
                from types import SimpleNamespace
                agent_model = SimpleNamespace(id=agent_id, name=agent_name)
            else:
                log_to_db(db, "ERROR", 
                    "No leader agent found and no agent specified. Cannot process request.",
                    service="minimee_router",
                    request_id=request_id,
                    user_id=chat_request.user_id
                )
                raise HTTPException(status_code=404, detail="No agent available. Please set a Minimee leader agent.")
        
        # 4. Invoke agent with user message
        log_to_db(db, "INFO", 
            f"Invoking agent: agent_id={agent_model.id}, conversation_id={conversation_id}",
            service="minimee_router",
            request_id=request_id,
            user_id=chat_request.user_id,
            metadata={"agent_id": agent_model.id, "conversation_id": conversation_id}
        )
        
        agent_result = await minimee_agent.invoke(
            user_message=chat_request.content,
            conversation_id=conversation_id
        )
        
        response_text = agent_result.get("response", "")
        requires_approval = agent_result.get("requires_approval", False)
        options = agent_result.get("options", None)
        
        log_to_db(db, "INFO", 
            f"Agent response generated: response_length={len(response_text)}, requires_approval={requires_approval}, "
            f"options_count={len(options) if options else 0}",
            service="minimee_router",
            request_id=request_id,
            user_id=chat_request.user_id,
            metadata={
                "agent_id": agent_model.id,
                "requires_approval": requires_approval,
                "response_preview": response_text[:100]
            }
        )
        
        # 5. Store Minimee response in DB
        minimee_message = Message(
            content=response_text,
            sender=agent_model.name if agent_model else "Minimee",
            timestamp=datetime.utcnow(),
            source="minimee",
            conversation_id=conversation_id,
            user_id=chat_request.user_id
        )
        db.add(minimee_message)
        db.commit()
        db.refresh(minimee_message)
        
        log_to_db(db, "INFO", 
            f"Minimee response stored: message_id={minimee_message.id}",
            service="minimee_router",
            request_id=request_id,
            user_id=chat_request.user_id,
            metadata={"message_id": minimee_message.id}
        )
        
        # 6. Generate embedding for Minimee response
        text_with_sender = f"{minimee_message.sender}: {minimee_message.content}" if minimee_message.sender else minimee_message.content
        store_embedding(db, text_with_sender, message_id=minimee_message.id, request_id=request_id, user_id=chat_request.user_id, message=minimee_message)
        db.commit()
        
        log_to_db(db, "INFO", 
            f"Embedding generated for Minimee response: message_id={minimee_message.id}",
            service="minimee_router",
            request_id=request_id,
            user_id=chat_request.user_id
        )
        
        # 7. Broadcast to WebSocket if source is whatsapp
        if chat_request.source == "whatsapp":
            await websocket_manager.broadcast_whatsapp_message({
                "id": user_message.id,
                "content": user_message.content,
                "sender": user_message.sender,
                "timestamp": user_message.timestamp.isoformat(),
                "source": user_message.source,
                "conversation_id": user_message.conversation_id,
            })
            
            await websocket_manager.broadcast_whatsapp_message({
                "id": minimee_message.id,
                "content": minimee_message.content,
                "sender": agent_model.name if agent_model else "Minimee",
                "timestamp": minimee_message.timestamp.isoformat(),
                "source": "minimee",
                "conversation_id": minimee_message.conversation_id,
            })
            
            log_to_db(db, "INFO", 
                f"Messages broadcasted via WebSocket: user_message_id={user_message.id}, minimee_message_id={minimee_message.id}",
                service="minimee_router",
                request_id=request_id,
                user_id=chat_request.user_id
            )
        
        # 8. Return response with approval info
        result = {
            "response": response_text,
            "message_id": minimee_message.id,
            "conversation_id": conversation_id,
            "requires_approval": requires_approval
        }
        
        if requires_approval and options:
            result["options"] = options
            log_to_db(db, "INFO", 
                f"Response requires approval: {len(options)} options provided",
                service="minimee_router",
                request_id=request_id,
                user_id=chat_request.user_id
            )
        else:
            log_to_db(db, "INFO", 
                "Response auto-approved, no approval required",
                service="minimee_router",
                request_id=request_id,
                user_id=chat_request.user_id
            )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        log_to_db(db, "ERROR", 
            f"Direct chat error: {str(e)}, traceback={repr(e)}",
            service="minimee_router",
            request_id=request_id,
            user_id=chat_request.user_id,
            metadata={"error_type": type(e).__name__, "error_message": str(e)}
        )
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


@router.delete("/minimee/conversations/{conversation_id}/messages")
async def delete_conversation_messages(
    conversation_id: str,
    user_id: int = Query(1, description="User ID"),  # TODO: Get from auth
    db: Session = Depends(get_db)
):
    """
    Delete all messages from a conversation
    Also deletes associated embeddings and action_logs
    Returns count of deleted messages
    """
    from models import Embedding, ActionLog
    
    try:
        # Get message IDs before deletion
        messages = db.query(Message).filter(
            Message.conversation_id == conversation_id,
            Message.user_id == user_id
        ).all()
        
        message_ids = [msg.id for msg in messages]
        message_count = len(message_ids)
        
        if message_count == 0:
            return {
                "deleted": 0,
                "message": "No messages found for this conversation"
            }
        
        # Delete in correct order to avoid foreign key violations:
        # 1. ActionLogs (reference messages)
        action_logs_count = 0
        if message_ids:
            action_logs_count = db.query(ActionLog).filter(ActionLog.message_id.in_(message_ids)).delete(synchronize_session=False)
        
        # 2. Embeddings (reference messages)
        embeddings_count = 0
        if message_ids:
            embeddings_count = db.query(Embedding).filter(Embedding.message_id.in_(message_ids)).delete(synchronize_session=False)
        
        # 3. Messages (last, after all dependencies are removed)
        deleted_count = db.query(Message).filter(
            Message.conversation_id == conversation_id,
            Message.user_id == user_id
        ).delete(synchronize_session=False)
        
        db.commit()
        
        log_to_db(
            db,
            "INFO",
            f"Deleted {deleted_count} messages from conversation {conversation_id}",
            service="minimee",
            metadata={
                "conversation_id": conversation_id,
                "user_id": user_id,
                "deleted_count": deleted_count,
                "action_logs_count": action_logs_count,
                "embeddings_count": embeddings_count
            }
        )
        
        return {
            "deleted": deleted_count,
            "message": f"Successfully deleted {deleted_count} message(s), {embeddings_count} embedding(s), and {action_logs_count} action log(s)"
        }
    
    except Exception as e:
        db.rollback()
        log_to_db(db, "ERROR", f"Error deleting conversation messages: {str(e)}", service="minimee")
        raise HTTPException(status_code=500, detail=f"Error deleting conversation messages: {str(e)}")


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

