"""
Retrieval-Augmented Generation service using LlamaIndex
Enhanced with reranking using cross-encoder models
"""
from sqlalchemy.orm import Session
from sqlalchemy import text as sql_text
from typing import Optional, List, Tuple, Dict, Union, TYPE_CHECKING, Any
from datetime import datetime
from services.embeddings import generate_embedding
from services.logs_service import log_to_db
from services.metrics import record_rag_hit
from services.action_logger import log_action_context
from models import Message, Summary
from config import settings

# Import LlamaIndex components
try:
    from llama_index.core import Settings as LlamaSettings
    from llama_index.embeddings.huggingface import HuggingFaceEmbedding
    from llama_index.postprocessor.sentence_transformer_rerank import SentenceTransformerRerank
    from llama_index.core.schema import NodeWithScore, TextNode
    LLAMAINDEX_AVAILABLE = True
except ImportError:
    LLAMAINDEX_AVAILABLE = False
    # Fallback if LlamaIndex not installed
    SentenceTransformerRerank = None
    NodeWithScore = None
    TextNode = None


# Initialize LlamaIndex settings and reranker (singleton pattern)
_reranker: Optional[Any] = None
_llama_settings_initialized = False


def _initialize_llama_settings():
    """Initialize LlamaIndex global settings with embedding model"""
    global _llama_settings_initialized
    if not LLAMAINDEX_AVAILABLE or _llama_settings_initialized:
        return
    
    try:
        # Configure embedding model (same as our existing model)
        LlamaSettings.embed_model = HuggingFaceEmbedding(
            model_name=settings.embedding_model
        )
        _llama_settings_initialized = True
    except Exception as e:
        log_to_db(None, "WARNING", f"Failed to initialize LlamaIndex settings: {str(e)}", service="rag_llamaindex")


def _get_reranker() -> Optional[Any]:
    """Get or create reranker instance (singleton)"""
    global _reranker
    if not LLAMAINDEX_AVAILABLE:
        return None
    
    if _reranker is None and settings.rag_rerank_enabled:
        try:
            _reranker = SentenceTransformerRerank(
                model=settings.rag_rerank_model,
                top_n=10  # Keep top 10 after reranking
            )
        except Exception as e:
            log_to_db(None, "WARNING", f"Failed to initialize reranker: {str(e)}", service="rag_llamaindex")
            return None
    
    return _reranker if settings.rag_rerank_enabled else None


def retrieve_context(
    db: Session,
    query: str,
    user_id: int,
    limit: int = 5,
    language: Optional[str] = None,
    use_chunks: bool = True,
    sender: Optional[str] = None,
    recipient: Optional[str] = None,
    conversation_id: Optional[str] = None,
    request_id: Optional[str] = None,
    return_details: bool = False
) -> Union[str, Tuple[str, Dict]]:
    """
    Retrieve relevant conversation context using RAG with top-k similarity and optional reranking
    Returns formatted context string for LLM prompt
    
    Uses LlamaIndex for reranking when enabled (improves relevance by re-evaluating with cross-encoder)
    """
    try:
        # Initialize LlamaIndex settings if needed
        _initialize_llama_settings()
        
        # Use enhanced RAG query with logging
        with log_action_context(
            db=db,
            action_type="semantic_search",
            model="llamaindex" if settings.rag_rerank_enabled else "pgvector",
            input_data={
                "query": query[:500],
                "limit": limit,
                "user_id": user_id,
                "language": language,
                "use_chunks": use_chunks,
                "rerank_enabled": settings.rag_rerank_enabled
            },
            request_id=request_id,
            user_id=user_id,
            metadata={"search_engine": "llamaindex" if settings.rag_rerank_enabled else "pgvector"}
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
                conversation_id=conversation_id,
                request_id=request_id
            )
            
            # Log results
            if similar_results:
                avg_similarity = sum(r['similarity'] for r in similar_results) / len(similar_results)
                log.set_output({
                    "results_count": len(similar_results),
                    "top_similarity": similar_results[0]['similarity'] if similar_results else 0,
                    "avg_similarity": avg_similarity,
                    "similarities": [r['similarity'] for r in similar_results[:10]],
                    "reranked": settings.rag_rerank_enabled and limit > 10
                })
            else:
                log.set_output({"results_count": 0})
        
        if not similar_results:
            if return_details:
                return "No relevant conversation history found.", {"results_count": 0, "top_similarity": 0, "avg_similarity": 0, "results": []}
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
                "reranked": settings.rag_rerank_enabled and (limit > 10 or len(similar_results) > limit),
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
        log_to_db(db, "ERROR", f"RAG retrieval error: {str(e)}", service="rag_llamaindex")
        if return_details:
            return "Error retrieving context.", {"results_count": 0, "top_similarity": 0, "avg_similarity": 0, "results": []}
        return "Error retrieving context."


def find_similar_messages_enhanced(
    db: Session,
    query_text: str,
    limit: int = 10,
    threshold: float = 0.5,
    user_id: Optional[int] = None,
    language: Optional[str] = None,
    use_chunks: bool = True,
    sender: Optional[str] = None,
    recipient: Optional[str] = None,
    conversation_id: Optional[str] = None,
    request_id: Optional[str] = None
) -> List[Dict]:
    """
    Enhanced similarity search with top-k, language filtering, chunk support, and optional reranking
    Returns list of dicts with: message, similarity, summary (if chunk), tags
    
    Uses LlamaIndex reranking when enabled and limit > 10
    """
    # Determine if we should use reranking
    use_reranking = (
        LLAMAINDEX_AVAILABLE and
        settings.rag_rerank_enabled and
        (limit > 10 or settings.rag_rerank_top_k > limit)
    )
    
    # If reranking, retrieve more results initially
    initial_limit = settings.rag_rerank_top_k if use_reranking else limit
    
    # Generate query embedding
    query_vector = generate_embedding(query_text, db=db, request_id=request_id, user_id=user_id)
    vector_str = "[" + ",".join(map(str, query_vector)) + "]"
    
    # Build query with optional filters
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
        "limit": initial_limit
    }
    
    # Filter by user_id
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
    
    # Filter by sender
    if sender:
        query_sql += " AND (e.metadata->>'sender' = :sender OR m.sender = :sender)"
        params["sender"] = sender
    
    # Filter by recipient
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
    
    # Filter by conversation_id (prioritize current conversation)
    if conversation_id:
        query_sql += """ AND (
            m.conversation_id = :conversation_id 
            OR e.metadata->>'conversation_id' = :conversation_id
            OR e.metadata->>'thread_id' = :conversation_id
        )"""
        params["conversation_id"] = conversation_id
    
    # Order by chunk priority and similarity
    if use_chunks:
        query_sql += " ORDER BY is_chunk DESC, e.vector <=> CAST(:query_vector AS vector)"
    else:
        query_sql += " ORDER BY e.vector <=> CAST(:query_vector AS vector)"
    
    query_sql += " LIMIT :limit"
    
    query = sql_text(query_sql)
    results = db.execute(query, params)
    
    # Format results
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
    
    # Apply reranking if enabled
    original_results = formatted_results.copy()  # Keep copy for fallback
    if use_reranking and formatted_results and LLAMAINDEX_AVAILABLE:
        try:
            reranker = _get_reranker()
            if reranker:
                # Convert results to LlamaIndex NodeWithScore format
                nodes = []
                for idx, result in enumerate(formatted_results):
                    node = TextNode(
                        text=result['message'].content,
                        metadata={
                            'message_id': result['message'].id,
                            'sender': result['message'].sender,
                            'similarity': result['similarity'],
                            'result_index': idx  # Use index to reference original
                        }
                    )
                    # Use similarity as initial score
                    nodes.append(NodeWithScore(node=node, score=result['similarity']))
                
                # Rerank nodes
                reranked_nodes = reranker.postprocess_nodes(
                    nodes,
                    query_str=query_text
                )
                
                # Convert back to our format, keeping top limit
                reranked_results = []
                for node_with_score in reranked_nodes[:limit]:
                    # Get original result by index
                    result_idx = node_with_score.node.metadata.get('result_index')
                    if result_idx is not None and result_idx < len(original_results):
                        original_result = original_results[result_idx].copy()
                        # Update similarity with reranked score
                        original_result['similarity'] = float(node_with_score.score)
                        reranked_results.append(original_result)
                    else:
                        # Fallback: create from node
                        reranked_results.append({
                            'message': Message(
                                id=node_with_score.node.metadata.get('message_id'),
                                content=node_with_score.node.text,
                                sender=node_with_score.node.metadata.get('sender', 'Unknown'),
                                timestamp=datetime.utcnow(),
                                source='unknown',
                                conversation_id=None,
                                user_id=user_id,
                                created_at=datetime.utcnow()
                            ),
                            'similarity': float(node_with_score.score)
                        })
                
                formatted_results = reranked_results
            else:
                # Reranker not available, use original results
                formatted_results = original_results[:limit]
                
        except Exception as e:
            log_to_db(db, "WARNING", f"Reranking failed, using original results: {str(e)}", service="rag_llamaindex", request_id=request_id)
            # Fallback to original results if reranking fails
            formatted_results = original_results[:limit]
    else:
        # No reranking, just take top limit
        formatted_results = formatted_results[:limit]
    
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

