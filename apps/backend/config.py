"""
Centralized configuration for Minimee backend
"""
from pydantic_settings import BaseSettings
from typing import Optional, Dict
from db.database import SessionLocal


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql://minimee:minimee@localhost:5432/minimee"
    
    # LLM Providers
    llm_provider: str = "ollama"  # ollama, vllm, openai
    ollama_base_url: str = "http://host.docker.internal:11434"  # Ollama sur l'hôte macOS
    ollama_model: str = "llama3.2:1b"  # Default Ollama model
    vllm_base_url: str = "http://vllm:8000"
    openai_api_key: Optional[str] = None
    
    # Embeddings
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimension: int = 384
    
    # RAG Reranking Configuration
    # Reranking improves retrieval quality by re-evaluating relevance using a cross-encoder model
    # Cross-encoder compares query + document directly (more accurate than vector similarity alone)
    # Process: Retrieve top 20 → Rerank → Return top 10 (configurable)
    rag_rerank_enabled: bool = True  # Enable/disable reranking
    rag_rerank_top_k: int = 20  # Number of results to rerank (before keeping top limit)
    rag_rerank_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"  # Cross-encoder model for reranking
    
    # RAG Context Management Configuration
    # Context window mapping: provider -> model -> context_window_size (in tokens)
    rag_context_window_map: Dict[str, Dict[str, int]] = {
        "openai": {
            "gpt-4o-mini": 128000,
            "gpt-4o": 128000,
            "gpt-4": 8192,
            "gpt-3.5-turbo": 16384,
        },
        "ollama": {
            "llama3.2:1b": 8192,
            "llama3.2:3b": 8192,
            "llama3.1:8b": 131072,
            "mistral": 32768,
            "deepseek-r1:1.5b": 16384,
            "gemma2:2b": 8192,
        },
        "vllm": {
            "mistral-7b-instruct-v0.1": 32768,
        }
    }
    rag_compression_enabled: bool = True  # Enable/disable context compression
    rag_token_buffer: int = 500  # Safety buffer for system prompt and response generation
    rag_recent_messages_keep: int = 5  # Number of recent messages to keep complete (not compressed)
    
    # Gmail OAuth
    gmail_client_id: Optional[str] = None
    gmail_client_secret: Optional[str] = None
    gmail_redirect_uri: str = "http://localhost:3002/auth/gmail/callback"
    
    # API Settings
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    
    # Bridge Settings
    bridge_api_url: str = "http://localhost:3003"
    approval_reminder_minutes: int = 10
    approval_expiration_minutes: int = 60
    
    class Config:
        env_file = ".env"
        case_sensitive = False

    def get_openai_api_key(self) -> Optional[str]:
        """
        Get OpenAI API key from database settings first, then fallback to env var
        This allows runtime configuration via the UI
        """
        # Try database first
        try:
            db: Session = SessionLocal()
            try:
                from models import Setting
                setting = db.query(Setting).filter(
                    Setting.key == "openai_api_key",
                    Setting.user_id == None
                ).first()
                
                if setting and isinstance(setting.value, dict):
                    api_key = setting.value.get("api_key")
                    if api_key:
                        return api_key
            except Exception:
                # Database not ready or table doesn't exist yet
                pass
            finally:
                db.close()
        except Exception:
            # Database connection failed, fallback to env
            pass
        
        # Fallback to environment variable
        return self.openai_api_key


settings = Settings()

