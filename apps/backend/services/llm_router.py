"""
LLM Router - Switch between different LLM providers
Optimized for speed with llama3.2:1b (60-80 tokens/sec)
"""
import httpx
import os
import time
import asyncio
import json
from typing import Optional, Dict, Any, Callable
from config import settings
from services.logs_service import log_to_db
from services.metrics import record_llm_call
from services.action_logger import log_action_context, log_action
from sqlalchemy.orm import Session


def get_llm_provider_from_db(db: Optional[Session] = None) -> tuple[str, Optional[str]]:
    """
    Get LLM provider and model from database settings, fallback to config
    Returns: (provider, model_name)
    """
    if db:
        try:
            from models import Setting
            llm_setting = db.query(Setting).filter(
                Setting.key == "llm_provider",
                Setting.user_id == None
            ).first()
            
            if llm_setting and isinstance(llm_setting.value, dict):
                provider = llm_setting.value.get("provider", settings.llm_provider).lower()
                model_name = llm_setting.value.get("model")
                return provider, model_name
        except Exception:
            pass  # Fallback to config
    
    # Fallback to config
    provider = settings.llm_provider.lower()
    model_name = None
    
    # Get default model from config
    if provider == "ollama":
        model_name = settings.ollama_model
    elif provider == "vllm":
        model_name = getattr(settings, "vllm_model", None)
    elif provider == "openai":
        model_name = getattr(settings, "openai_model", "gpt-4o")
    
    return provider, model_name


async def generate_llm_response(
    prompt: str,
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    db: Optional[Session] = None,
    request_id: Optional[str] = None,
    message_id: Optional[int] = None,
    user_id: Optional[int] = None,
    llm_log_callback: Optional[Callable[[Dict[str, Any]], None]] = None
) -> str:
    """
    Generate response using configured LLM provider
    Tracks metrics: latency, provider, success/failure
    Reads provider and model from DB settings if available
    
    Args:
        llm_log_callback: Optional callback for real-time LLM logging (receives dict with request/response)
    """
    import time
    from datetime import datetime
    
    # Get provider from DB settings if available
    provider, default_model_from_db = get_llm_provider_from_db(db)
    
    # Log LLM request via callback if provided
    if llm_log_callback:
        request_data = {
            "type": "llm_call",
            "request": prompt[:500] if len(prompt) > 500 else prompt,  # Truncate for display
            "timestamp": datetime.utcnow().isoformat(),
            "provider": provider,
            "model": model or default_model_from_db,
            "user_id": user_id
        }
        try:
            llm_log_callback(request_data)
        except Exception as e:
            # Don't fail if callback fails
            if db:
                log_to_db(db, "WARNING", f"LLM log callback failed: {str(e)}", service="llm_router")
    
    # Déterminer le modèle utilisé (paramètre > DB > config > default)
    if provider == "ollama":
        actual_model = model or default_model_from_db or settings.ollama_model or "llama3.2:1b"
    elif provider == "vllm":
        actual_model = model or default_model_from_db or "mistral-7b-instruct-v0.1"
    elif provider == "openai":
        actual_model = model or default_model_from_db or "gpt-4o"
    else:
        actual_model = model or "unknown"
    
    if db:
        with log_action_context(
            db=db,
            action_type="llm_call",
            model=f"{provider}:{actual_model}",
            input_data={
                "prompt": prompt[:500],  # Limiter la taille
                "prompt_length": len(prompt),
                "temperature": temperature,
                "max_tokens": max_tokens,
                "provider": provider
            },
            message_id=message_id,
            request_id=request_id,
            user_id=user_id,
            metadata={"llm_provider": provider}
        ) as log:
            try:
                if provider == "ollama":
                    result = await _generate_ollama(prompt, actual_model, temperature, max_tokens)
                elif provider == "vllm":
                    result = await _generate_vllm(prompt, actual_model, temperature, max_tokens)
                elif provider == "openai":
                    result = await _generate_openai(prompt, actual_model, temperature, max_tokens)
                else:
                    raise ValueError(f"Unknown LLM provider: {provider}")
                
                # Record successful call
                if db:
                    record_llm_call(db, provider, 0, len(result), success=True)  # Duration déjà mesuré
                
                log.set_output({
                    "response": result[:500],  # Limiter la taille
                    "response_length": len(result),
                    "provider": provider,
                    "model": actual_model
                })
                
                # Log LLM response via callback if provided
                if llm_log_callback:
                    response_data = {
                        "type": "llm_call",
                        "request": prompt[:500] if len(prompt) > 500 else prompt,
                        "response": result[:500] if len(result) > 500 else result,  # Truncate for display
                        "timestamp": datetime.utcnow().isoformat(),
                        "provider": provider,
                        "model": actual_model,
                        "user_id": user_id
                    }
                    try:
                        llm_log_callback(response_data)
                    except Exception as e:
                        # Don't fail if callback fails
                        if db:
                            log_to_db(db, "WARNING", f"LLM log callback failed: {str(e)}", service="llm_router")
                
                return result
            except Exception as e:
                error_msg = f"LLM generation error ({provider}): {str(e)}"
                if db:
                    record_llm_call(db, provider, 0, None, success=False)
                    log_to_db(db, "ERROR", error_msg, service="llm_router")
                
                # Log LLM error via callback if provided
                if llm_log_callback:
                    error_data = {
                        "type": "llm_error",
                        "request": prompt[:500] if len(prompt) > 500 else prompt,
                        "error": str(e),
                        "timestamp": datetime.utcnow().isoformat(),
                        "provider": provider,
                        "model": actual_model,
                        "user_id": user_id
                    }
                    try:
                        llm_log_callback(error_data)
                    except Exception:
                        pass  # Ignore callback errors
                
                raise RuntimeError(error_msg)
    else:
        # Sans DB, pas de logging mais on continue
        try:
            if provider == "ollama":
                result = await _generate_ollama(prompt, actual_model, temperature, max_tokens)
            elif provider == "vllm":
                result = await _generate_vllm(prompt, actual_model, temperature, max_tokens)
            elif provider == "openai":
                result = await _generate_openai(prompt, actual_model, temperature, max_tokens)
            else:
                raise ValueError(f"Unknown LLM provider: {provider}")
            return result
        except Exception as e:
            raise RuntimeError(f"LLM generation error ({provider}): {str(e)}")


# Reusable HTTP client for Ollama (avoids connection overhead)
_ollama_client: Optional[httpx.AsyncClient] = None

async def _get_ollama_client() -> httpx.AsyncClient:
    """Get or create reusable Ollama HTTP client"""
    global _ollama_client
    if _ollama_client is None:
        # 90s timeout: Ollama prend 14-57s par génération sur ce système Docker
        # Avec 3 appels en parallèle, certains peuvent prendre jusqu'à 60s
        _ollama_client = httpx.AsyncClient(timeout=90.0)
    return _ollama_client

async def _generate_ollama(
    prompt: str,
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None
) -> str:
    """Generate using Ollama with optimized settings for llama3.2:1b"""
    model = model or "llama3.2:1b"  # Use smaller model by default to avoid memory issues
    base_url = settings.ollama_base_url
    
    # Use reduced tokens for WhatsApp (50 tokens = ~40 words)
    # Timeout 10s is plenty for llama3.2:1b at 60-80 tokens/sec
    client = await _get_ollama_client()
    response = await client.post(
        f"{base_url}/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens or 50  # Reduced from 150 to 50 for speed
            }
        }
    )
    response.raise_for_status()
    data = response.json()
    result = data.get("response", "")
    if not result:
        raise ValueError(f"Empty response from Ollama. Status: {response.status_code}, Data: {data}")
    return result


async def _generate_vllm(
    prompt: str,
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None
) -> str:
    """Generate using vLLM"""
    model = model or "mistral-7b-instruct-v0.1"
    base_url = settings.vllm_base_url
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{base_url}/v1/completions",
            json={
                "model": model,
                "prompt": prompt,
                "temperature": temperature,
                "max_tokens": max_tokens or 512
            }
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["text"].strip()


async def _generate_openai(
    prompt: str,
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None
) -> str:
    """Generate using OpenAI"""
    from openai import AsyncOpenAI
    import os
    
    # Use get_openai_api_key() to get key from DB or env
    api_key = settings.get_openai_api_key()
    if not api_key:
        raise ValueError("OpenAI API key not configured. Please configure it in Settings > Integrations > API Keys & Credentials")
    
    # Default to gpt-4o (Standard level) if no model specified
    model = model or "gpt-4o"
    
    # Create client with custom http_client to avoid proxies parameter issues
    # OpenAI SDK 2.x may try to pass 'proxies' to httpx.AsyncClient which doesn't support it
    import httpx
    http_client = httpx.AsyncClient(
        timeout=60.0,
        # Explicitly don't configure proxy to avoid version conflicts
    )
    client = AsyncOpenAI(
        api_key=api_key,
        http_client=http_client
    )
    
    response = await client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=max_tokens
    )
    
    return response.choices[0].message.content


async def generate_multiple_options(
    prompt: str,
    num_options: int = 3,
    db: Optional[Session] = None,
    request_id: Optional[str] = None,
    message_id: Optional[int] = None,
    user_id: Optional[int] = None
) -> list[str]:
    """
    Generate multiple response options in PARALLEL for speed
    Uses asyncio.gather() to generate all options simultaneously
    """
    # Create tasks for parallel execution
    tasks = []
    for i in range(num_options):
        # Slight temperature variation for diversity
        temperature = 0.7 + (i * 0.1)
        task = generate_llm_response(
            prompt,
            temperature=temperature,
            max_tokens=50,  # Explicitly limit to 50 tokens for WhatsApp
            db=db,
            request_id=request_id,
            message_id=message_id,
            user_id=user_id
        )
        tasks.append(task)
    
    # Generate all options in parallel → 3x faster!
    options = await asyncio.gather(*tasks)
    return list(options)


async def generate_llm_response_stream(
    prompt: str,
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    db: Optional[Session] = None,
    request_id: Optional[str] = None,
    message_id: Optional[int] = None,
    user_id: Optional[int] = None
):
    """
    Generate response using configured LLM provider with streaming
    Yields tokens one by one as they are generated
    Yields {"token": "...", "done": false} for each token
    Finally yields {"done": true, "response": "...", "actions": [...]} when complete
    Reads provider and model from DB settings if available
    """
    # Get provider from DB settings if available
    provider, default_model_from_db = get_llm_provider_from_db(db)
    
    # Déterminer le modèle utilisé (paramètre > DB > config > default)
    if provider == "ollama":
        actual_model = model or default_model_from_db or settings.ollama_model or "llama3.2:1b"
    elif provider == "vllm":
        actual_model = model or default_model_from_db or "mistral-7b-instruct-v0.1"
    elif provider == "openai":
        actual_model = model or default_model_from_db or "gpt-4o"
    else:
        actual_model = model or "unknown"
    
    try:
        if provider == "ollama":
            async for token_data in _generate_ollama_stream(prompt, actual_model, temperature, max_tokens):
                yield token_data
        elif provider == "vllm":
            # vLLM uses Ollama-compatible API
            async for token_data in _generate_vllm_stream(prompt, actual_model, temperature, max_tokens):
                yield token_data
        elif provider == "openai":
            async for token_data in _generate_openai_stream(prompt, actual_model, temperature, max_tokens):
                yield token_data
        else:
            raise ValueError(f"Unknown LLM provider: {provider}")
    except Exception as e:
        error_msg = f"LLM streaming error ({provider}): {str(e)}"
        if db:
            log_to_db(db, "ERROR", error_msg, service="llm_router")
        yield {"error": error_msg, "done": True}
        raise RuntimeError(error_msg)


async def _generate_ollama_stream(
    prompt: str,
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None
):
    """Generate using Ollama with streaming"""
    # Model should be provided by caller (from DB settings), but fallback for safety
    model = model or settings.ollama_model or "llama3.2:1b"
    base_url = settings.ollama_base_url
    
    client = await _get_ollama_client()
    
    async with client.stream(
        "POST",
        f"{base_url}/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens or 512
            }
        }
    ) as response:
        response.raise_for_status()
        full_response = ""
        
        async for line in response.aiter_lines():
            if not line:
                continue
            
            try:
                data = json.loads(line)  # Ollama returns JSON lines
                if "response" in data:
                    token = data["response"]
                    full_response += token
                    yield {"token": token, "done": False}
                
                if data.get("done", False):
                    yield {"done": True, "response": full_response, "actions": []}
                    break
            except json.JSONDecodeError:
                # Skip malformed lines
                continue


async def _generate_vllm_stream(
    prompt: str,
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None
):
    """Generate using vLLM with streaming (Ollama-compatible API)"""
    # Model should be provided by caller, but fallback for safety
    model = model or getattr(settings, "vllm_model", None) or "mistral-7b-instruct-v0.1"
    base_url = settings.vllm_base_url
    
    # vLLM uses Ollama-compatible API, so same logic
    async with httpx.AsyncClient(timeout=90.0) as client:
        async with client.stream(
            "POST",
            f"{base_url}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": True,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens or 512
                }
            }
        ) as response:
            response.raise_for_status()
            full_response = ""
            
            async for line in response.aiter_lines():
                if not line:
                    continue
                
                try:
                    data = json.loads(line)  # Ollama-compatible JSON lines
                    if "response" in data:
                        token = data["response"]
                        full_response += token
                        yield {"token": token, "done": False}
                    
                    if data.get("done", False):
                        yield {"done": True, "response": full_response, "actions": []}
                        break
                except json.JSONDecodeError:
                    # Skip malformed lines
                    continue


async def _generate_openai_stream(
    prompt: str,
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None
):
    """Generate using OpenAI with streaming"""
    from openai import AsyncOpenAI
    import os
    
    api_key = settings.get_openai_api_key()
    if not api_key:
        raise ValueError("OpenAI API key not configured. Please configure it in Settings > Integrations > API Keys & Credentials")
    
    model = model or "gpt-4o"
    
    # Create client with custom http_client to avoid proxies parameter issues
    import httpx
    http_client = httpx.AsyncClient(
        timeout=60.0,
        # Explicitly don't configure proxy to avoid version conflicts
    )
    client = AsyncOpenAI(
        api_key=api_key,
        http_client=http_client
    )
    
    full_response = ""
    
    stream = await client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True
    )
    
    async for chunk in stream:
        if chunk.choices[0].delta.content:
            token = chunk.choices[0].delta.content
            full_response += token
            yield {"token": token, "done": False}
    
    yield {"done": True, "response": full_response, "actions": []}

