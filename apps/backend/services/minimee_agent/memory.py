"""
Conversation memory management for Minimee agents
Uses LangChain's ConversationSummaryBufferMemory with persistent storage
"""
from typing import List, Optional, Dict, Any
from langchain.memory import ConversationSummaryBufferMemory
from langchain_core.language_models import BaseLanguageModel
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.chat_history import BaseChatMessageHistory
from sqlalchemy.orm import Session
from models import Message
from datetime import datetime


class PersistentChatMessageHistory(BaseChatMessageHistory):
    """
    Persistent chat message history stored in database
    Uses the messages table to store conversation history
    """
    
    def __init__(self, db: Session, conversation_id: str, user_id: int):
        self.db = db
        self.conversation_id = conversation_id
        self.user_id = user_id
    
    @property
    def messages(self) -> List[BaseMessage]:
        """Load messages from database"""
        db_messages = self.db.query(Message).filter(
            Message.conversation_id == self.conversation_id,
            Message.user_id == self.user_id
        ).order_by(Message.timestamp.asc()).all()
        
        langchain_messages = []
        for msg in db_messages:
            if msg.sender == "User" or msg.source == "dashboard":
                langchain_messages.append(HumanMessage(content=msg.content))
            elif msg.sender == "Minimee" or msg.source == "minimee":
                langchain_messages.append(AIMessage(content=msg.content))
            else:
                # Other senders as human messages
                langchain_messages.append(HumanMessage(content=f"{msg.sender}: {msg.content}"))
        
        return langchain_messages
    
    def add_user_message(self, message: str) -> None:
        """Add user message to database"""
        msg = Message(
            content=message,
            sender="User",
            timestamp=datetime.utcnow(),
            source="dashboard",
            conversation_id=self.conversation_id,
            user_id=self.user_id
        )
        self.db.add(msg)
        self.db.commit()
    
    def add_ai_message(self, message: str) -> None:
        """Add AI message to database"""
        msg = Message(
            content=message,
            sender="Minimee",
            timestamp=datetime.utcnow(),
            source="minimee",
            conversation_id=self.conversation_id,
            user_id=self.user_id
        )
        self.db.add(msg)
        self.db.commit()
    
    def add_message(self, message: BaseMessage) -> None:
        """Add a message to the history (required by BaseChatMessageHistory)"""
        if isinstance(message, HumanMessage):
            self.add_user_message(message.content)
        elif isinstance(message, AIMessage):
            self.add_ai_message(message.content)
        else:
            # Generic message - treat as user message
            self.add_user_message(message.content)
    
    def add_messages(self, messages: List[BaseMessage]) -> None:
        """Add multiple messages to the history"""
        for message in messages:
            self.add_message(message)
    
    def clear(self) -> None:
        """Clear conversation history (not implemented - keep history)"""
        pass


class MinimeeConversationBufferMemory(ConversationSummaryBufferMemory):
    """
    Custom ConversationSummaryBufferMemory that properly delegates add_message
    """
    
    def add_message(self, message: BaseMessage) -> None:
        """Add message to chat history - delegate to chat_memory"""
        # Always delegate to chat_memory if it exists
        if hasattr(self, 'chat_memory') and self.chat_memory is not None:
            if hasattr(self.chat_memory, 'add_message'):
                self.chat_memory.add_message(message)
            else:
                # Fallback: use add_user_message or add_ai_message
                if isinstance(message, HumanMessage):
                    if hasattr(self.chat_memory, 'add_user_message'):
                        self.chat_memory.add_user_message(message.content)
                elif isinstance(message, AIMessage):
                    if hasattr(self.chat_memory, 'add_ai_message'):
                        self.chat_memory.add_ai_message(message.content)
        # Don't call super() - it will fail
    
    def add_messages(self, messages: List[BaseMessage]) -> None:
        """Add multiple messages to chat history"""
        for message in messages:
            self.add_message(message)
    
    def save_context(self, inputs: Dict[str, Any], outputs: Dict[str, str]) -> None:
        """Override save_context to use our custom add_message"""
        # Extract messages from inputs/outputs
        from langchain_core.messages import HumanMessage, AIMessage
        
        # Get input message
        if "input" in inputs:
            input_msg = HumanMessage(content=str(inputs["input"]))
            self.add_message(input_msg)
        
        # Get output message
        if "output" in outputs:
            output_msg = AIMessage(content=str(outputs["output"]))
            self.add_message(output_msg)


def create_conversation_memory(
    llm: BaseLanguageModel,
    db: Session,
    conversation_id: str,
    user_id: int,
    max_token_limit: int = 2000,
    return_messages: bool = True
) -> MinimeeConversationBufferMemory:
    """
    Create conversation memory with automatic summarization
    
    Args:
        llm: Language model for summarization
        db: Database session
        conversation_id: Conversation ID
        user_id: User ID
        max_token_limit: Maximum tokens before summarization kicks in
        return_messages: Whether to return messages or strings
    
    Returns:
        MinimeeConversationBufferMemory instance
    """
    # Create persistent message history
    chat_history = PersistentChatMessageHistory(
        db=db,
        conversation_id=conversation_id,
        user_id=user_id
    )
    
    # Create memory with summarization
    memory = MinimeeConversationBufferMemory(
        llm=llm,
        chat_memory=chat_history,
        max_token_limit=max_token_limit,
        return_messages=return_messages,
        memory_key="chat_history"
    )
    
    return memory


def get_recent_messages_for_context(
    db: Session,
    conversation_id: str,
    user_id: int,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Get recent messages formatted for context
    
    Args:
        db: Database session
        conversation_id: Conversation ID
        user_id: User ID
        limit: Number of recent messages to retrieve
    
    Returns:
        List of message dicts with sender, content, timestamp
    """
    messages = db.query(Message).filter(
        Message.conversation_id == conversation_id,
        Message.user_id == user_id
    ).order_by(Message.timestamp.desc()).limit(limit).all()
    
    # Reverse to get chronological order
    messages.reverse()
    
    return [
        {
            "sender": msg.sender,
            "content": msg.content,
            "timestamp": msg.timestamp.isoformat() if msg.timestamp else None,
            "source": msg.source
        }
        for msg in messages
    ]


