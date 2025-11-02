"""
LLM Status Router
Checks LLM provider status and model availability
"""
import httpx
from fastapi import APIRouter, HTTPException
from config import settings
from typing import Optional

router = APIRouter(prefix="/llm", tags=["llm"])


async def check_ollama_model(model_name: str = "llama3.2:1b") -> dict:
    """Check if Ollama model is available"""
    base_url = settings.ollama_base_url
    model = model_name or "llama3.2:1b"
    
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
        # Get model name from settings or default to smaller model
        model_name = getattr(settings, "ollama_model", "llama3.2:1b") or "llama3.2:1b"
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


async def get_ollama_models() -> list:
    """Get all available Ollama models with details"""
    base_url = settings.ollama_base_url
    models = []
    
    try:
        # Use shorter timeout: 2s connect, 1.5s read - faster failure if Ollama is slow/unavailable
        timeout = httpx.Timeout(connect=2.0, read=1.5, write=2.0, pool=2.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(f"{base_url}/api/tags")
            response.raise_for_status()
            models_data = response.json()
            
            # Model parameter mappings (known models)
            param_mapping = {
                "llama3.2:1b": "1B",
                "llama3.2:3b": "3B",
                "llama3:8b": "8B",
                "llama3:70b": "70B",
                "mistral:7b": "7B",
                "mixtral:8x7b": "47B",
                "codellama:7b": "7B",
                "codellama:13b": "13B",
                "codellama:34b": "34B",
            }
            
            for model_info in models_data.get("models", []):
                model_name = model_info.get("name", "")
                size_bytes = model_info.get("size", 0)
                size_gb = size_bytes / (1024 ** 3)
                size_str = f"{size_gb:.2f} GB" if size_gb >= 1 else f"{size_bytes / (1024 ** 2):.2f} MB"
                
                # Try to extract parameters from model name
                parameters = "Unknown"
                for key, value in param_mapping.items():
                    if key in model_name.lower():
                        parameters = value
                        break
                
                modified = model_info.get("modified_at")
                if modified:
                    from datetime import datetime
                    try:
                        dt = datetime.fromisoformat(modified.replace('Z', '+00:00'))
                        modified = dt.strftime("%Y-%m-%d %H:%M")
                    except:
                        pass
                
                models.append({
                    "provider": "ollama",
                    "model": model_name,
                    "parameters": parameters,
                    "size": size_str,
                    "modified": modified or "Unknown",
                    "available": True,
                    "location_type": "local",
                    "cost": "free",
                })
            
            return models
    except httpx.TimeoutException:
        return [{
            "provider": "ollama",
            "error": "Ollama service timeout",
            "available": False,
            "location_type": "local",
            "cost": "free",
        }]
    except httpx.ConnectError:
        return [{
            "provider": "ollama",
            "error": "Cannot connect to Ollama service",
            "available": False,
            "location_type": "local",
            "cost": "free",
        }]
    except Exception as e:
        return [{
            "provider": "ollama",
            "error": f"Error checking Ollama: {str(e)}",
            "available": False,
            "location_type": "local",
            "cost": "free",
        }]


@router.get("/models")
async def get_all_models():
    """
    Get all available LLM models across all providers with their details
    Returns static models immediately, Ollama models are fetched asynchronously with short timeout
    """
    all_models = []
    
    # Return static models first (OpenAI and vLLM) for immediate response
    # OpenAI models (static list)
    openai_models = [
        {
            "provider": "openai",
            "model": "gpt-4o",
            "parameters": "Unknown",
            "context_length": "128K tokens",
            "available": True,
            "description": "OpenAI's most advanced model",
            "location_type": "cloud",
            "cost": "paid",
            "cost_info": "Pay per token"
        },
        {
            "provider": "openai",
            "model": "gpt-4-turbo",
            "parameters": "Unknown",
            "context_length": "128K tokens",
            "available": True,
            "description": "High-performance GPT-4 variant",
            "location_type": "cloud",
            "cost": "paid",
            "cost_info": "Pay per token"
        },
        {
            "provider": "openai",
            "model": "gpt-3.5-turbo",
            "parameters": "Unknown",
            "context_length": "16K tokens",
            "available": True,
            "description": "Fast and efficient model",
            "location_type": "cloud",
            "cost": "paid",
            "cost_info": "Pay per token (lower cost)"
        },
    ]
    all_models.extend(openai_models)
    
    # vLLM models (static list)
    vllm_models = [
        {
            "provider": "vllm",
            "model": "Llama-2-70B",
            "parameters": "70B",
            "context_length": "4K tokens",
            "available": True,
            "description": "High-performance 70B parameter model",
            "location_type": "local",
            "cost": "free"
        },
        {
            "provider": "vllm",
            "model": "Mixtral-8x7B",
            "parameters": "47B",
            "context_length": "32K tokens",
            "available": True,
            "description": "Mixture of Experts model",
            "location_type": "local",
            "cost": "free"
        },
    ]
    all_models.extend(vllm_models)
    
    # Add Ollama models (with short timeout to avoid blocking)
    # If Ollama is slow/unavailable, we still return the static models immediately
    try:
        ollama_models = await get_ollama_models()
        all_models.extend(ollama_models)
    except Exception:
        # If Ollama fails, add an error entry but don't block the response
        all_models.append({
            "provider": "ollama",
            "model": "Unknown",
            "error": "Ollama service unavailable or slow",
            "available": False,
            "location_type": "local",
            "cost": "free",
        })
    
    return {"models": all_models}

