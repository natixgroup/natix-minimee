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
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    messages = relationship("Message", back_populates="user")
    agents = relationship("Agent", back_populates="user")
    gmail_threads = relationship("GmailThread", back_populates="user")
    oauth_tokens = relationship("OAuthToken", back_populates="user")
    settings = relationship("Setting", back_populates="user")
    policies = relationship("Policy", back_populates="user")


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
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="agents")
    prompts = relationship("Prompt", back_populates="agent")


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

