"""
Centralized configuration for Minimee backend
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql://minimee:minimee@localhost:5432/minimee"
    
    # LLM Providers
    llm_provider: str = "ollama"  # ollama, vllm, openai
    ollama_base_url: str = "http://ollama:11434"
    vllm_base_url: str = "http://vllm:8000"
    openai_api_key: Optional[str] = None
    
    # Embeddings
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimension: int = 384
    
    # Gmail OAuth
    gmail_client_id: Optional[str] = None
    gmail_client_secret: Optional[str] = None
    gmail_redirect_uri: str = "http://localhost:3002/auth/gmail/callback"
    
    # API Settings
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()

