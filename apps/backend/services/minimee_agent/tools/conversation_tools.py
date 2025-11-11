"""
LangChain tools for conversation and context management
"""
from typing import Optional
from langchain.tools import tool
from sqlalchemy.orm import Session
from models import Message, Summary
from ..retriever import create_advanced_retriever, create_simple_retriever
from services.logs_service import log_to_db


@tool
def search_conversation_history(
    query: str,
    user_id: int,
    limit: int = 10
) -> str:
    """
    Search through conversation history (WhatsApp and Gmail) using RAG.
    Finds relevant past messages based on semantic similarity.
    
    Args:
        query: Search query to find relevant conversations
        user_id: User ID to search within
        limit: Maximum number of results to return (default: 10)
    
    Returns:
        Formatted string with relevant conversation snippets
    """
    # This will be called from within an agent context with db and llm available
    # For now, return a placeholder - the actual implementation will be in the agent
    return f"Searching conversation history for: {query} (user_id: {user_id}, limit: {limit})"


def create_search_conversation_tool(db: Session, llm, user_id: int):
    """
    Create search_conversation_history tool with database and LLM context
    
    Args:
        db: Database session
        llm: Language model for advanced retriever
        user_id: User ID
    
    Returns:
        Tool instance
    """
    @tool
    def search_conversation_history_tool(query: str, limit: int = 10) -> str:
        """Search conversation history using RAG"""
        try:
            # Use simple retriever directly - bypass any wrapper that might return RunnableBranch
            from ..vector_store import get_vector_store_retriever
            retriever = get_vector_store_retriever(
                db=db,
                user_id=user_id,
                limit=limit,
                threshold=0.15  # Lower threshold for better recall (especially for proper names)
            )
            
            # Retrieve documents - use invoke (get_relevant_documents is deprecated)
            try:
                # BaseRetriever.invoke() accepts a string directly in LangChain 0.2.x
                if hasattr(retriever, 'invoke'):
                    result = retriever.invoke(query)
                    # invoke returns a list of Documents
                    docs = result if isinstance(result, list) else [result] if result else []
                elif hasattr(retriever, 'get_relevant_documents'):
                    # Fallback for older versions
                    docs = retriever.get_relevant_documents(query)
                else:
                    log_to_db(db, "ERROR", f"Retriever has neither invoke nor get_relevant_documents: {type(retriever)}", service="minimee_agent")
                    return "Error: Retriever not compatible"
            except Exception as e:
                log_to_db(db, "ERROR", f"Error retrieving documents: {str(e)}, retriever_type={type(retriever)}", service="minimee_agent")
                import traceback
                log_to_db(db, "ERROR", f"Traceback: {traceback.format_exc()}", service="minimee_agent")
                return f"Error retrieving documents: {str(e)}"
            
            if not docs:
                return "No relevant conversation history found."
            
            # Format results
            results = []
            for doc in docs:
                metadata = doc.metadata if hasattr(doc, 'metadata') else {}
                sender = metadata.get('sender', 'Unknown')
                if not sender or sender == 'Unknown':
                    # Try to extract sender from text if available
                    text = doc.page_content if hasattr(doc, 'page_content') else str(doc)
                    if ':' in text:
                        sender = text.split(':')[0].strip()
                
                timestamp = metadata.get('timestamp', '')
                similarity = metadata.get('similarity', 0)
                
                # Get text content
                text_content = doc.page_content if hasattr(doc, 'page_content') else str(doc)
                
                # Format result line
                if timestamp:
                    result_line = f"[{timestamp}] {sender}: {text_content[:200]}"
                else:
                    result_line = f"{sender}: {text_content[:200]}"
                
                if similarity:
                    result_line += f" (similarity: {similarity:.2f})"
                results.append(result_line)
            
            formatted_result = "\n".join(results)
            log_to_db(db, "INFO", f"Search found {len(results)} results for query: {query[:50]}", service="minimee_agent", user_id=user_id)
            
            # Log the actual result being returned for debugging
            log_to_db(db, "DEBUG", f"Search result preview: {formatted_result[:200]}...", service="minimee_agent", user_id=user_id)
            
            return formatted_result
        except Exception as e:
            log_to_db(db, "ERROR", f"Search conversation history failed: {str(e)}", service="minimee_agent")
            return f"Error searching conversation history: {str(e)}"
    
    # Update tool description
    search_conversation_history_tool.name = "search_conversation_history"
    search_conversation_history_tool.description = (
        "Search through conversation history (WhatsApp and Gmail) using RAG. "
        "Finds relevant past messages based on semantic similarity. "
        "Use this when you need context from previous conversations."
    )
    
    return search_conversation_history_tool


@tool
def get_recent_messages(conversation_id: str, limit: int = 10) -> str:
    """
    Get recent messages from a specific conversation.
    Useful for understanding the immediate context of the current conversation.
    
    Args:
        conversation_id: Conversation ID to retrieve messages from
        limit: Number of recent messages to retrieve (default: 10)
    
    Returns:
        Formatted string with recent messages
    """
    return f"Getting recent messages from conversation: {conversation_id} (limit: {limit})"


def create_get_recent_messages_tool(db: Session, user_id: int):
    """
    Create get_recent_messages tool with database context
    
    Args:
        db: Database session
        user_id: User ID
    
    Returns:
        Tool instance
    """
    @tool
    def get_recent_messages_tool(conversation_id: str, limit: int = 10) -> str:
        """Get recent messages from a conversation"""
        try:
            messages = db.query(Message).filter(
                Message.conversation_id == conversation_id,
                Message.user_id == user_id
            ).order_by(Message.timestamp.desc()).limit(limit).all()
            
            if not messages:
                return f"No messages found in conversation {conversation_id}"
            
            # Reverse to get chronological order
            messages.reverse()
            
            results = []
            for msg in messages:
                timestamp_str = msg.timestamp.strftime('%Y-%m-%d %H:%M') if msg.timestamp else 'Unknown'
                results.append(f"[{timestamp_str}] {msg.sender}: {msg.content}")
            
            return "\n".join(results)
        except Exception as e:
            log_to_db(db, "ERROR", f"Get recent messages failed: {str(e)}", service="minimee_agent")
            return f"Error retrieving recent messages: {str(e)}"
    
    get_recent_messages_tool.name = "get_recent_messages"
    get_recent_messages_tool.description = (
        "Get recent messages from a specific conversation. "
        "Useful for understanding the immediate context of the current conversation."
    )
    
    return get_recent_messages_tool


@tool
def summarize_conversation(conversation_id: str) -> str:
    """
    Get a summary of a conversation if available.
    Summaries include TL;DR and tags for quick understanding.
    
    Args:
        conversation_id: Conversation ID to summarize
    
    Returns:
        Summary text with TL;DR and tags
    """
    return f"Getting summary for conversation: {conversation_id}"


def create_summarize_conversation_tool(db: Session, user_id: int):
    """
    Create summarize_conversation tool with database context
    
    Args:
        db: Database session
        user_id: User ID
    
    Returns:
        Tool instance
    """
    @tool
    def summarize_conversation_tool(conversation_id: str) -> str:
        """Get conversation summary"""
        try:
            summary = db.query(Summary).filter(
                Summary.conversation_id == conversation_id
            ).first()
            
            if not summary:
                return f"No summary available for conversation {conversation_id}"
            
            return summary.summary_text
        except Exception as e:
            log_to_db(db, "ERROR", f"Get conversation summary failed: {str(e)}", service="minimee_agent")
            return f"Error retrieving summary: {str(e)}"
    
    summarize_conversation_tool.name = "summarize_conversation"
    summarize_conversation_tool.description = (
        "Get a summary of a conversation if available. "
        "Summaries include TL;DR and tags for quick understanding."
    )
    
    return summarize_conversation_tool


