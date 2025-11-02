"""
Approval flow service for message validation
Supports both WhatsApp messages and email drafts
"""
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from services.llm_router import generate_multiple_options
from services.rag import retrieve_context, build_prompt_with_context
from services.agent_manager import select_agent_for_context
from services.action_logger import log_action_context, log_action
from services.logs_service import log_to_db
from services.bridge_client import send_approval_request_to_bridge, send_message_via_bridge
from models import Message, PendingApproval
from schemas import MessageOptions, ApprovalRequest
from config import settings


# In-memory storage for email drafts (keep for backward compatibility during transition)
_pending_email_drafts: Dict[str, MessageOptions] = {}  # key: thread_id


async def generate_response_options(
    db: Session,
    message: Message,
    num_options: int = 3,
    request_id: Optional[str] = None
) -> MessageOptions:
    """
    Generate multiple response options for user approval
    """
    # Retrieve context using RAG (sera loggé dans rag.py)
    try:
        context = retrieve_context(db, message.content, message.user_id, request_id=request_id)
    except Exception as e:
        from services.logs_service import log_to_db
        log_to_db(db, "WARNING", f"RAG context error: {str(e)}, using empty context", service="approval_flow")
        context = ""
    
    # Select appropriate agent
    agent = select_agent_for_context(db, message.content, message.user_id)
    
    # Build prompt with logging
    with log_action_context(
        db=db,
        action_type="prompt_building",
        model=None,
        input_data={
            "message_content": message.content[:500],
            "agent_id": agent.id if agent else None,
            "agent_name": agent.name if agent else None,
            "has_context": bool(context)
        },
        message_id=message.id,
        conversation_id=message.conversation_id,
        request_id=request_id,
        user_id=message.user_id,
        source=message.source,
        metadata={"num_options": num_options}
    ) as log:
        # Build prompt
        if agent:
            system_prompt = f"You are {agent.name}, {agent.role}. {agent.prompt}"
            if agent.style:
                system_prompt += f"\nCommunication style: {agent.style}"
        else:
            system_prompt = "You are Minimee, a personal AI assistant."
        
    # Build prompt optimized for speed (short responses for WhatsApp)
    if context:
        full_prompt = f"{system_prompt}\n\nContext: {context}\n\nUser: {message.content}\n\nShort reply (30 words max):"
    else:
        full_prompt = f"{system_prompt}\n\nUser: {message.content}\n\nShort reply (30 words max):"
        
        log.set_output({
            "system_prompt": system_prompt[:500],
            "full_prompt_length": len(full_prompt),
            "context_length": len(context) if context else 0
        })
    
    # Generate multiple options (sera loggé dans llm_router.py)
    options = await generate_multiple_options(full_prompt, num_options, db, request_id=request_id, message_id=message.id, user_id=message.user_id)
    
    # Log response options generated
    log_action(
        db=db,
        action_type="response_options",
        input_data={
            "message_id": message.id,
            "num_options_requested": num_options
        },
        output_data={
            "options_count": len(options),
            "options_preview": [opt[:100] for opt in options[:3]]  # Preview des 3 premiers
        },
        message_id=message.id,
        conversation_id=message.conversation_id,
        request_id=request_id,
        user_id=message.user_id,
        source=message.source,
        status="success"
    )
    
    message_options = MessageOptions(
        options=options,
        message_id=message.id,
        conversation_id=message.conversation_id
    )
    
    # Store in database instead of in-memory
    # Get recipient info
    recipient_jid = None
    recipient_email = None
    if message.source == 'whatsapp':
        # For WhatsApp, recipient is in conversation_id (phone number)
        recipient_jid = f"{message.conversation_id}@s.whatsapp.net" if message.conversation_id and '@' not in message.conversation_id else message.conversation_id
    elif message.source == 'gmail':
        # For Gmail, recipient is the sender (we reply to them)
        recipient_email = message.sender
    
    # Prepare context summary (truncate if too long)
    context_summary = context[:500] if context else None
    original_preview = message.content[:300]
    
    # Calculate expiration (default 60 minutes from now)
    expires_at = datetime.utcnow() + timedelta(minutes=settings.approval_expiration_minutes)
    
    # Check if approval already exists for this message
    existing = db.query(PendingApproval).filter(
        PendingApproval.message_id == message.id,
        PendingApproval.status == 'pending'
    ).first()
    
    if existing:
        # Update existing approval
        existing.option_a = options[0] if len(options) > 0 else ""
        existing.option_b = options[1] if len(options) > 1 else ""
        existing.option_c = options[2] if len(options) > 2 else ""
        existing.context_summary = context_summary
        existing.original_content_preview = original_preview
        existing.expires_at = expires_at
        pending_approval = existing
    else:
        # Create new approval
        pending_approval = PendingApproval(
            message_id=message.id,
            conversation_id=message.conversation_id,
            sender=message.sender,
            source=message.source,
            recipient_jid=recipient_jid,
            recipient_email=recipient_email,
            option_a=options[0] if len(options) > 0 else "",
            option_b=options[1] if len(options) > 1 else "",
            option_c=options[2] if len(options) > 2 else "",
            context_summary=context_summary,
            original_content_preview=original_preview,
            user_id=message.user_id,
            status='pending',
            expires_at=expires_at
        )
        db.add(pending_approval)
    
    db.commit()
    db.refresh(pending_approval)
    
    return message_options


async def send_approval_request_notification(
    db: Session,
    pending_approval: PendingApproval,
    request_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Send approval request notification to WhatsApp group via bridge
    """
    try:
        # Format message for WhatsApp group
        source_emoji = "📱" if pending_approval.source == 'whatsapp' else "📧"
        source_label = "WhatsApp" if pending_approval.source == 'whatsapp' else "Gmail"
        
        message_text = f"""[🤖 Minimee] Nouveau message

{source_emoji} De: {pending_approval.sender} ({source_label})"""
        
        if pending_approval.email_subject:
            message_text += f"\n   Sujet: {pending_approval.email_subject}"
        
        if pending_approval.context_summary:
            message_text += f"\n\n📝 Contexte:\n{pending_approval.context_summary}"
        
        message_text += f"\n\n💬 Message reçu:\n{pending_approval.original_content_preview}"
        
        message_text += f"""

🎯 Options de réponse:
A) {pending_approval.option_a}
B) {pending_approval.option_b}
C) {pending_approval.option_c}
No) Ne pas répondre

Répondez: A, B, C ou No"""
        
        # Prepare approval data
        approval_data = {
            "message_id": pending_approval.message_id,
            "approval_id": pending_approval.id,
            "message_text": message_text,
            "options": {
                "A": pending_approval.option_a,
                "B": pending_approval.option_b,
                "C": pending_approval.option_c
            },
            "sender": pending_approval.sender,
            "source": pending_approval.source,
            "context_summary": pending_approval.context_summary,
            "original_content": pending_approval.original_content_preview
        }
        
        if pending_approval.email_subject:
            approval_data["email_subject"] = pending_approval.email_subject
        
        # Log action before sending
        start_time = datetime.utcnow()
        
        # Send to bridge
        bridge_response = await send_approval_request_to_bridge(approval_data, db)
        
        duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        # Update pending_approval with group_message_id
        pending_approval.group_message_id = bridge_response.get('group_message_id')
        db.commit()
        
        # Log action
        log_action(
            db=db,
            action_type="approval_request_sent",
            duration_ms=duration_ms,
            input_data={
                "message_id": pending_approval.message_id,
                "approval_id": pending_approval.id,
                "source": pending_approval.source
            },
            output_data={
                "group_message_id": bridge_response.get('group_message_id'),
                "sent": True
            },
            message_id=pending_approval.message_id,
            conversation_id=pending_approval.conversation_id,
            request_id=request_id,
            user_id=pending_approval.user_id,
            source=pending_approval.source,
            status="success"
        )
        
        log_to_db(
            db,
            "INFO",
            f"Approval request sent to group for message_id {pending_approval.message_id}",
            service="approval_flow",
            request_id=request_id,
            metadata={
                "message_id": pending_approval.message_id,
                "approval_id": pending_approval.id,
                "group_message_id": bridge_response.get('group_message_id')
            }
        )
        
        return bridge_response
        
    except Exception as e:
        log_action(
            db=db,
            action_type="approval_request_sent",
            input_data={
                "message_id": pending_approval.message_id,
                "approval_id": pending_approval.id
            },
            message_id=pending_approval.message_id,
            conversation_id=pending_approval.conversation_id,
            request_id=request_id,
            user_id=pending_approval.user_id,
            source=pending_approval.source,
            status="error",
            error_message=str(e)
        )
        log_to_db(
            db,
            "ERROR",
            f"Failed to send approval request: {str(e)}",
            service="approval_flow",
            request_id=request_id,
            metadata={
                "message_id": pending_approval.message_id,
                "error": str(e)
            }
        )
        raise


async def process_approval(
    db: Session,
    approval_request: ApprovalRequest
) -> Dict[str, Any]:
    """
    Process user approval decision
    Supports both WhatsApp messages and email drafts
    """
    approval_type = approval_request.type or "whatsapp_message"
    
    if approval_type == "email_draft":
        return await process_email_draft_approval(db, approval_request)
    else:
        return await process_message_approval(db, approval_request)


async def process_message_approval(
    db: Session,
    approval_request: ApprovalRequest
) -> Dict[str, Any]:
    """Process WhatsApp message approval"""
    message_id = approval_request.message_id
    
    # Get pending approval from database
    pending_approval = db.query(PendingApproval).filter(
        PendingApproval.message_id == message_id,
        PendingApproval.status == 'pending'
    ).first()
    
    if not pending_approval:
        return {
            "status": "error",
            "message": "No pending approval found for this message",
            "sent": False
        }
    
    action = approval_request.action.lower()
    
    if action == "yes":
        if approval_request.option_index is None:
            return {
                "status": "error",
                "message": "option_index required for 'yes' action",
                "sent": False
            }
        
        # Get selected option
        options_map = {
            0: pending_approval.option_a,
            1: pending_approval.option_b,
            2: pending_approval.option_c
        }
        
        if approval_request.option_index not in options_map:
            return {
                "status": "error",
                "message": f"Invalid option_index. Choose 0-2",
                "sent": False
            }
        
        selected_option = options_map[approval_request.option_index]
        
        # Determine recipient
        recipient = None
        if pending_approval.source == 'whatsapp':
            recipient = pending_approval.recipient_jid
        elif pending_approval.source == 'gmail':
            recipient = pending_approval.recipient_email
        
        if not recipient:
            return {
                "status": "error",
                "message": "Cannot determine recipient",
                "sent": False
            }
        
        # Send message via bridge
        try:
            start_time = datetime.utcnow()
            # Add prefix to identify Minimee messages and avoid loops
            message_with_prefix = f"[🤖 Minimee] {selected_option}"
            bridge_response = await send_message_via_bridge(
                recipient=recipient,
                message_text=message_with_prefix,
                source=pending_approval.source,
                db=db
            )
            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            # Update approval status
            pending_approval.status = 'approved'
            db.commit()
            
            # Log action
            log_action(
                db=db,
                action_type="message_sent_via_bridge",
                duration_ms=duration_ms,
                input_data={
                    "message_id": message_id,
                    "approval_id": pending_approval.id,
                    "option_index": approval_request.option_index,
                    "recipient": recipient
                },
                output_data={
                    "sent": bridge_response.get("sent", False),
                    "selected_option_preview": selected_option[:100]
                },
                message_id=message_id,
                conversation_id=pending_approval.conversation_id,
                user_id=pending_approval.user_id,
                source=pending_approval.source,
                status="success"
            )
            
            return {
                "status": "approved",
                "message": "Response sent",
                "sent": True,
                "selected_option": selected_option
            }
        except Exception as e:
            log_action(
                db=db,
                action_type="message_sent_via_bridge",
                input_data={
                    "message_id": message_id,
                    "approval_id": pending_approval.id,
                    "option_index": approval_request.option_index
                },
                message_id=message_id,
                conversation_id=pending_approval.conversation_id,
                user_id=pending_approval.user_id,
                source=pending_approval.source,
                status="error",
                error_message=str(e)
            )
            return {
                "status": "error",
                "message": f"Failed to send message: {str(e)}",
                "sent": False
            }
    
    elif action == "no":
        pending_approval.status = 'rejected'
        db.commit()
        return {
            "status": "rejected",
            "message": "Response rejected",
            "sent": False
        }
    
    elif action == "maybe":
        # Keep pending
        return {
            "status": "pending",
            "message": "Response kept for later review",
            "sent": False
        }
    
    elif action == "reformulate":
        # Generate new options with reformulation hint
        # TODO: Implement reformulation
        return {
            "status": "reformulating",
            "message": "Generating new options...",
            "sent": False
        }
    
    else:
        return {
            "status": "error",
            "message": f"Unknown action: {action}",
            "sent": False
        }


async def process_email_draft_approval(
    db: Session,
    approval_request: ApprovalRequest
) -> Dict[str, Any]:
    """Process email draft approval (A/B/C/No) - Uses DB instead of memory"""
    thread_id = approval_request.email_thread_id
    
    if not thread_id:
        return {
            "status": "error",
            "message": "email_thread_id required for email draft approval",
            "sent": False
        }
    
    # Find pending approval by conversation_id (thread_id) and source='gmail'
    pending_approval = db.query(PendingApproval).filter(
        PendingApproval.conversation_id == thread_id,
        PendingApproval.source == 'gmail',
        PendingApproval.status == 'pending'
    ).first()
    
    if not pending_approval:
        # Fallback to old system for backward compatibility during transition
        if thread_id in _pending_email_drafts:
            message_options = _pending_email_drafts[thread_id]
            action = approval_request.action.lower()
            
            if action == "yes":
                if approval_request.option_index is None:
                    return {
                        "status": "error",
                        "message": "option_index required for 'yes' action (0=A, 1=B, 2=C)",
                        "sent": False
                    }
                
                if approval_request.option_index < 0 or approval_request.option_index >= len(message_options.options):
                    return {
                        "status": "error",
                        "message": f"Invalid option_index. Choose 0-{len(message_options.options)-1}",
                        "sent": False
                    }
                
                selected_draft = message_options.options[approval_request.option_index]
                del _pending_email_drafts[thread_id]
                
                return {
                    "status": "approved",
                    "message": "Email draft selected (legacy system)",
                    "sent": False,
                    "selected_draft": selected_draft
                }
            
            elif action == "no":
                del _pending_email_drafts[thread_id]
                return {
                    "status": "rejected",
                    "message": "All email drafts rejected",
                    "sent": False
                }
        
        return {
            "status": "error",
            "message": "No pending email draft found for this thread",
            "sent": False
        }
    
    action = approval_request.action.lower()
    
    if action == "yes":
        if approval_request.option_index is None:
            return {
                "status": "error",
                "message": "option_index required for 'yes' action (0=A, 1=B, 2=C)",
                "sent": False
            }
        
        # Get selected option
        options_map = {
            0: pending_approval.option_a,
            1: pending_approval.option_b,
            2: pending_approval.option_c
        }
        
        if approval_request.option_index not in options_map:
            return {
                "status": "error",
                "message": f"Invalid option_index. Choose 0-2",
                "sent": False
            }
        
        selected_draft = options_map[approval_request.option_index]
        option_labels = ['A', 'B', 'C']
        option_label = option_labels[approval_request.option_index] if approval_request.option_index < 3 else str(approval_request.option_index)
        
        # TODO: Store draft in Gmail drafts or send directly via Gmail API
        # For now, just log and mark as approved
        log_action(
            db=db,
            action_type="email_draft_approved",
            input_data={
                "thread_id": thread_id,
                "approval_id": pending_approval.id,
                "option_index": approval_request.option_index,
                "option_label": option_label
            },
            output_data={
                "selected_draft_preview": selected_draft[:200],
                "status": "approved"
            },
            conversation_id=thread_id,
            user_id=pending_approval.user_id,
            source='gmail',
            status="success"
        )
        
        log_to_db(
            db,
            "INFO",
            f"Email draft approved for thread {thread_id}: Option {option_label}",
            service="approval_flow",
            metadata={
                "thread_id": thread_id,
                "approval_id": pending_approval.id,
                "option_label": option_label
            }
        )
        
        # Mark as approved
        pending_approval.status = 'approved'
        db.commit()
        
        return {
            "status": "approved",
            "message": f"Email draft {option_label} selected and saved",
            "sent": False,  # Not sent yet, just saved as draft
            "selected_draft": selected_draft,
            "option_label": option_label
        }
    
    elif action == "no":
        pending_approval.status = 'rejected'
        db.commit()
        
        log_to_db(
            db,
            "INFO",
            f"Email draft rejected for thread {thread_id}",
            service="approval_flow",
            metadata={"thread_id": thread_id, "approval_id": pending_approval.id}
        )
        
        return {
            "status": "rejected",
            "message": "All email drafts rejected",
            "sent": False
        }
    
    elif action == "maybe":
        return {
            "status": "pending",
            "message": "Email drafts kept for later review",
            "sent": False
        }
    
    else:
        return {
            "status": "error",
            "message": f"Unknown action: {action}",
            "sent": False
        }


def store_email_draft_proposals(
    thread_id: str,
    message_options: MessageOptions
):
    """Store email draft proposals for approval"""
    _pending_email_drafts[thread_id] = message_options


async def send_pending_approval_reminders(db: Session) -> Dict[str, Any]:
    """
    Check for pending approvals that need reminders (10 minutes after creation)
    Sends reminder to WhatsApp group if no response received
    """
    from datetime import datetime, timedelta
    
    reminder_threshold = datetime.utcnow() - timedelta(minutes=settings.approval_reminder_minutes)
    
    # Find pending approvals that:
    # 1. Are still pending
    # 2. Were created more than reminder_minutes ago
    # 3. Haven't received a reminder yet
    pending_approvals = db.query(PendingApproval).filter(
        PendingApproval.status == 'pending',
        PendingApproval.created_at <= reminder_threshold,
        PendingApproval.reminder_sent_at.is_(None)
    ).all()
    
    results = {
        'checked': len(pending_approvals),
        'reminders_sent': 0,
        'errors': []
    }
    
    for approval in pending_approvals:
        try:
            # Calculate elapsed time
            elapsed_minutes = (datetime.utcnow() - approval.created_at).total_seconds() / 60
            
            # Send reminder notification
            reminder_text = f"""[🤖 Minimee] ⏰ Rappel

Message #{approval.message_id} toujours en attente depuis {int(elapsed_minutes)} minutes.

Répondez: A, B, C ou No"""
            
            # Send to bridge
            reminder_data = {
                "message_id": approval.message_id,
                "approval_id": approval.id,
                "message_text": reminder_text,
                "options": {
                    "A": approval.option_a,
                    "B": approval.option_b,
                    "C": approval.option_c
                },
                "sender": approval.sender,
                "source": approval.source,
                "is_reminder": True
            }
            
            bridge_response = await send_approval_request_to_bridge(reminder_data, db)
            
            # Update reminder_sent_at
            approval.reminder_sent_at = datetime.utcnow()
            db.commit()
            
            # Log action
            log_action(
                db=db,
                action_type="approval_reminder_sent",
                input_data={
                    "message_id": approval.message_id,
                    "approval_id": approval.id,
                    "elapsed_minutes": elapsed_minutes
                },
                output_data={
                    "reminder_sent": True,
                    "group_message_id": bridge_response.get('group_message_id')
                },
                message_id=approval.message_id,
                conversation_id=approval.conversation_id,
                user_id=approval.user_id,
                source=approval.source,
                status="success"
            )
            
            log_to_db(
                db,
                "INFO",
                f"Reminder sent for pending approval {approval.id} (message_id: {approval.message_id})",
                service="approval_flow",
                metadata={
                    "approval_id": approval.id,
                    "message_id": approval.message_id,
                    "elapsed_minutes": elapsed_minutes
                }
            )
            
            results['reminders_sent'] += 1
            
        except Exception as e:
            error_msg = f"Failed to send reminder for approval {approval.id}: {str(e)}"
            results['errors'].append(error_msg)
            log_to_db(
                db,
                "ERROR",
                error_msg,
                service="approval_flow",
                metadata={
                    "approval_id": approval.id,
                    "message_id": approval.message_id,
                    "error": str(e)
                }
            )
    
    return results
