"""
RAG Chain for automatic context injection
Automatically retrieves relevant documents and injects them into the prompt
"""
from typing import Optional, List, Dict, Any
from langchain_core.language_models import BaseLanguageModel
from langchain_core.retrievers import BaseRetriever
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.documents import Document
from sqlalchemy.orm import Session
from services.logs_service import log_to_db
import time
import asyncio


# Metrics tracking
_rag_metrics = {
    "total_calls": 0,
    "successful_calls": 0,
    "failed_calls": 0,
    "fallback_used": 0,
    "total_latency_ms": 0.0,
    "total_chunks_retrieved": 0,
    "total_context_size": 0,
}


def get_rag_metrics() -> Dict[str, Any]:
    """Get current RAG metrics"""
    metrics = _rag_metrics.copy()
    if metrics["total_calls"] > 0:
        metrics["avg_latency_ms"] = metrics["total_latency_ms"] / metrics["total_calls"]
        metrics["success_rate"] = metrics["successful_calls"] / metrics["total_calls"]
        metrics["avg_chunks_per_call"] = metrics["total_chunks_retrieved"] / metrics["total_calls"]
        metrics["avg_context_size"] = metrics["total_context_size"] / metrics["total_calls"]
    else:
        metrics["avg_latency_ms"] = 0.0
        metrics["success_rate"] = 0.0
        metrics["avg_chunks_per_call"] = 0.0
        metrics["avg_context_size"] = 0.0
    return metrics


def reset_rag_metrics():
    """Reset RAG metrics (for testing)"""
    global _rag_metrics
    _rag_metrics = {
        "total_calls": 0,
        "successful_calls": 0,
        "failed_calls": 0,
        "fallback_used": 0,
        "total_latency_ms": 0.0,
        "total_chunks_retrieved": 0,
        "total_context_size": 0,
    }


def _compress_context(context: str, max_tokens: int = 5000) -> str:
    """
    Compress context if too long
    Simple truncation - could be enhanced with summarization
    """
    # Rough estimate: 1 token ≈ 4 characters
    max_chars = max_tokens * 4
    
    if len(context) <= max_chars:
        return context
    
    # Truncate and add indicator
    truncated = context[:max_chars]
    # Try to cut at a sentence boundary
    last_period = truncated.rfind('.')
    if last_period > max_chars * 0.9:  # If period is near the end
        truncated = truncated[:last_period + 1]
    
    return truncated + "\n\n[Context truncated due to length limit]"


def _format_context_from_documents(documents: List[Any], max_chunks: int = 10) -> str:
    """
    Format documents into context string with enhanced metadata
    Limits to max_chunks and compresses if necessary
    """
    if not documents:
        return ""
    
    # Limit number of chunks
    limited_docs = documents[:max_chunks]
    
    # Format documents with enhanced metadata
    context_parts = []
    for doc in limited_docs:
        # Extract metadata info
        metadata = doc.metadata if hasattr(doc, 'metadata') else {}
        source = metadata.get('source', 'unknown')
        sender = metadata.get('sender', '')
        timestamp = metadata.get('timestamp', '')
        conversation_id = metadata.get('conversation_id', '')
        
        # Try to extract date from timestamp
        date_str = ""
        if timestamp:
            try:
                from datetime import datetime
                if isinstance(timestamp, str):
                    # Try to parse ISO format
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    date_str = dt.strftime("%Y-%m-%d")
                elif isinstance(timestamp, datetime):
                    date_str = timestamp.strftime("%Y-%m-%d")
            except:
                pass
        
        # Build metadata string
        metadata_parts = []
        if source:
            metadata_parts.append(f"Source: {source}")
        if sender:
            metadata_parts.append(f"From: {sender}")
        if date_str:
            metadata_parts.append(f"Date: {date_str}")
        if conversation_id:
            # Shorten conversation_id for display
            short_id = conversation_id[:8] + "..." if len(conversation_id) > 8 else conversation_id
            metadata_parts.append(f"Conv: {short_id}")
        
        metadata_str = " | ".join(metadata_parts) if metadata_parts else "Unknown"
        
        # Format: [Metadata] content
        context_parts.append(f"[{metadata_str}]\n{doc.page_content}")
    
    context = "\n\n".join(context_parts)
    
    # Compress if too long
    context = _compress_context(context, max_tokens=5000)
    
    return context


def create_rag_chain(
    retriever: BaseRetriever,
    llm: BaseLanguageModel,
    prompt_template: ChatPromptTemplate,
    db: Optional[Session] = None,
    user_id: Optional[int] = None,
    max_chunks: int = 10,
    timeout_seconds: float = 5.0
) -> Any:
    """
    Create a RAG chain that automatically injects context
    
    Args:
        retriever: LangChain retriever
        llm: Language model
        prompt_template: Prompt template with {context} placeholder
        db: Database session for logging
        user_id: User ID for logging
        max_chunks: Maximum number of chunks to include in context
        timeout_seconds: Maximum time to wait for retrieval
    
    Returns:
        RAG chain wrapper that can be invoked with {"input": query, "chat_history": [...]}
        Returns dict with "context" key containing formatted context
    """
    try:
        # Wrap retriever with timeout and error handling
        class RAGChainWrapper:
            def __init__(self, retriever, max_chunks, timeout_seconds, db, user_id):
                self.retriever = retriever
                self.max_chunks = max_chunks
                self.timeout_seconds = timeout_seconds
                self.db = db
                self.user_id = user_id
            
            def invoke(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
                """Retrieve context with error handling and metrics"""
                global _rag_metrics
                start_time = time.time()
                _rag_metrics["total_calls"] += 1
                
                try:
                    query = input_data.get("input", "")
                    
                    # Retrieve documents with timeout
                    try:
                        # Use asyncio timeout for retrieval
                        if hasattr(self.retriever, 'invoke'):
                            # LangChain 0.2.x style
                            docs = asyncio.run(
                                asyncio.wait_for(
                                    asyncio.to_thread(self.retriever.invoke, query),
                                    timeout=self.timeout_seconds
                                )
                            )
                        elif hasattr(self.retriever, 'get_relevant_documents'):
                            # Older style
                            docs = asyncio.run(
                                asyncio.wait_for(
                                    asyncio.to_thread(self.retriever.get_relevant_documents, query),
                                    timeout=self.timeout_seconds
                                )
                            )
                        else:
                            raise ValueError("Retriever has no invoke or get_relevant_documents method")
                        
                        # Ensure docs is a list
                        if not isinstance(docs, list):
                            docs = [docs] if docs else []
                        
                        # Limit chunks
                        docs = docs[:self.max_chunks]
                        
                        # Format context
                        context = _format_context_from_documents(docs, max_chunks=self.max_chunks)
                        
                        # Update metrics
                        _rag_metrics["total_chunks_retrieved"] += len(docs)
                        _rag_metrics["total_context_size"] += len(context)
                        
                        latency_ms = (time.time() - start_time) * 1000
                        _rag_metrics["total_latency_ms"] += latency_ms
                        _rag_metrics["successful_calls"] += 1
                        
                        # Log success
                        if self.db:
                            log_to_db(
                                self.db,
                                "INFO",
                                f"RAG context retrieved: {len(docs)} chunks, {len(context)} chars, {latency_ms:.1f}ms",
                                service="rag_chain",
                                user_id=self.user_id,
                                metadata={
                                    "chunks_retrieved": len(docs),
                                    "context_size": len(context),
                                    "latency_ms": latency_ms
                                }
                            )
                        
                        return {
                            "context": context,
                            "chunks_retrieved": len(docs),
                            "documents": docs
                        }
                        
                    except asyncio.TimeoutError:
                        # Timeout - use fallback
                        _rag_metrics["failed_calls"] += 1
                        _rag_metrics["fallback_used"] += 1
                        latency_ms = (time.time() - start_time) * 1000
                        
                        if self.db:
                            log_to_db(
                                self.db,
                                "WARNING",
                                f"RAG retrieval timeout after {self.timeout_seconds}s, using fallback",
                                service="rag_chain",
                                user_id=self.user_id,
                                metadata={"timeout_seconds": self.timeout_seconds, "latency_ms": latency_ms}
                            )
                        
                        # Fallback: return empty context
                        return {
                            "context": "",
                            "chunks_retrieved": 0,
                            "documents": []
                        }
                    
                except Exception as e:
                    # Error - use fallback
                    _rag_metrics["failed_calls"] += 1
                    _rag_metrics["fallback_used"] += 1
                    latency_ms = (time.time() - start_time) * 1000
                    
                    if self.db:
                        log_to_db(
                            self.db,
                            "ERROR",
                            f"RAG retrieval error: {str(e)}, using fallback",
                            service="rag_chain",
                            user_id=self.user_id,
                            metadata={"error": str(e), "latency_ms": latency_ms}
                        )
                    
                    # Fallback: return empty context
                    return {
                        "context": "",
                        "chunks_retrieved": 0,
                        "documents": [],
                        "error": str(e)
                    }
        
        return RAGChainWrapper(retriever, max_chunks, timeout_seconds, db, user_id)
        
    except Exception as e:
        # If chain creation fails, return a fallback wrapper
        if db:
            log_to_db(
                db,
                "ERROR",
                f"Failed to create RAG chain: {str(e)}, will use fallback",
                service="rag_chain",
                user_id=user_id,
                metadata={"error": str(e)}
            )
        
        # Return a fallback wrapper that returns empty context
        class FallbackRAGChain:
            def invoke(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
                global _rag_metrics
                _rag_metrics["total_calls"] += 1
                _rag_metrics["failed_calls"] += 1
                _rag_metrics["fallback_used"] += 1
                return {
                    "answer": "",
                    "context": "",
                    "chunks_retrieved": 0,
                    "error": "RAG chain creation failed"
                }
        
        return FallbackRAGChain()



