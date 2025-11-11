"""
SQLAlchemy models for Minimee
"""
from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, Text
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from datetime import datetime
from db.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=True)
    password_hash = Column(String, nullable=True)
    avatar_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    messages = relationship("Message", back_populates="user")
    agents = relationship("Agent", back_populates="user")
    gmail_threads = relationship("GmailThread", back_populates="user")
    oauth_tokens = relationship("OAuthToken", back_populates="user")
    settings = relationship("Setting", back_populates="user")
    policies = relationship("Policy", back_populates="user")
    whatsapp_integrations = relationship("WhatsAppIntegration", back_populates="user")
    contacts = relationship("Contact", back_populates="user")
    ingestion_jobs = relationship("IngestionJob", back_populates="user")
    user_infos = relationship("UserInfo", back_populates="user")
    contact_categories = relationship("ContactCategory", back_populates="user")
    conversation_sessions = relationship("ConversationSession", back_populates="user")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text, nullable=False)
    sender = Column(String, nullable=False)
    recipient = Column(String, nullable=True, index=True)  # For 1-1 conversations
    recipients = Column(JSONB, nullable=True)  # For group conversations (array of participants)
    timestamp = Column(DateTime, nullable=False, index=True)
    source = Column(String, nullable=False)  # 'whatsapp' or 'gmail'
    conversation_id = Column(String, nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="messages")
    embedding = relationship("Embedding", back_populates="message", uselist=False)


class Embedding(Base):
    __tablename__ = "embeddings"

    id = Column(Integer, primary_key=True, index=True)
    text = Column(Text, nullable=False)
    vector = Column(Vector(384), nullable=False)  # pgvector, dimension 384
    meta_data = Column("metadata", JSONB, nullable=True)  # Renamed to avoid SQLAlchemy reserved keyword
    message_id = Column(Integer, ForeignKey("messages.id"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    message = relationship("Message", back_populates="embedding")


class Summary(Base):
    __tablename__ = "summaries"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(String, nullable=False, index=True)
    summary_text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class Agent(Base):
    __tablename__ = "agents"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    role = Column(String, nullable=False)
    prompt = Column(Text, nullable=False)
    style = Column(Text, nullable=True)
    enabled = Column(Boolean, default=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    is_minimee_leader = Column(Boolean, default=False, nullable=False, index=True)
    whatsapp_integration_id = Column(Integer, ForeignKey("whatsapp_integrations.id"), nullable=True, index=True)
    whatsapp_display_name = Column(String, nullable=True)
    approval_rules = Column(JSONB, nullable=True)  # Rules for automatic approval decisions
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="agents")
    prompts = relationship("Prompt", back_populates="agent")
    whatsapp_integration = relationship("WhatsAppIntegration", foreign_keys=[whatsapp_integration_id])


class Prompt(Base):
    __tablename__ = "prompts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    agent = relationship("Agent", back_populates="prompts")


class Policy(Base):
    __tablename__ = "policy"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    rules = Column(JSONB, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="policies")


class Log(Base):
    __tablename__ = "logs"

    id = Column(Integer, primary_key=True, index=True)
    level = Column(String, nullable=False, index=True)  # 'DEBUG', 'INFO', 'WARNING', 'ERROR'
    message = Column(Text, nullable=False)
    meta_data = Column("metadata", JSONB, nullable=True)  # Renamed to avoid SQLAlchemy reserved keyword
    service = Column(String, nullable=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class GmailThread(Base):
    __tablename__ = "gmail_threads"

    id = Column(Integer, primary_key=True, index=True)
    thread_id = Column(String, unique=True, nullable=False, index=True)
    subject = Column(String, nullable=True)
    participants = Column(JSONB, nullable=True)  # Array of email addresses
    last_message_date = Column(DateTime, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="gmail_threads")


class OAuthToken(Base):
    __tablename__ = "oauth_tokens"

    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String, nullable=False, index=True)  # 'gmail', etc.
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="oauth_tokens")


class Setting(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, nullable=False, index=True)
    value = Column(JSONB, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)  # NULL for global settings
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="settings")


class ActionLog(Base):
    __tablename__ = "action_logs"

    id = Column(Integer, primary_key=True, index=True)
    action_type = Column(String, nullable=False, index=True)  # message_arrived, vectorization, semantic_search, etc.
    duration_ms = Column("duration_ms", sa.Float(), nullable=True)  # Temps en millisecondes
    model = Column(String, nullable=True)  # Modèle utilisé
    input_data = Column("input_data", JSONB, nullable=True)  # Données d'entrée
    output_data = Column("output_data", JSONB, nullable=True)  # Données de sortie
    meta_data = Column("metadata", JSONB, nullable=True)  # Renamed to avoid SQLAlchemy reserved keyword
    message_id = Column(Integer, ForeignKey("messages.id"), nullable=True, index=True)
    conversation_id = Column(String, nullable=True, index=True)
    request_id = Column(String, nullable=True, index=True)  # Pour tracer un flux complet
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    source = Column(String, nullable=True)  # 'whatsapp', 'gmail', etc.
    status = Column(String, nullable=True)  # 'success', 'error', 'pending'
    error_message = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    message = relationship("Message", backref="action_logs")
    user_rel = relationship("User", backref="action_logs")


class PendingApproval(Base):
    __tablename__ = "pending_approvals"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(Integer, ForeignKey("messages.id"), nullable=True, index=True)  # NULL for email drafts
    conversation_id = Column(String, nullable=True)
    sender = Column(String, nullable=False)
    source = Column(String, nullable=False)  # 'whatsapp' or 'gmail'
    recipient_jid = Column(String, nullable=True)  # For WhatsApp
    recipient_email = Column(String, nullable=True)  # For Gmail
    option_a = Column(Text, nullable=False)
    option_b = Column(Text, nullable=False)
    option_c = Column(Text, nullable=False)
    context_summary = Column(Text, nullable=True)
    original_content_preview = Column(Text, nullable=True)
    email_subject = Column(String, nullable=True)  # For Gmail emails
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    status = Column(String, nullable=False, default='pending')  # pending/approved/rejected/expired
    group_message_id = Column(String, nullable=True)  # WhatsApp message ID in group
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=True, index=True)
    reminder_sent_at = Column(DateTime, nullable=True)
    
    # Relationships
    message = relationship("Message", backref="pending_approvals")
    user = relationship("User", backref="pending_approvals")


class WhatsAppIntegration(Base):
    __tablename__ = "whatsapp_integrations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    integration_type = Column(String, nullable=False, index=True)  # 'user' or 'minimee'
    phone_number = Column(String, nullable=True)
    display_name = Column(String, nullable=True)
    status = Column(String, nullable=False, default='disconnected', index=True)  # connected/disconnected/pending
    auth_info_path = Column(String, nullable=True)  # Path to auth_info directory
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="whatsapp_integrations")
    
    # Unique constraint: one integration per type per user
    __table_args__ = (
        sa.UniqueConstraint('user_id', 'integration_type', name='uq_user_integration_type'),
    )


class RelationType(Base):
    __tablename__ = "relation_types"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, nullable=False, index=True)  # Unique code like 'epoux', 'client'
    label_masculin = Column(String, nullable=False)
    label_feminin = Column(String, nullable=False)
    label_autre = Column(String, nullable=True)  # For "autre" gender
    category = Column(String, nullable=False, index=True)  # 'personnel' or 'professionnel'
    display_order = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    meta_data = Column("metadata", JSONB, nullable=True)  # For icons, colors, descriptions (renamed to avoid SQLAlchemy reserved word)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    contacts = relationship("Contact", secondary="contact_relation_types", back_populates="relation_types")


class ContactRelationType(Base):
    __tablename__ = "contact_relation_types"

    contact_id = Column(Integer, ForeignKey("contacts.id", ondelete="CASCADE"), primary_key=True, index=True)
    relation_type_id = Column(Integer, ForeignKey("relation_types.id", ondelete="CASCADE"), primary_key=True, index=True)


class Contact(Base):
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    conversation_id = Column(String, nullable=False, index=True)
    first_name = Column(String, nullable=True)
    nickname = Column(String, nullable=True)
    gender = Column(String, nullable=True)  # masculin, féminin, autre
    # relation_type removed - now using many-to-many relation_types
    context = Column(Text, nullable=True)
    languages = Column(JSONB, nullable=True)  # Array of languages
    location = Column(String, nullable=True)
    importance_rating = Column(Integer, nullable=True)  # 1-5
    dominant_themes = Column(JSONB, nullable=True)  # Array of themes
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    contact_category_id = Column(Integer, ForeignKey("contact_categories.id", ondelete="SET NULL"), nullable=True, index=True)

    # Relationships
    user = relationship("User", back_populates="contacts")
    relation_types = relationship("RelationType", secondary="contact_relation_types", back_populates="contacts")
    category = relationship("ContactCategory", back_populates="contacts")
    
    # Unique constraint: one contact per conversation per user
    __table_args__ = (
        sa.UniqueConstraint('user_id', 'conversation_id', name='uq_user_conversation_contact'),
    )


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    conversation_id = Column(String, nullable=True, index=True)
    status = Column(String, nullable=False, default='pending', index=True)  # pending/running/completed/failed
    progress = Column(JSONB, nullable=True)  # Progress data
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="ingestion_jobs")


class UserInfo(Base):
    __tablename__ = "user_info"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    info_type = Column(String, nullable=False, index=True)  # first_name, last_name, birth_date, etc.
    info_value = Column(Text, nullable=True)  # For simple text values
    info_value_json = Column(JSONB, nullable=True)  # For complex values (arrays, objects like children)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="user_infos")
    visibilities = relationship("UserInfoVisibility", back_populates="user_info", cascade="all, delete-orphan")
    
    # Unique constraint: one info per type per user
    __table_args__ = (
        sa.UniqueConstraint('user_id', 'info_type', name='uq_user_info_user_type'),
    )


class UserInfoVisibility(Base):
    __tablename__ = "user_info_visibility"

    id = Column(Integer, primary_key=True, index=True)
    user_info_id = Column(Integer, ForeignKey("user_info.id", ondelete="CASCADE"), nullable=False, index=True)
    relation_type_id = Column(Integer, ForeignKey("relation_types.id", ondelete="CASCADE"), nullable=True, index=True)  # NULL = global rule
    contact_id = Column(Integer, ForeignKey("contacts.id", ondelete="CASCADE"), nullable=True, index=True)  # NULL = rule for category, not specific contact
    can_use_for_response = Column(Boolean, nullable=False, default=False)  # Utilisé pour répondre à
    can_say_explicitly = Column(Boolean, nullable=False, default=False)  # Dit explicitement à
    forbidden_for_response = Column(Boolean, nullable=False, default=False)  # Interdit pour répondre
    forbidden_to_say = Column(Boolean, nullable=False, default=False)  # Interdit de dire explicitement
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user_info = relationship("UserInfo", back_populates="visibilities")
    relation_type = relationship("RelationType", backref="user_info_visibilities")
    contact = relationship("Contact", backref="user_info_visibilities")
    
    # Unique constraint: one visibility rule per user_info + relation_type/contact combination
    __table_args__ = (
        sa.UniqueConstraint('user_info_id', 'relation_type_id', 'contact_id', name='uq_user_info_visibility_composite'),
    )


class ContactCategory(Base):
    __tablename__ = "contact_categories"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, nullable=False, index=True)  # Unique code like 'famille', 'amis'
    label = Column(String, nullable=False)
    category_type = Column(String, nullable=False, index=True)  # 'personnel', 'professionnel', 'autre'
    is_system = Column(Boolean, nullable=False, default=False, index=True)  # System categories vs user-created
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)  # NULL for system categories
    display_order = Column(Integer, nullable=False, default=0)
    meta_data = Column("metadata", JSONB, nullable=True)  # For icons, colors, descriptions (renamed to avoid SQLAlchemy reserved word)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="contact_categories")
    contacts = relationship("Contact", back_populates="category")
    
    # Unique constraint: code must be unique per user (or globally for system categories)
    __table_args__ = (
        sa.UniqueConstraint('code', 'user_id', name='uq_contact_categories_code_user'),
    )


class ConversationSession(Base):
    __tablename__ = "conversation_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    session_type = Column(String, nullable=False, index=True)  # 'normal', 'getting_to_know'
    title = Column(String, nullable=True)  # User-defined or auto-generated title
    conversation_id = Column(String, nullable=False, index=True)  # Links to messages.conversation_id
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    deleted_at = Column(DateTime, nullable=True, index=True)  # Soft delete

    # Relationships
    user = relationship("User", back_populates="conversation_sessions")

