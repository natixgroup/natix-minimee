"""
Advanced RAG retriever with multi-query, compression, reranking, and history-aware capabilities
"""
from typing import Optional, List, Dict, Any
from langchain_core.retrievers import BaseRetriever
from langchain_core.language_models import BaseLanguageModel
from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.multi_query import MultiQueryRetriever
from langchain.retrievers.document_compressors import CrossEncoderReranker
from langchain.chains.history_aware_retriever import create_history_aware_retriever
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from sqlalchemy.orm import Session
from .vector_store import get_vector_store_retriever
from config import settings


def create_advanced_retriever(
    llm: BaseLanguageModel,
    db: Session,
    user_id: int,
    conversation_id: Optional[str] = None,
    source: Optional[str] = None,
    initial_limit: int = 20,
    final_limit: int = 10,
    threshold: float = 0.2,  # Lowered from 0.3 to 0.2 for better recall (especially for proper names)
    use_reranking: bool = True,
    use_multi_query: bool = True,
    use_history_aware: bool = True
) -> BaseRetriever:
    """
    Create an advanced RAG retriever with multiple enhancement strategies
    
    Args:
        llm: Language model for multi-query and history-aware features
        db: Database session
        user_id: User ID for filtering
        conversation_id: Optional conversation ID filter
        source: Optional source filter (whatsapp, gmail, etc.)
        initial_limit: Number of results to retrieve before reranking
        final_limit: Number of results to return after reranking
        threshold: Minimum similarity threshold
        use_reranking: Enable cross-encoder reranking
        use_multi_query: Enable multi-query retriever (reformulates queries)
        use_history_aware: Enable history-aware retriever (uses conversation context)
    
    Returns:
        Advanced retriever with all enabled enhancements
    """
    # Base retriever using our custom vector store
    base_retriever = get_vector_store_retriever(
        db=db,
        user_id=user_id,
        conversation_id=conversation_id,
        source=source,
        limit=initial_limit,
        threshold=threshold
    )
    
    current_retriever = base_retriever
    
    # Step 1: Multi-query retriever (reformulates query for better retrieval)
    # DISABLED for now - can transform "Hajar" into unrelated queries
    # if use_multi_query and llm:
    #     try:
    #         current_retriever = MultiQueryRetriever.from_llm(
    #             retriever=current_retriever,
    #             llm=llm
    #         )
    #     except Exception as e:
    #         # Fallback to base retriever if multi-query fails
    #         from services.logs_service import log_to_db
    #         log_to_db(db, "WARNING", f"Multi-query retriever failed, using base: {str(e)}", service="minimee_agent")
    
    # Step 2: Reranking with cross-encoder (improves relevance)
    if use_reranking:
        try:
            reranker = CrossEncoderReranker(
                model=settings.rag_rerank_model if hasattr(settings, 'rag_rerank_model') else "cross-encoder/ms-marco-MiniLM-L-6-v2",
                top_n=final_limit
            )
            
            compression_retriever = ContextualCompressionRetriever(
                base_compressor=reranker,
                base_retriever=current_retriever
            )
            current_retriever = compression_retriever
        except Exception as e:
            # Fallback if reranking fails
            from services.logs_service import log_to_db
            log_to_db(db, "WARNING", f"Reranking failed, using base: {str(e)}", service="minimee_agent")
    
    # Step 3: History-aware retriever (uses conversation context)
    # DISABLED for now - can transform simple queries like "Hajar" into complex queries
    # if use_history_aware and llm:
    #     try:
    #         # Create prompt for history-aware retrieval
    #         history_prompt = ChatPromptTemplate.from_messages([
    #             MessagesPlaceholder(variable_name="chat_history"),
    #             ("user", "{input}"),
    #             ("user", "Given the above conversation, generate a search query to find relevant information from the conversation history.")
    #         ])
    #         
    #         current_retriever = create_history_aware_retriever(
    #             llm=llm,
    #             retriever=current_retriever,
    #             prompt=history_prompt
    #         )
    #     except Exception as e:
    #         # Fallback if history-aware fails
    #         from services.logs_service import log_to_db
    #         log_to_db(db, "WARNING", f"History-aware retriever failed, using base: {str(e)}", service="minimee_agent")
    
    return current_retriever


def create_simple_retriever(
    db: Session,
    user_id: int,
    conversation_id: Optional[str] = None,
    source: Optional[str] = None,
    limit: int = 10,
    threshold: float = 0.2  # Lowered from 0.3 to 0.2 for better recall
) -> BaseRetriever:
    """
    Create a simple retriever without advanced features (for fallback or simple use cases)
    
    Args:
        db: Database session
        user_id: User ID for filtering
        conversation_id: Optional conversation ID filter
        source: Optional source filter
        limit: Maximum number of results
        threshold: Minimum similarity threshold
    
    Returns:
        Simple retriever
    """
    return get_vector_store_retriever(
        db=db,
        user_id=user_id,
        conversation_id=conversation_id,
        source=source,
        limit=limit,
        threshold=threshold
    )


