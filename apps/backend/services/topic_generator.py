"""
Topic generator service
Generates latent topics for conversational blocks using LLM
Logs LLM calls in real-time via WebSocket
"""
from typing import Optional, Callable, Dict, Any
from sqlalchemy.orm import Session
from services.llm_router import generate_llm_response
from services.logs_service import log_to_db
import asyncio
import json
from datetime import datetime


async def generate_latent_topic(
    block_text: str,
    db: Session,
    user_id: int,
    job_id: Optional[int] = None,
    llm_log_callback: Optional[Callable[[Dict[str, Any]], None]] = None
) -> str:
    """
    Generate a latent topic for a conversational block using LLM
    
    Args:
        block_text: Text content of the conversational block
        db: Database session
        user_id: User ID
        job_id: Optional ingestion job ID for WebSocket logging
        llm_log_callback: Optional callback for real-time LLM logging
    
    Returns:
        Topic string (1-2 words, e.g., "travail", "famille", "couple", "santé")
    """
    # Truncate block text if too long (keep first 500 chars for topic generation)
    truncated_text = block_text[:500] if len(block_text) > 500 else block_text
    
    prompt = f"""Analyse ce bloc de conversation WhatsApp et donne un seul mot-clé latent qui décrit le thème principal.

Thèmes possibles : travail, famille, couple, santé, quotidien, projet personnel, affection, fatigue, etc.

Bloc de conversation :
{truncated_text}

Réponds UNIQUEMENT avec le mot-clé (1-2 mots maximum), sans explication."""

    try:
        # Log LLM request
        request_data = {
            "type": "llm_call",
            "request": prompt,
            "timestamp": datetime.utcnow().isoformat(),
            "job_id": job_id,
            "user_id": user_id
        }
        
        if llm_log_callback:
            llm_log_callback(request_data)
        
        log_to_db(db, "DEBUG", f"Generating latent topic for block (length: {len(block_text)} chars)", 
                 service="topic_generator", user_id=user_id, metadata={"job_id": job_id})
        
        # Generate topic using LLM
        start_time = datetime.utcnow()
        topic = await generate_llm_response(
            prompt=prompt,
            model=None,  # Use default from DB/config
            temperature=0.3,  # Lower temperature for more consistent topics
            max_tokens=10,  # Very short response
            db=db,
            user_id=user_id
        )
        end_time = datetime.utcnow()
        duration_ms = (end_time - start_time).total_seconds() * 1000
        
        # Clean topic (remove extra whitespace, quotes, etc.)
        topic = topic.strip().strip('"').strip("'").strip()
        # Take only first 2 words
        topic_words = topic.split()[:2]
        topic = " ".join(topic_words)
        
        # Log LLM response
        response_data = {
            "type": "llm_call",
            "request": prompt,
            "response": topic,
            "timestamp": datetime.utcnow().isoformat(),
            "duration_ms": round(duration_ms, 2),
            "job_id": job_id,
            "user_id": user_id
        }
        
        if llm_log_callback:
            llm_log_callback(response_data)
        
        log_to_db(db, "INFO", f"Generated latent topic: {topic} (duration: {duration_ms:.0f}ms)", 
                 service="topic_generator", user_id=user_id, metadata={"job_id": job_id, "topic": topic})
        
        return topic
        
    except Exception as e:
        error_msg = f"Error generating latent topic: {str(e)}"
        log_to_db(db, "ERROR", error_msg, service="topic_generator", user_id=user_id, metadata={"job_id": job_id})
        
        # Log error via callback
        if llm_log_callback:
            error_data = {
                "type": "llm_error",
                "request": prompt,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
                "job_id": job_id,
                "user_id": user_id
            }
            llm_log_callback(error_data)
        
        # Fallback: return generic topic
        return "conversation"


def generate_latent_topic_sync(
    block_text: str,
    db: Session,
    user_id: int,
    job_id: Optional[int] = None,
    llm_log_callback: Optional[Callable[[Dict[str, Any]], None]] = None
) -> str:
    """
    Synchronous wrapper for generate_latent_topic
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If loop is running, create new event loop in thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    generate_latent_topic(block_text, db, user_id, job_id, llm_log_callback)
                )
                return future.result()
        else:
            return loop.run_until_complete(
                generate_latent_topic(block_text, db, user_id, job_id, llm_log_callback)
            )
    except RuntimeError:
        # No event loop, create one
        return asyncio.run(
            generate_latent_topic(block_text, db, user_id, job_id, llm_log_callback)
        )


