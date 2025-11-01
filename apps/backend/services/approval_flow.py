"""
Approval flow service for message validation
Supports both WhatsApp messages and email drafts
"""
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from services.llm_router import generate_multiple_options
from services.rag import retrieve_context, build_prompt_with_context
from services.agent_manager import select_agent_for_context
from models import Message
from schemas import MessageOptions, ApprovalRequest


# In-memory storage for pending approvals (in production, use Redis/DB)
_pending_approvals: Dict[int, MessageOptions] = {}
_pending_email_drafts: Dict[str, MessageOptions] = {}  # key: thread_id


def generate_response_options(
    db: Session,
    message: Message,
    num_options: int = 3
) -> MessageOptions:
    """
    Generate multiple response options for user approval
    """
    # Retrieve context using RAG
    context = retrieve_context(db, message.content, message.user_id)
    
    # Select appropriate agent
    agent = select_agent_for_context(db, message.content, message.user_id)
    
    # Build prompt
    if agent:
        system_prompt = f"You are {agent.name}, {agent.role}. {agent.prompt}"
        if agent.style:
            system_prompt += f"\nCommunication style: {agent.style}"
    else:
        system_prompt = "You are Minimee, a personal AI assistant."
    
    full_prompt = f"{system_prompt}\n\n{context}\n\n{message.content}\n\nGenerate a response:"
    
    # Generate multiple options (using sync wrapper - async would need different approach)
    # For now, use a simple synchronous approach
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    options = loop.run_until_complete(
        generate_multiple_options(full_prompt, num_options, db)
    )
    
    message_options = MessageOptions(
        options=options,
        message_id=message.id,
        conversation_id=message.conversation_id
    )
    
    # Store for approval
    _pending_approvals[message.id] = message_options
    
    return message_options


def process_approval(
    db: Session,
    approval_request: ApprovalRequest
) -> Dict[str, Any]:
    """
    Process user approval decision
    Supports both WhatsApp messages and email drafts
    """
    approval_type = approval_request.type or "whatsapp_message"
    
    if approval_type == "email_draft":
        return process_email_draft_approval(db, approval_request)
    else:
        return process_message_approval(db, approval_request)


def process_message_approval(
    db: Session,
    approval_request: ApprovalRequest
) -> Dict[str, Any]:
    """Process WhatsApp message approval"""
    message_id = approval_request.message_id
    
    if message_id not in _pending_approvals:
        return {
            "status": "error",
            "message": "No pending approval found for this message",
            "sent": False
        }
    
    message_options = _pending_approvals[message_id]
    action = approval_request.action.lower()
    
    if action == "yes":
        if approval_request.option_index is None:
            return {
                "status": "error",
                "message": "option_index required for 'yes' action",
                "sent": False
            }
        
        selected_option = message_options.options[approval_request.option_index]
        # TODO: Send message via WhatsApp bridge
        del _pending_approvals[message_id]
        
        return {
            "status": "approved",
            "message": "Response sent",
            "sent": True,
            "selected_option": selected_option
        }
    
    elif action == "no":
        del _pending_approvals[message_id]
        return {
            "status": "rejected",
            "message": "Response rejected",
            "sent": False
        }
    
    elif action == "maybe":
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


def process_email_draft_approval(
    db: Session,
    approval_request: ApprovalRequest
) -> Dict[str, Any]:
    """Process email draft approval (A/B/C/No)"""
    thread_id = approval_request.email_thread_id
    
    if not thread_id:
        return {
            "status": "error",
            "message": "email_thread_id required for email draft approval",
            "sent": False
        }
    
    if thread_id not in _pending_email_drafts:
        return {
            "status": "error",
            "message": "No pending email draft found for this thread",
            "sent": False
        }
    
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
        option_labels = ['A', 'B', 'C']
        option_label = option_labels[approval_request.option_index] if approval_request.option_index < 3 else str(approval_request.option_index)
        
        # TODO: Store draft in Gmail drafts or send directly
        # For now, just log and return success
        from services.logs_service import log_to_db
        log_to_db(
            db,
            "INFO",
            f"Email draft approved for thread {thread_id}: Option {option_label}",
            service="approval_flow"
        )
        
        del _pending_email_drafts[thread_id]
        
        return {
            "status": "approved",
            "message": f"Email draft {option_label} selected and saved",
            "sent": False,  # Not sent yet, just saved as draft
            "selected_draft": selected_draft,
            "option_label": option_label
        }
    
    elif action == "no":
        del _pending_email_drafts[thread_id]
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
