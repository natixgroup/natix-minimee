"""
Email draft generation service
Generates draft reply options using RAG context
"""
import asyncio
from sqlalchemy.orm import Session
from typing import List, Optional
from models import GmailThread, Message
from services.rag_llamaindex import retrieve_context
from services.llm_router import generate_multiple_options
from services.agent_manager import select_agent_for_context
from services.logs_service import log_to_db


async def generate_email_drafts(
    db: Session,
    thread_id: str,
    user_id: int,
    num_options: int = 3
) -> List[str]:
    """
    Generate email draft reply options for a Gmail thread
    Returns list of draft options (A/B/C format)
    """
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
        
        # Retrieve context using RAG (searches Gmail history, limit to current thread)
        context = retrieve_context(
            db=db,
            query=last_message.content,
            user_id=user_id,
            limit=5,
            language=None,
            use_chunks=True,
            conversation_id=thread_id  # Limit to current thread for better context
        )
        
        # Select appropriate agent
        agent = select_agent_for_context(db, last_message.content, user_id)
        
        # Build prompt for email draft
        subject = thread.subject or "Re: Your message"
        recipient = next(iter(thread.participants or []), "Recipient")
        
        # Extract recipient email if available
        if '<' in recipient and '>' in recipient:
            recipient_name = recipient.split('<')[0].strip()
            recipient_email = recipient.split('<')[1].split('>')[0]
        else:
            recipient_name = recipient
            recipient_email = recipient
        
        # Build system prompt
        if agent:
            system_prompt = f"""You are {agent.name}, {agent.role}. {agent.prompt}
You are drafting an email reply. Be professional and contextually appropriate."""
            if agent.style:
                system_prompt += f"\nCommunication style: {agent.style}"
        else:
            system_prompt = "You are Minimee, a personal AI assistant drafting an email reply. Be professional and contextually appropriate."
        
        # Build full prompt
        full_prompt = f"""{system_prompt}

Email Context:
Subject: {subject}
To: {recipient_name} ({recipient_email})

Conversation History:
{context}

Last Message to Reply To:
{last_message.content}

Generate {num_options} different draft reply options. Each option should be a complete, professional email reply that:
1. Addresses the points raised in the last message
2. Is contextually appropriate based on conversation history
3. Matches the communication style
4. Is concise but comprehensive

Format each draft as a complete email ready to send."""

        # Generate multiple draft options
        drafts = await generate_multiple_options(full_prompt, num_options, db)
        
        log_to_db(
            db,
            "INFO",
            f"Generated {len(drafts)} email draft options for thread {thread_id}",
            service="email_draft"
        )
        
        return drafts
    
    except Exception as e:
        log_to_db(db, "ERROR", f"Email draft generation error: {str(e)}", service="email_draft")
        raise


def generate_email_drafts_sync(
    db: Session,
    thread_id: str,
    user_id: int,
    num_options: int = 3
) -> List[str]:
    """
    Synchronous wrapper for generate_email_drafts
    """
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(
        generate_email_drafts(db, thread_id, user_id, num_options)
    )

