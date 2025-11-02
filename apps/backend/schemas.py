"""
Pydantic schemas for request/response validation
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


# Settings Schemas
class SettingCreate(BaseModel):
    key: str
    value: Dict[str, Any]
    user_id: Optional[int] = None


class SettingResponse(BaseModel):
    id: int
    key: str
    value: Dict[str, Any]
    user_id: Optional[int]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Policy Schemas
class PolicyCreate(BaseModel):
    name: str
    rules: Dict[str, Any]
    user_id: int


class PolicyUpdate(BaseModel):
    name: Optional[str] = None
    rules: Optional[Dict[str, Any]] = None


class PolicyResponse(BaseModel):
    id: int
    name: str
    rules: Dict[str, Any]
    user_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Agent Schemas
class AgentCreate(BaseModel):
    name: str
    role: str
    prompt: str
    style: Optional[str] = None
    enabled: bool = True
    user_id: int


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    prompt: Optional[str] = None
    style: Optional[str] = None
    enabled: Optional[bool] = None


class AgentResponse(BaseModel):
    id: int
    name: str
    role: str
    prompt: str
    style: Optional[str]
    enabled: bool
    user_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Prompt Schemas
class PromptCreate(BaseModel):
    name: str
    content: str
    agent_id: Optional[int] = None


class PromptUpdate(BaseModel):
    name: Optional[str] = None
    content: Optional[str] = None
    agent_id: Optional[int] = None


class PromptResponse(BaseModel):
    id: int
    name: str
    content: str
    agent_id: Optional[int]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Message Schemas
class MessageCreate(BaseModel):
    content: str
    sender: str
    timestamp: datetime
    source: str  # 'whatsapp' or 'gmail'
    conversation_id: Optional[str] = None
    user_id: int


class MessageResponse(BaseModel):
    id: int
    content: str
    sender: str
    recipient: Optional[str]
    recipients: Optional[List[str]]
    timestamp: datetime
    source: str
    conversation_id: Optional[str]
    user_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class MessageOptions(BaseModel):
    options: List[str]
    message_id: int
    conversation_id: Optional[str] = None


# Approval Schemas
class ApprovalRequest(BaseModel):
    message_id: int
    option_index: Optional[int] = None  # For "yes" approval (0=A, 1=B, 2=C)
    action: str  # "yes", "no", "maybe", "reformulate"
    reformulation_hint: Optional[str] = None  # For "reformulate"
    type: Optional[str] = "whatsapp_message"  # "whatsapp_message" | "email_draft"
    email_thread_id: Optional[str] = None  # For email drafts


class ApprovalResponse(BaseModel):
    status: str
    message: str
    sent: bool = False


# Gmail Schemas
class GmailFetchRequest(BaseModel):
    days: int = 30
    only_replied: bool = True


class GmailThreadResponse(BaseModel):
    id: int
    thread_id: str
    subject: Optional[str]
    participants: Optional[List[str]]
    last_message_date: Optional[datetime]
    user_id: int
    created_at: datetime

    class Config:
        from_attributes = True


# Log Schemas
class LogQuery(BaseModel):
    level: Optional[str] = None
    service: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    limit: int = 100
    offset: int = 0


class LogResponse(BaseModel):
    id: int
    level: str
    message: str
    metadata: Optional[Dict[str, Any]]
    service: Optional[str]
    timestamp: datetime

    class Config:
        from_attributes = True


# Action Log Schemas
class ActionLogResponse(BaseModel):
    id: int
    action_type: str
    duration_ms: Optional[float]
    model: Optional[str]
    input_data: Optional[Dict[str, Any]]
    output_data: Optional[Dict[str, Any]]
    metadata: Optional[Dict[str, Any]]  # JSON field name is metadata, but model uses meta_data
    message_id: Optional[int]
    conversation_id: Optional[str]
    request_id: Optional[str]
    user_id: Optional[int]
    source: Optional[str]
    status: Optional[str]
    error_message: Optional[str]
    timestamp: datetime

    class Config:
        from_attributes = True


class ActionLogQuery(BaseModel):
    action_type: Optional[str] = None
    request_id: Optional[str] = None
    message_id: Optional[int] = None
    conversation_id: Optional[str] = None
    user_id: Optional[int] = None
    source: Optional[str] = None
    status: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    limit: int = 100
    offset: int = 0


# Embedding Schemas
class EmbeddingMessageInfo(BaseModel):
    """Info about associated message if message_id exists"""
    id: int
    content: str
    sender: str
    recipient: Optional[str]
    recipients: Optional[List[str]]
    source: str
    conversation_id: Optional[str]
    timestamp: datetime

    class Config:
        from_attributes = True


class EmbeddingResponse(BaseModel):
    id: int
    text: str
    source: Optional[str]  # from metadata or message.source
    metadata: Optional[Dict[str, Any]]
    message_id: Optional[int]
    message: Optional[EmbeddingMessageInfo]  # Full message info if exists
    created_at: datetime

    class Config:
        from_attributes = True


class EmbeddingsListResponse(BaseModel):
    """Paginated response for embeddings list"""
    embeddings: List[EmbeddingResponse]
    total: int
    page: int
    limit: int
    total_pages: int


# Chat Schemas
class ChatMessageRequest(BaseModel):
    content: str
    user_id: int
    conversation_id: Optional[str] = None


class ChatMessageResponse(BaseModel):
    id: int
    content: str
    sender: str
    timestamp: datetime
    source: str
    conversation_id: Optional[str] = None

    class Config:
        from_attributes = True

