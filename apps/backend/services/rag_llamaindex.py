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


def estimate_tokens(text: str) -> int:
    """
    Estimate number of tokens in text
    Approximation: 1 token ≈ 4 characters for French/English
    This is a rough estimate, actual tokenization varies by model
    """
    if not text:
        return 0
    # Conservative estimate: 1 token per 4 characters
    # This works well for French and English text
    return len(text) // 4


def get_model_context_window(provider: str, model: str) -> int:
    """
    Get the context window size for a specific model
    Looks up in rag_context_window_map, with intelligent fallbacks
    """
    provider_lower = provider.lower()
    model_lower = model.lower()
    
    # Try exact match first
    if provider_lower in settings.rag_context_window_map:
        if model_lower in settings.rag_context_window_map[provider_lower]:
            return settings.rag_context_window_map[provider_lower][model_lower]
        
        # Try partial match (e.g., "llama3.2:1b" matches "llama3.2:1b")
        for model_key, context_window in settings.rag_context_window_map[provider_lower].items():
            if model_lower in model_key.lower() or model_key.lower() in model_lower:
                return context_window
    
    # Fallback: provider-specific defaults
    if provider_lower == "openai":
        return 128000  # Most OpenAI models have large context windows
    elif provider_lower == "ollama":
        return 8192  # Most Ollama models have smaller context windows
    elif provider_lower == "vllm":
        return 32768  # vLLM models typically have medium context windows
    
    # Ultimate fallback
    return 4096


def calculate_available_context_tokens(
    provider: str,
    model: str,
    user_message: str,
    system_prompt_size: int = 200
) -> int:
    """
    Calculate available tokens for context after accounting for:
    - System prompt
    - User message
    - Safety buffer
    """
    context_window = get_model_context_window(provider, model)
    user_message_tokens = estimate_tokens(user_message)
    buffer = settings.rag_token_buffer
    
    available = context_window - system_prompt_size - user_message_tokens - buffer
    
    # Ensure we don't return negative
    return max(0, available)


def _get_recent_conversation_messages(
    db: Session,
    conversation_id: str,
    user_id: int,
    limit: int = 10
) -> List[Message]:
    """
    Get recent messages from the same conversation, ordered by timestamp (most recent first)
    This ensures we include recent context even if semantic similarity is low
    """
    try:
        messages = db.query(Message).filter(
            Message.conversation_id == conversation_id,
            Message.user_id == user_id
        ).order_by(Message.timestamp.desc()).limit(limit).all()
        return messages
    except Exception as e:
        log_to_db(db, "WARNING", f"Error fetching recent messages: {str(e)}", service="rag_llamaindex")
        return []


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
    recent_conversation_id: Optional[str] = None,
    request_id: Optional[str] = None,
    return_details: bool = False
) -> Union[str, Tuple[str, Dict]]:
    """
    Retrieve relevant conversation context using RAG with top-k similarity and optional reranking
    Returns formatted context string for LLM prompt
    
    Uses LlamaIndex for reranking when enabled (improves relevance by re-evaluating with cross-encoder)
    
    Also includes recent messages from the same conversation to ensure context continuity,
    even if they don't match semantically well with the query.
    
    Args:
        conversation_id: Filter RAG search to this conversation (None = search all conversations)
        recent_conversation_id: Include recent messages from this conversation (for context continuity)
                                 If None, uses conversation_id. Useful when you want to search all conversations
                                 but still include recent messages from a specific conversation.
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
                "rerank_enabled": settings.rag_rerank_enabled,
                "conversation_id": conversation_id,
                "recent_conversation_id": recent_conversation_id
            },
            request_id=request_id,
            user_id=user_id,
            conversation_id=conversation_id,  # Pass conversation_id to log context
            metadata={"search_engine": "llamaindex" if settings.rag_rerank_enabled else "pgvector"}
        ) as log:
            # Reduce threshold when filtering by conversation_id to prioritize recent conversation context
            # This ensures that recent messages in the same conversation are included even if semantic similarity is lower
            # Lower threshold (0.35) for global search to find more relevant results across all conversations
            threshold = 0.3 if conversation_id else 0.35  # More permissive threshold for global search
            similar_results = find_similar_messages_enhanced(
                db,
                query,
                limit=limit,
                threshold=threshold,
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
        
        # Combine RAG results with recent conversation messages
        # This ensures we don't miss important recent context
        all_messages_dict = {}  # key -> (message, similarity, summary, tags, from_rag)
        rag_message_ids = set()  # Track message IDs from RAG to avoid duplicates
        
        # Add RAG results (including chunks)
        if similar_results:
            for idx, result in enumerate(similar_results):
                message = result['message']
                if message and message.user_id == user_id:
                    # Use message.id as key if available, otherwise use index-based key for chunks
                    if message.id:
                        key = message.id
                        rag_message_ids.add(message.id)
                    else:
                        # For chunks without message.id, use a unique key based on content and timestamp
                        key = f"chunk_{idx}_{message.timestamp.isoformat() if message.timestamp else idx}"
                    
                    all_messages_dict[key] = (
                        message,
                        result['similarity'],
                        result.get('summary'),
                        result.get('tags'),
                        True  # from_rag
                    )
        
        # Add recent conversation messages (if recent_conversation_id or conversation_id provided)
        # This ensures recent context is included even if not semantically similar
        # Use recent_conversation_id if provided, otherwise fall back to conversation_id
        recent_conv_id = recent_conversation_id or conversation_id
        if recent_conv_id:
            recent_messages = _get_recent_conversation_messages(db, recent_conv_id, user_id, limit=limit * 2)
            for msg in recent_messages:
                if msg.id and msg.id not in rag_message_ids:
                    # Message not in RAG results, add it with similarity 0 (recent context)
                    all_messages_dict[msg.id] = (msg, 0.0, None, None, False)  # from_recent
        
        if not all_messages_dict:
            if return_details:
                return "No relevant conversation history found.", {"results_count": 0, "top_similarity": 0, "avg_similarity": 0, "results": []}
            return "No relevant conversation history found."
        
        # Record RAG hit
        rag_messages = [m for m in all_messages_dict.values() if m[4]]  # from_rag=True
        if rag_messages:
            avg_similarity = sum(r[1] for r in rag_messages) / len(rag_messages) if rag_messages else 0
            record_rag_hit(db, avg_similarity, len(rag_messages))
        
        # Build context lines, sorted by timestamp (chronological order)
        context_parts = ["Relevant conversation history:"]
        context_lines = []
        
        for message, similarity, summary, tags, from_rag in all_messages_dict.values():
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
            
            # Add similarity score for debugging (only for RAG results)
            if from_rag:
                context_line += f" (similarity: {similarity:.2f})"
            else:
                context_line += " (recent context)"
            
            context_lines.append((message.timestamp, context_line))
        
        # Sort by timestamp (chronological order)
        context_lines.sort(key=lambda x: x[0])
        context_parts.extend([line for _, line in context_lines])
        
        context = "\n".join(context_parts)
        
        if return_details:
            # Return context + debug details
            # Include both RAG and recent messages in details
            all_results = []
            for message, similarity, summary, tags, from_rag in all_messages_dict.values():
                all_results.append({
                    "content": message.content if message else "",
                    "sender": message.sender if message else "",
                    "timestamp": message.timestamp.isoformat() if message and message.timestamp else "",
                    "source": message.source if message else "",
                    "similarity": similarity if from_rag else None,  # None for recent context
                    "summary": summary,
                    "tags": tags,
                    "from_rag": from_rag
                })
            
            # Sort results by timestamp for details too
            all_results.sort(key=lambda x: x.get("timestamp", ""))
            
            details = {
                "results_count": len(all_messages_dict),
                "rag_results_count": len(rag_messages),
                "recent_results_count": len(all_messages_dict) - len(rag_messages),
                "top_similarity": max((r[1] for r in rag_messages), default=0) if rag_messages else 0,
                "avg_similarity": avg_similarity if rag_messages else 0,
                "reranked": settings.rag_rerank_enabled and (limit > 10 or len(similar_results) > limit) if similar_results else False,
                "results": all_results
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
    
    # Order by chunk priority, similarity, and timestamp (recent messages first)
    # This ensures that among messages with similar relevance, the most recent ones are prioritized
    if use_chunks:
        query_sql += """ ORDER BY 
            is_chunk DESC, 
            e.vector <=> CAST(:query_vector AS vector),
            COALESCE(m.timestamp, m.created_at, e.created_at) DESC NULLS LAST"""
    else:
        query_sql += """ ORDER BY 
            e.vector <=> CAST(:query_vector AS vector),
            COALESCE(m.timestamp, m.created_at, e.created_at) DESC NULLS LAST"""
    
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


def compress_context(
    context: str,
    max_tokens: int,
    db: Session,
    conversation_id: Optional[str],
    original_tokens: int
) -> Tuple[str, Dict]:
    """
    Compress context intelligently using hybrid strategy:
    1. Keep recent messages complete
    2. Use summaries for old messages if available
    3. Truncate intelligently if no summary available
    
    Returns: (compressed_context, metadata_dict)
    """
    import re
    
    if not context or context.strip() == "No relevant conversation history found.":
        return context, {
            "compression_applied": False,
            "compression_strategy": "none",
            "tokens_before": original_tokens,
            "tokens_after": estimate_tokens(context) if context else 0,
            "messages_compressed": 0
        }
    
    # Parse context into individual messages
    # Format: [timestamp] sender: content (similarity: X.XX)
    message_pattern = re.compile(r'\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\]\s+([^:]+):\s+(.+?)(?=\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}\]|$)', re.DOTALL)
    messages = []
    
    for match in message_pattern.finditer(context):
        timestamp = match.group(1)
        sender = match.group(2).strip()
        content = match.group(3).strip()
        # Remove similarity score if present
        content = re.sub(r'\s*\(similarity: [\d.]+\)\s*$', '', content)
        content = re.sub(r'\s*\(recent context\)\s*$', '', content)
        messages.append({
            "timestamp": timestamp,
            "sender": sender,
            "content": content,
            "full_line": match.group(0)
        })
    
    if not messages:
        # If parsing failed, try simple truncation
        compressed = context[:max_tokens * 4]  # 4 chars per token
        if len(compressed) < len(context):
            compressed += "\n[... context truncated ...]"
        return compressed, {
            "compression_applied": True,
            "compression_strategy": "truncation",
            "tokens_before": original_tokens,
            "tokens_after": estimate_tokens(compressed),
            "messages_compressed": 0
        }
    
    # Separate recent vs old messages
    recent_messages_count = settings.rag_recent_messages_keep
    recent_messages = messages[-recent_messages_count:] if len(messages) > recent_messages_count else messages
    old_messages = messages[:-recent_messages_count] if len(messages) > recent_messages_count else []
    
    compressed_parts = []
    messages_compressed = 0
    strategy_used = []
    
    # Try to use summary for old messages
    summary_available = False
    if old_messages and conversation_id:
        try:
            summary = db.query(Summary).filter(
                Summary.conversation_id == conversation_id
            ).first()
            
            if summary and summary.summary_text:
                # Parse summary to extract TL;DR
                summary_text = summary.summary_text
                if "TL;DR:" in summary_text:
                    tldr = summary_text.split("TL;DR:")[1].split("Tags:")[0].strip()
                    if tldr:
                        # Format summary as a context line
                        compressed_parts.append(f"[Summary] Previous conversation: {tldr}")
                        summary_available = True
                        messages_compressed = len(old_messages)
                        strategy_used.append("summary")
        except Exception as e:
            log_to_db(db, "WARNING", f"Error fetching summary for compression: {str(e)}", service="rag_llamaindex")
    
    # If no summary, truncate old messages intelligently
    if old_messages and not summary_available:
        # Keep first and last old messages, truncate middle ones
        if len(old_messages) > 2:
            # Keep first message
            compressed_parts.append(old_messages[0]["full_line"])
            # Truncate middle messages
            middle_messages = old_messages[1:-1]
            for msg in middle_messages:
                # Truncate content but keep structure
                truncated_content = msg["content"][:100] + "..." if len(msg["content"]) > 100 else msg["content"]
                compressed_parts.append(f"[{msg['timestamp']}] {msg['sender']}: {truncated_content} [truncated]")
                messages_compressed += 1
            # Keep last old message
            compressed_parts.append(old_messages[-1]["full_line"])
            strategy_used.append("truncation")
        else:
            # Keep all old messages if only 1-2
            for msg in old_messages:
                compressed_parts.append(msg["full_line"])
    
    # Add recent messages (always keep complete)
    for msg in recent_messages:
        compressed_parts.append(msg["full_line"])
    
    compressed_context = "\n".join(compressed_parts)
    compressed_tokens = estimate_tokens(compressed_context)
    
    # If still too long, apply final truncation
    if compressed_tokens > max_tokens:
        # Truncate from the end, keeping the header
        if "Relevant conversation history:" in compressed_context:
            header = "Relevant conversation history:\n"
            content = compressed_context[len(header):]
            max_content_chars = (max_tokens - estimate_tokens(header)) * 4
            if len(content) > max_content_chars:
                content = content[:max_content_chars] + "\n[... context truncated due to length ...]"
            compressed_context = header + content
            strategy_used.append("final_truncation")
    
    final_tokens = estimate_tokens(compressed_context)
    
    return compressed_context, {
        "compression_applied": True,
        "compression_strategy": "+".join(strategy_used) if strategy_used else "none",
        "tokens_before": original_tokens,
        "tokens_after": final_tokens,
        "messages_compressed": messages_compressed,
        "recent_messages_kept": len(recent_messages),
        "summary_used": summary_available
    }


def build_prompt_with_context(
    current_message: str,
    context: str,
    user_style: Optional[str] = None,
    provider: str = "openai",
    model: str = "gpt-4o-mini",
    db: Optional[Session] = None,
    conversation_id: Optional[str] = None
) -> Tuple[str, Dict]:
    """
    Build prompt with retrieved context
    Includes dynamic token management and context compression
    
    Returns: (prompt, metadata_dict) with token information
    """
    # Calculate token limits
    context_window = get_model_context_window(provider, model)
    available_tokens = calculate_available_context_tokens(provider, model, current_message)
    context_tokens_before = estimate_tokens(context)
    
    metadata = {
        "model_context_window": context_window,
        "available_tokens": available_tokens,
        "context_tokens_before": context_tokens_before,
        "compression_applied": False,
        "compression_strategy": "none"
    }
    
    # Compress context if needed
    if settings.rag_compression_enabled and context_tokens_before > available_tokens:
        if db is None:
            # If no db provided, use simple truncation
            compressed = context[:available_tokens * 4]
            if len(compressed) < len(context):
                compressed += "\n[... context truncated ...]"
            context = compressed
            metadata["compression_applied"] = True
            metadata["compression_strategy"] = "truncation"
            metadata["context_tokens_after"] = estimate_tokens(context)
        else:
            context, compression_metadata = compress_context(
                context,
                available_tokens,
                db,
                conversation_id,
                context_tokens_before
            )
            metadata.update(compression_metadata)
            metadata["context_tokens_after"] = compression_metadata.get("tokens_after", estimate_tokens(context))
    else:
        metadata["context_tokens_after"] = context_tokens_before
    
    # Build prompt
    prompt_parts = []
    
    if context and context.strip() and context != "No relevant conversation history found.":
        prompt_parts.append("=== Conversation History ===")
        prompt_parts.append(context)
        prompt_parts.append("=== End of History ===")
        prompt_parts.append("")
        prompt_parts.append("Instructions:")
        prompt_parts.append("- Use the conversation history above to understand context and provide relevant responses")
        prompt_parts.append("- If the user's message refers to previous messages, use that context appropriately")
        prompt_parts.append("- If context information is missing, ask clarifying questions when helpful")
        prompt_parts.append("- Respond naturally and conversationally, maintaining the conversation flow")
        if metadata.get("compression_applied"):
            prompt_parts.append("- Note: Some older messages have been summarized/truncated for context management")
    else:
        prompt_parts.append("No previous conversation history available.")
        prompt_parts.append("Respond naturally to the user's message.")
    
    prompt_parts.append("")
    
    if user_style:
        prompt_parts.append(f"User communication style: {user_style}")
        prompt_parts.append("")
    
    prompt_parts.append(f"User message: {current_message}")
    prompt_parts.append("")
    prompt_parts.append("Generate a helpful, contextual response:")
    
    prompt = "\n".join(prompt_parts)
    
    return prompt, metadata

