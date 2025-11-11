"""
LangChain tools for Gmail operations
"""
from typing import Optional
from langchain.tools import tool
from sqlalchemy.orm import Session
from models import Message, GmailThread
from services.logs_service import log_to_db


@tool
def search_gmail(query: str, user_id: int, limit: int = 10) -> str:
    """
    Search for emails in Gmail using a search query.
    Returns matching email threads with subject and participants.
    
    Args:
        query: Search query (searches in subject, participants, content)
        user_id: User ID to search within
        limit: Maximum number of results (default: 10)
    
    Returns:
        Formatted string with matching email threads
    """
    return f"Searching Gmail for: {query} (user_id: {user_id}, limit: {limit})"


def create_search_gmail_tool(db: Session, user_id: int):
    """
    Create search_gmail tool with database context
    
    Args:
        db: Database session
        user_id: User ID
    
    Returns:
        Tool instance
    """
    @tool
    def search_gmail_tool(query: str, limit: int = 10) -> str:
        """Search Gmail threads"""
        try:
            # Search in Gmail threads and messages
            threads = db.query(GmailThread).filter(
                GmailThread.user_id == user_id
            ).all()
            
            # Also search in messages with Gmail source
            messages = db.query(Message).filter(
                Message.user_id == user_id,
                Message.source == "gmail"
            ).filter(
                Message.content.ilike(f"%{query}%")
            ).limit(limit).all()
            
            results = []
            
            # Add thread results
            for thread in threads[:limit]:
                if query.lower() in (thread.subject or "").lower():
                    participants_str = ", ".join(thread.participants or [])
                    results.append(f"Thread: {thread.subject} | Participants: {participants_str}")
            
            # Add message results
            for msg in messages:
                results.append(f"Email: {msg.sender} -> {msg.content[:100]}...")
            
            if not results:
                return f"No Gmail results found for: {query}"
            
            return "\n".join(results[:limit])
        except Exception as e:
            log_to_db(db, "ERROR", f"Search Gmail failed: {str(e)}", service="minimee_agent")
            return f"Error searching Gmail: {str(e)}"
    
    search_gmail_tool.name = "search_gmail"
    search_gmail_tool.description = (
        "Search for emails in Gmail using a search query. "
        "Returns matching email threads with subject and participants."
    )
    
    return search_gmail_tool


@tool
def get_gmail_thread(thread_id: str) -> str:
    """
    Get all messages from a Gmail thread.
    Returns the complete conversation thread.
    
    Args:
        thread_id: Gmail thread ID
    
    Returns:
        Formatted string with all messages in the thread
    """
    return f"Getting Gmail thread: {thread_id}"


def create_get_gmail_thread_tool(db: Session, user_id: int):
    """
    Create get_gmail_thread tool with database context
    
    Args:
        db: Database session
        user_id: User ID
    
    Returns:
        Tool instance
    """
    @tool
    def get_gmail_thread_tool(thread_id: str) -> str:
        """Get Gmail thread messages"""
        try:
            thread = db.query(GmailThread).filter(
                GmailThread.thread_id == thread_id,
                GmailThread.user_id == user_id
            ).first()
            
            if not thread:
                return f"Thread {thread_id} not found"
            
            # Get all messages in thread
            messages = db.query(Message).filter(
                Message.conversation_id == thread_id,
                Message.user_id == user_id,
                Message.source == "gmail"
            ).order_by(Message.timestamp.asc()).all()
            
            results = [f"Thread: {thread.subject}"]
            results.append(f"Participants: {', '.join(thread.participants or [])}")
            results.append("")
            
            for msg in messages:
                timestamp_str = msg.timestamp.strftime('%Y-%m-%d %H:%M') if msg.timestamp else 'Unknown'
                results.append(f"[{timestamp_str}] {msg.sender}: {msg.content}")
            
            return "\n".join(results)
        except Exception as e:
            log_to_db(db, "ERROR", f"Get Gmail thread failed: {str(e)}", service="minimee_agent")
            return f"Error retrieving thread: {str(e)}"
    
    get_gmail_thread_tool.name = "get_gmail_thread"
    get_gmail_thread_tool.description = (
        "Get all messages from a Gmail thread. "
        "Returns the complete conversation thread."
    )
    
    return get_gmail_thread_tool


@tool
def draft_gmail_reply(thread_id: str, message: str) -> str:
    """
    Create a draft reply for a Gmail thread.
    Note: This creates a draft in the database, actual Gmail draft creation requires Gmail API with write scope.
    
    Args:
        thread_id: Gmail thread ID to reply to
        message: Reply message content
    
    Returns:
        Status message
    """
    return f"Creating draft reply for thread {thread_id}"


def create_draft_gmail_reply_tool(db: Session, user_id: int):
    """
    Create draft_gmail_reply tool with database context
    
    Args:
        db: Database session
        user_id: User ID
    
    Returns:
        Tool instance
    """
    @tool
    def draft_gmail_reply_tool(thread_id: str, message: str) -> str:
        """Create Gmail draft reply"""
        try:
            thread = db.query(GmailThread).filter(
                GmailThread.thread_id == thread_id,
                GmailThread.user_id == user_id
            ).first()
            
            if not thread:
                return f"Thread {thread_id} not found"
            
            # For now, just log the draft
            # TODO: Integrate with Gmail API to create actual draft
            log_to_db(
                db,
                "INFO",
                f"Draft reply created for thread {thread_id}",
                service="minimee_agent",
                metadata={"thread_id": thread_id, "draft_preview": message[:100]}
            )
            
            return f"Draft reply created for thread {thread_id}. Note: Actual Gmail draft requires API integration."
        except Exception as e:
            log_to_db(db, "ERROR", f"Create Gmail draft failed: {str(e)}", service="minimee_agent")
            return f"Error creating draft: {str(e)}"
    
    draft_gmail_reply_tool.name = "draft_gmail_reply"
    draft_gmail_reply_tool.description = (
        "Create a draft reply for a Gmail thread. "
        "Note: This creates a draft in the database, actual Gmail draft creation requires Gmail API with write scope."
    )
    
    return draft_gmail_reply_tool


