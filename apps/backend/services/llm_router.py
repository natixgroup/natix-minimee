"""
LLM Router - Switch between different LLM providers
"""
import httpx
import os
from typing import Optional, Dict, Any
from config import settings
from services.logs_service import log_to_db
from sqlalchemy.orm import Session


async def generate_llm_response(
    prompt: str,
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    db: Optional[Session] = None
) -> str:
    """
    Generate response using configured LLM provider
    """
    provider = settings.llm_provider.lower()
    
    try:
        if provider == "ollama":
            return await _generate_ollama(prompt, model, temperature, max_tokens)
        elif provider == "vllm":
            return await _generate_vllm(prompt, model, temperature, max_tokens)
        elif provider == "openai":
            return await _generate_openai(prompt, model, temperature, max_tokens)
        else:
            raise ValueError(f"Unknown LLM provider: {provider}")
    except Exception as e:
        error_msg = f"LLM generation error ({provider}): {str(e)}"
        if db:
            log_to_db(db, "ERROR", error_msg, service="llm_router")
        raise RuntimeError(error_msg)


async def _generate_ollama(
    prompt: str,
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None
) -> str:
    """Generate using Ollama"""
    model = model or "llama2"
    base_url = settings.ollama_base_url
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{base_url}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens
                }
            }
        )
        response.raise_for_status()
        data = response.json()
        return data.get("response", "")


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
    
    if not settings.openai_api_key:
        raise ValueError("OpenAI API key not configured")
    
    model = model or "gpt-4o"
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    
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
    db: Optional[Session] = None
) -> list[str]:
    """
    Generate multiple response options with slight variations
    """
    options = []
    for i in range(num_options):
        # Slight temperature variation for diversity
        temperature = 0.7 + (i * 0.1)
        option = await generate_llm_response(
            prompt,
            temperature=temperature,
            db=db
        )
        options.append(option)
    return options

