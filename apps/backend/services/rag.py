"""
Retrieval-Augmented Generation service
Enhanced with top-k similarity search and chunk support
"""
from sqlalchemy.orm import Session
from sqlalchemy import text as sql_text
from typing import Optional, List, Tuple, Dict, Union
from datetime import datetime
from services.embeddings import generate_embedding, find_similar_messages
from services.logs_service import log_to_db
from services.metrics import record_rag_hit
from services.action_logger import log_action_context
from models import Message, Summary


def retrieve_context(
    db: Session,
    query: str,
    user_id: int,
    limit: int = 5,
    language: Optional[str] = None,
    use_chunks: bool = True,
    sender: Optional[str] = None,
    recipient: Optional[str] = None,
    request_id: Optional[str] = None,
    return_details: bool = False
) -> Union[str, Tuple[str, Dict]]:
    """
    Retrieve relevant conversation context using RAG with top-k similarity
    Returns formatted context string for LLM prompt
    """
    try:
        # Use enhanced RAG query with logging
        with log_action_context(
            db=db,
            action_type="semantic_search",
            model="pgvector",
            input_data={
                "query": query[:500],  # Limiter la taille
                "limit": limit,
                "user_id": user_id,
                "language": language,
                "use_chunks": use_chunks
            },
            request_id=request_id,
            user_id=user_id,
            metadata={"search_engine": "pgvector"}
        ) as log:
            similar_results = find_similar_messages_enhanced(
                db,
                query,
                limit=limit,
                user_id=user_id,
                language=language,
                use_chunks=use_chunks,
                sender=sender,
                recipient=recipient,
                request_id=request_id
            )
            
            # Log results
            if similar_results:
                avg_similarity = sum(r['similarity'] for r in similar_results) / len(similar_results)
                log.set_output({
                    "results_count": len(similar_results),
                    "top_similarity": similar_results[0]['similarity'] if similar_results else 0,
                    "avg_similarity": avg_similarity,
                    "similarities": [r['similarity'] for r in similar_results[:10]]
                })
            else:
                log.set_output({"results_count": 0})
        
        if not similar_results:
            return "No relevant conversation history found."
        
        # Record RAG hit
        avg_similarity = sum(r['similarity'] for r in similar_results) / len(similar_results) if similar_results else 0
        record_rag_hit(db, avg_similarity, len(similar_results))
        
        context_parts = ["Relevant conversation history:"]
        for result in similar_results:
            message = result['message']
            similarity = result['similarity']
            summary = result.get('summary')
            tags = result.get('tags')
            
            # Only include messages from the same user
            if message and message.user_id == user_id:
                # Build context line with sender/recipient info
                context_line = (
                    f"[{message.timestamp.strftime('%Y-%m-%d %H:%M')}] "
                    f"{message.sender}"
                )
                
                # Add recipient info if available
                if message.recipient:
                    context_line += f" → {message.recipient}"
                elif message.recipients:
                    participants_str = ", ".join(message.recipients[:3])  # Limit for display
                    if len(message.recipients) > 3:
                        participants_str += f" (+{len(message.recipients) - 3} others)"
                    context_line += f" → [Group: {participants_str}]"
                
                context_line += f": {message.content}"
                
                # Add summary if available (for chunks)
                if summary:
                    context_line += f" [Summary: {summary}]"
                
                # Add similarity score for debugging
                context_line += f" (similarity: {similarity:.2f})"
                
                context_parts.append(context_line)
        
        context = "\n".join(context_parts)
        
        if return_details:
            # Return context + debug details
            details = {
                "results_count": len(similar_results),
                "top_similarity": similar_results[0]['similarity'] if similar_results else 0,
                "avg_similarity": avg_similarity if similar_results else 0,
                "results": [
                    {
                        "content": r['message'].content if r.get('message') else "",
                        "sender": r['message'].sender if r.get('message') else "",
                        "timestamp": r['message'].timestamp.isoformat() if r.get('message') and r['message'].timestamp else "",
                        "source": r['message'].source if r.get('message') else "",
                        "similarity": r['similarity'],
                        "summary": r.get('summary'),
                        "tags": r.get('tags'),
                    }
                    for r in similar_results
                ]
            }
            return context, details
        
        return context
    
    except Exception as e:
        log_to_db(db, "ERROR", f"RAG retrieval error: {str(e)}", service="rag")
        if return_details:
            return "Error retrieving context.", {"results_count": 0, "top_similarity": 0, "avg_similarity": 0, "results": []}
        return "Error retrieving context."


def find_similar_messages_enhanced(
    db: Session,
    query_text: str,
    limit: int = 10,
    threshold: float = 0.5,  # Reduced from 0.7 to be more permissive
    user_id: Optional[int] = None,
    language: Optional[str] = None,
    use_chunks: bool = True,
    sender: Optional[str] = None,
    recipient: Optional[str] = None,
    request_id: Optional[str] = None
) -> List[Dict]:
    """
    Enhanced similarity search with top-k, language filtering, and chunk support
    Returns list of dicts with: message, similarity, summary (if chunk), tags
    """
    query_vector = generate_embedding(query_text, db=db, request_id=request_id, user_id=user_id)
    vector_str = "[" + ",".join(map(str, query_vector)) + "]"
    
    # Build query with optional filters - use CAST instead of ::type in params
    # For chunks, use conversation_id from metadata (stored during ingestion)
    query_sql = """
        SELECT
            m.id, m.content, m.sender, m.timestamp, 
            COALESCE(m.source, e.metadata->>'source') as source,
            m.conversation_id, m.user_id, m.created_at,
            m.recipient, m.recipients,
            e.id as embedding_id,
            e.text as embedding_text,
            1 - (e.vector <=> CAST(:query_vector AS vector)) as similarity,
            e.metadata->>'tags' as tags,
            CASE WHEN e.metadata->>'chunk' = 'true' THEN TRUE ELSE FALSE END as is_chunk,
            COALESCE(m.conversation_id, e.metadata->>'conversation_id', e.metadata->>'thread_id') as effective_conversation_id,
            COALESCE(m.user_id, (
                SELECT DISTINCT msg.user_id 
                FROM messages msg 
                WHERE msg.conversation_id = COALESCE(m.conversation_id, e.metadata->>'conversation_id', e.metadata->>'thread_id')
                LIMIT 1
            )) as effective_user_id
        FROM embeddings e
        LEFT JOIN messages m ON e.message_id = m.id
        WHERE 1 - (e.vector <=> CAST(:query_vector AS vector)) >= :threshold
    """
    
    # Build params dict
    params = {
        "query_vector": vector_str,
        "threshold": threshold,
        "limit": limit
    }
    
    # Filter by user_id: for messages use m.user_id, for chunks use conversation_id/thread_id from metadata
    # Note: Chunks without conversation_id/thread_id in metadata (old chunks) won't be filtered by user_id
    # This is acceptable if all data belongs to the same user or for backward compatibility
    if user_id:
        query_sql += """ AND (
            m.user_id = :user_id 
            OR (e.metadata->>'chunk' = 'true' AND EXISTS (
                SELECT 1 FROM messages msg 
                WHERE msg.conversation_id = COALESCE(m.conversation_id, e.metadata->>'conversation_id', e.metadata->>'thread_id')
                AND msg.user_id = :user_id
            ))
        )"""
        params["user_id"] = user_id
    
    if language:
        query_sql += " AND e.metadata->>'language' = :language"
        params["language"] = language
    
    # Filter by sender (from metadata or message)
    if sender:
        query_sql += " AND (e.metadata->>'sender' = :sender OR m.sender = :sender)"
        params["sender"] = sender
    
    # Filter by recipient (1-1 conversations) or participants (groups)
    if recipient:
        query_sql += """ AND (
            m.recipient = :recipient 
            OR e.metadata->>'recipient' = :recipient
            OR :recipient = ANY(SELECT jsonb_array_elements_text(m.recipients))
            OR :recipient = ANY(SELECT jsonb_array_elements_text(e.metadata->'recipients'))
        )"""
        params["recipient"] = recipient
    
    if not use_chunks:
        query_sql += " AND e.metadata->>'chunk' != 'true'"
    
    # Order by chunk priority and similarity
    if use_chunks:
        query_sql += " ORDER BY is_chunk DESC, e.vector <=> CAST(:query_vector AS vector)"
    else:
        query_sql += " ORDER BY e.vector <=> CAST(:query_vector AS vector)"
    
    query_sql += " LIMIT :limit"
    
    query = sql_text(query_sql)
    results = db.execute(query, params)
    
    # Format results with summary lookup if chunk
    formatted_results = []
    for row in results:
        # Handle both messages and chunks
        if row.id:  # Has message (regular message embedding)
            msg = Message(
                id=row.id,
                content=row.content,
                sender=row.sender,
                recipient=getattr(row, 'recipient', None),
                recipients=getattr(row, 'recipients', None),
                timestamp=row.timestamp,
                source=row.source,
                conversation_id=row.conversation_id,
                user_id=row.user_id,
                created_at=row.created_at
            )
            
            result_dict = {
                'message': msg,
                'similarity': float(row.similarity),
            }
        else:  # Chunk without message_id (chunk embedding)
            # Create a pseudo-message for chunks using embedding text
            effective_conv_id = getattr(row, 'effective_conversation_id', None)
            effective_user_id = getattr(row, 'effective_user_id', None)
            
            # Extract sender from metadata or use first sender
            chunk_senders = None
            if hasattr(row, 'embedding_text'):
                # Try to get sender from metadata
                pass  # Will be handled below
            
            msg = Message(
                id=None,  # No message ID for chunks
                content=getattr(row, 'embedding_text', ''),
                sender=getattr(row, 'sender', 'Multiple senders'),  # Fallback
                recipient=None,
                recipients=None,
                timestamp=datetime.utcnow(),  # Fallback timestamp
                source=getattr(row, 'source', 'whatsapp'),
                conversation_id=effective_conv_id,
                user_id=effective_user_id,
                created_at=datetime.utcnow()
            )
            
            result_dict = {
                'message': msg,
                'similarity': float(row.similarity),
            }
        
        # If chunk, try to get summary
        conversation_id_for_summary = getattr(row, 'effective_conversation_id', None) or getattr(row, 'conversation_id', None)
        if row.is_chunk and conversation_id_for_summary:
            summary = db.query(Summary).filter(
                Summary.conversation_id == conversation_id_for_summary
            ).first()
            if summary:
                # Parse TL;DR and Tags from summary_text
                summary_text = summary.summary_text
                if "TL;DR:" in summary_text:
                    result_dict['summary'] = summary_text.split("TL;DR:")[1].split("Tags:")[0].strip()
                if "Tags:" in summary_text:
                    result_dict['tags'] = summary_text.split("Tags:")[1].strip()
        
        if hasattr(row, 'tags') and row.tags:
            result_dict['tags'] = row.tags
        
        formatted_results.append(result_dict)
    
    return formatted_results


def build_prompt_with_context(
    current_message: str,
    context: str,
    user_style: Optional[str] = None
) -> str:
    """
    Build prompt with retrieved context
    """
    prompt_parts = []
    
    if context:
        prompt_parts.append(context)
        prompt_parts.append("\n---\n")
    
    if user_style:
        prompt_parts.append(f"User communication style: {user_style}\n")
    
    prompt_parts.append(f"Current message to respond to: {current_message}\n")
    prompt_parts.append("Generate a personalized response that matches the user's style and context.")
    
    return "\n".join(prompt_parts)
