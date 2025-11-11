"""
Summary generation service
Generates TL;DR summaries and extracts tags from conversation chunks
"""
import asyncio
from sqlalchemy.orm import Session
from typing import List, Dict, Optional, Callable
from services.llm_router import generate_llm_response
from services.logs_service import log_to_db


async def generate_summary(
    chunk_text: str,
    db: Optional[Session] = None
) -> Dict[str, str]:
    """
    Generate summary for a conversation chunk
    Returns dict with: summary (TL;DR), tags (comma-separated)
    """
    prompt = f"""Analyze this WhatsApp conversation chunk and provide:
1. A concise TL;DR summary (2-3 sentences)
2. Key tags/topics (3-5 comma-separated tags)

Conversation chunk:
{chunk_text}

Format your response as:
TL;DR: [summary]
Tags: [tag1, tag2, tag3]

Only provide the TL;DR and Tags lines, nothing else."""
    
    try:
        response = await generate_llm_response(prompt, temperature=0.3, db=db)
        
        # Parse response
        summary = ""
        tags = ""
        
        for line in response.split('\n'):
            line = line.strip()
            if line.startswith('TL;DR:'):
                summary = line.replace('TL;DR:', '').strip()
            elif line.startswith('Tags:'):
                tags = line.replace('Tags:', '').strip()
        
        # Fallback if parsing failed
        if not summary:
            summary = response[:200] + "..." if len(response) > 200 else response
        if not tags:
            tags = "conversation"
        
        return {
            'summary': summary,
            'tags': tags,
        }
    
    except Exception as e:
        error_msg = f"Summary generation error: {str(e)}"
        if db:
            log_to_db(db, "ERROR", error_msg, service="summarizer")
        # Return fallback
        return {
            'summary': f"Conversation chunk ({len(chunk_text.split())} words)",
            'tags': "conversation",
        }


def generate_summaries_sync(
    chunks: List[Dict],
    db: Optional[Session] = None,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> List[Dict]:
    """
    Generate summaries for multiple chunks (synchronous wrapper)
    
    Args:
        chunks: List of chunk dictionaries
        db: Optional database session
        progress_callback: Optional callback(current, total) for progress updates
    """
    summaries = []
    total_chunks = len(chunks)
    
    # Use event loop for async operations
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    async def process_all():
        results = []
        for idx, chunk in enumerate(chunks):
            summary_data = await generate_summary(chunk['text'], db)
            chunk_with_summary = {**chunk, **summary_data}
            results.append(chunk_with_summary)
            
            # Call progress callback every 10 summaries or on last one
            if progress_callback and ((idx + 1) % 10 == 0 or (idx + 1) == total_chunks):
                progress_callback(idx + 1, total_chunks)
            
            # Log less frequently to avoid DB overhead
            if db and (idx + 1) % 50 == 0:
                log_to_db(
                    db,
                    "INFO",
                    f"Generated {idx + 1}/{total_chunks} summaries...",
                    service="summarizer"
                )
        return results
    
    summaries = loop.run_until_complete(process_all())
    return summaries

