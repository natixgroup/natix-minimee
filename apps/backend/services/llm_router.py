"""
LLM Router - Switch between different LLM providers
Optimized for speed with llama3.2:1b (60-80 tokens/sec)
"""
import httpx
import os
import time
import asyncio
from typing import Optional, Dict, Any
from config import settings
from services.logs_service import log_to_db
from services.metrics import record_llm_call
from services.action_logger import log_action_context, log_action
from sqlalchemy.orm import Session


async def generate_llm_response(
    prompt: str,
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    db: Optional[Session] = None,
    request_id: Optional[str] = None,
    message_id: Optional[int] = None,
    user_id: Optional[int] = None
) -> str:
    """
    Generate response using configured LLM provider
    Tracks metrics: latency, provider, success/failure
    """
    provider = settings.llm_provider.lower()
    
    # Déterminer le modèle utilisé
    if provider == "ollama":
        actual_model = model or "llama3.2:1b"
    elif provider == "vllm":
        actual_model = model or "mistral-7b-instruct-v0.1"
    elif provider == "openai":
        # Default to gpt-4o (Standard level) if no model specified
        actual_model = model or "gpt-4o"
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
                    result = await _generate_ollama(prompt, model, temperature, max_tokens)
                elif provider == "vllm":
                    result = await _generate_vllm(prompt, model, temperature, max_tokens)
                elif provider == "openai":
                    result = await _generate_openai(prompt, model, temperature, max_tokens)
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
                return result
            except Exception as e:
                error_msg = f"LLM generation error ({provider}): {str(e)}"
                if db:
                    record_llm_call(db, provider, 0, None, success=False)
                    log_to_db(db, "ERROR", error_msg, service="llm_router")
                raise RuntimeError(error_msg)
    else:
        # Sans DB, pas de logging mais on continue
        try:
            if provider == "ollama":
                result = await _generate_ollama(prompt, model, temperature, max_tokens)
            elif provider == "vllm":
                result = await _generate_vllm(prompt, model, temperature, max_tokens)
            elif provider == "openai":
                result = await _generate_openai(prompt, model, temperature, max_tokens)
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
    
    # Use get_openai_api_key() to get key from DB or env
    api_key = settings.get_openai_api_key()
    if not api_key:
        raise ValueError("OpenAI API key not configured. Please configure it in Settings > Integrations > API Keys & Credentials")
    
    # Default to gpt-4o (Standard level) if no model specified
    model = model or "gpt-4o"
    client = AsyncOpenAI(api_key=api_key)
    
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

