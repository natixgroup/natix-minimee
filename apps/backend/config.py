"""
Centralized configuration for Minimee backend
"""
from pydantic_settings import BaseSettings
from typing import Optional
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

