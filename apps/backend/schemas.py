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
    whatsapp_display_name: Optional[str] = None
    approval_rules: Optional[Dict] = None


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    prompt: Optional[str] = None
    style: Optional[str] = None
    enabled: Optional[bool] = None
    whatsapp_display_name: Optional[str] = None
    approval_rules: Optional[Dict] = None


class AgentResponse(BaseModel):
    id: int
    name: str
    role: str
    prompt: str
    style: Optional[str]
    enabled: bool
    user_id: int
    is_minimee_leader: bool
    whatsapp_integration_id: Optional[int]
    whatsapp_display_name: Optional[str]
    approval_rules: Optional[Dict]
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
    sender: Optional[str] = "User"
    source: Optional[str] = "dashboard"
    timestamp: Optional[str] = None
    agent_name: Optional[str] = None  # For routing to specific agent via [Agent Name] prefix


class ChatMessageResponse(BaseModel):
    id: int
    content: str
    sender: str
    timestamp: datetime
    source: str
    conversation_id: Optional[str] = None

    class Config:
        from_attributes = True


# WhatsApp Integration Schemas
class WhatsAppIntegrationCreate(BaseModel):
    user_id: int
    integration_type: str  # 'user' or 'minimee'
    phone_number: Optional[str] = None
    display_name: Optional[str] = None
    status: str = 'disconnected'  # connected/disconnected/pending
    auth_info_path: Optional[str] = None


class WhatsAppIntegrationUpdate(BaseModel):
    phone_number: Optional[str] = None
    display_name: Optional[str] = None
    status: Optional[str] = None
    auth_info_path: Optional[str] = None


class WhatsAppIntegrationResponse(BaseModel):
    id: int
    user_id: int
    integration_type: str
    phone_number: Optional[str]
    display_name: Optional[str]
    status: str
    auth_info_path: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Relation Type Schemas
class RelationTypeResponse(BaseModel):
    id: int
    code: str
    label_masculin: str
    label_feminin: str
    label_autre: Optional[str]
    category: str  # 'personnel' or 'professionnel'
    display_order: int
    is_active: bool
    meta_data: Optional[Dict[str, Any]] = None  # Renamed from metadata to match model
    
    class Config:
        from_attributes = True
        populate_by_name = True  # Allow both meta_data and metadata in JSON


# Contact Schemas
class ContactCreate(BaseModel):
    user_id: int
    conversation_id: str
    first_name: Optional[str] = None
    nickname: Optional[str] = None
    gender: Optional[str] = None  # masculin, féminin, autre
    relation_type_ids: Optional[List[int]] = None  # List of relation_type IDs
    context: Optional[str] = None
    languages: Optional[List[str]] = None
    location: Optional[str] = None
    importance_rating: Optional[int] = Field(None, ge=1, le=5)
    dominant_themes: Optional[List[str]] = None


class ContactUpdate(BaseModel):
    first_name: Optional[str] = None
    nickname: Optional[str] = None
    gender: Optional[str] = None
    relation_type_ids: Optional[List[int]] = None  # List of relation_type IDs
    context: Optional[str] = None
    languages: Optional[List[str]] = None
    location: Optional[str] = None
    importance_rating: Optional[int] = Field(None, ge=1, le=5)
    dominant_themes: Optional[List[str]] = None


class ContactResponse(BaseModel):
    id: int
    user_id: int
    conversation_id: str
    first_name: Optional[str]
    nickname: Optional[str]
    gender: Optional[str]
    relation_types: Optional[List[RelationTypeResponse]] = None  # List of relation types
    context: Optional[str]
    languages: Optional[List[str]]
    location: Optional[str]
    importance_rating: Optional[int]
    dominant_themes: Optional[List[str]]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ContactDetectionResponse(BaseModel):
    """Response for contact detection (pre-filled data)"""
    first_name: Optional[str] = None
    nickname: Optional[str] = None
    gender: Optional[str] = None
    relation_type_ids: Optional[List[int]] = None  # Suggested relation_type IDs
    context: Optional[str] = None
    languages: Optional[List[str]] = None
    location: Optional[str] = None
    importance_rating: Optional[int] = None
    dominant_themes: Optional[List[str]] = None


# Ingestion Job Schemas
class IngestionJobResponse(BaseModel):
    id: int
    user_id: int
    conversation_id: Optional[str]
    status: str  # pending/running/completed/failed
    progress: Optional[Dict[str, Any]]
    error: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

