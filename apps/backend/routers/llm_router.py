"""
LLM Status Router
Checks LLM provider status and model availability
"""
import httpx
from fastapi import APIRouter, HTTPException
from config import settings
from typing import Optional

router = APIRouter(prefix="/llm", tags=["llm"])


async def check_ollama_model(model_name: str = "llama2") -> dict:
    """Check if Ollama model is available"""
    base_url = settings.ollama_base_url
    model = model_name or "llama2"
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Check if model exists
            response = await client.get(f"{base_url}/api/tags")
            response.raise_for_status()
            models_data = response.json()
            
            # Find the requested model
            for model_info in models_data.get("models", []):
                if model_info.get("name", "").startswith(model):
                    size_bytes = model_info.get("size", 0)
                    size_gb = size_bytes / (1024 ** 3)
                    size_str = f"{size_gb:.2f} GB" if size_gb >= 1 else f"{size_bytes / (1024 ** 2):.2f} MB"
                    
                    modified = model_info.get("modified_at")
                    if modified:
                        from datetime import datetime
                        try:
                            dt = datetime.fromisoformat(modified.replace('Z', '+00:00'))
                            modified = dt.strftime("%Y-%m-%d %H:%M")
                        except:
                            pass
                    
                    return {
                        "available": True,
                        "provider": "ollama",
                        "model": model_info.get("name"),
                        "size": size_str,
                        "modified": modified or "Unknown",
                    }
            
            return {
                "available": False,
                "provider": "ollama",
                "error": f"Model '{model}' not found. Available models: {', '.join([m.get('name', 'unknown') for m in models_data.get('models', [])])}",
            }
    except httpx.TimeoutException:
        return {
            "available": False,
            "provider": "ollama",
            "error": "Ollama service timeout - check if Ollama is running",
        }
    except httpx.ConnectError:
        return {
            "available": False,
            "provider": "ollama",
            "error": "Cannot connect to Ollama service - check if Ollama is running",
        }
    except Exception as e:
        return {
            "available": False,
            "provider": "ollama",
            "error": f"Error checking Ollama: {str(e)}",
        }


@router.get("/status")
async def get_llm_status():
    """
    Get LLM provider status and model availability
    """
    provider = settings.llm_provider.lower()
    
    if provider == "ollama":
        # Get model name from settings or default
        model_name = getattr(settings, "ollama_model", "llama2") or "llama2"
        return await check_ollama_model(model_name)
    elif provider == "openai":
        return {
            "available": True,
            "provider": "openai",
            "model": getattr(settings, "openai_model", "gpt-3.5-turbo"),
        }
    elif provider == "vllm":
        return {
            "available": True,
            "provider": "vllm",
            "model": getattr(settings, "vllm_model", "unknown"),
        }
    else:
        return {
            "available": False,
            "provider": provider,
            "error": f"Unknown provider: {provider}",
        }

