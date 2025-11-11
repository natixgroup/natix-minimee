"""
Custom vector store for LangChain using Minimee's existing embeddings table
We use a custom retriever instead of PGVector since our schema is different
"""
from typing import Optional, List, Any
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from .embeddings_wrapper import MinimeeEmbeddings
from services.embeddings import generate_embedding
from sqlalchemy.orm import Session
from sqlalchemy import text as sql_text


class MinimeeVectorStoreRetriever(BaseRetriever):
    """
    Custom retriever that uses Minimee's existing embeddings table
    Directly queries the embeddings table with pgvector similarity search
    """
    
    db: Any  # Session - using Any to avoid Pydantic validation issues
    user_id: Optional[int] = None
    conversation_id: Optional[str] = None
    source: Optional[str] = None  # Deprecated: use included_sources instead
    included_sources: Optional[List[str]] = None  # List of sources to include (whatsapp, gmail). None = all sources, [] = no sources, [source1, ...] = only these sources.
    limit: int = 15  # Increased from 10 to 15 for better context
    threshold: float = 0.15  # Lowered from 0.2 to 0.15 for better recall
    embeddings: Any = None  # MinimeeEmbeddings
    
    class Config:
        arbitrary_types_allowed = True
    
    def __init__(
        self,
        db: Session,
        user_id: Optional[int] = None,
        conversation_id: Optional[str] = None,
        source: Optional[str] = None,  # Deprecated: use included_sources instead
        included_sources: Optional[List[str]] = None,
        limit: int = 15,  # Increased from 10 to 15 for better context
        threshold: float = 0.15,  # Lowered from 0.2 to 0.15 for better recall
        **kwargs
    ):
        super().__init__(**kwargs)
        self.db = db
        self.user_id = user_id
        self.conversation_id = conversation_id
        # Support both old source parameter (for backward compatibility) and new included_sources
        if included_sources is not None:
            self.included_sources = included_sources
            self.source = None  # Clear old source if included_sources is provided
        else:
            self.included_sources = [source] if source else None
            self.source = source  # Keep for backward compatibility
        self.limit = limit
        self.threshold = threshold
        self.embeddings = MinimeeEmbeddings()
    
    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverRun,
    ) -> List[Document]:
        """
        Retrieve relevant documents using pgvector similarity search
        """
        # Generate query embedding
        query_vector = generate_embedding(query, db=self.db)
        vector_str = "[" + ",".join(map(str, query_vector)) + "]"
        
        # Build SQL query with filters
        # Calculate relevance_score (similarity) and recency_weight on-the-fly
        # Prioritize chunks (chunk=true) over individual messages
        query_sql = """
            SELECT
                e.id,
                e.text,
                e.metadata,
                e.message_id,
                1 - (e.vector <=> CAST(:query_vector AS vector)) as similarity,
                CASE 
                    WHEN e.metadata->>'chunk' = 'true' THEN 1.2  -- Boost chunks by 20%
                    ELSE 1.0
                END as chunk_boost,
                CASE 
                    WHEN EXISTS (SELECT 1 FROM messages m WHERE m.id = e.message_id AND m.timestamp IS NOT NULL) THEN
                        -- Use message timestamp (most reliable)
                        EXP(-EXTRACT(EPOCH FROM (NOW() - (SELECT m2.timestamp FROM messages m2 WHERE m2.id = e.message_id))) / 2592000.0)
                    WHEN e.metadata->>'timestamp' IS NOT NULL AND e.metadata->>'timestamp' != 'null' THEN
                        -- Try to parse timestamp from metadata (ISO format)
                        EXP(-EXTRACT(EPOCH FROM (NOW() - (e.metadata->>'timestamp')::timestamptz)) / 2592000.0)
                    ELSE 0.5  -- Default recency weight if no timestamp
                END as recency_weight
            FROM embeddings e
            WHERE 1 - (e.vector <=> CAST(:query_vector AS vector)) >= :threshold
        """
        
        params = {
            "query_vector": vector_str,
            "threshold": self.threshold,
            "limit": self.limit
        }
        
        # Add filters
        if self.user_id:
            # Filter by user_id via message relationship OR metadata OR conversation_id
            # Chunks don't have message_id but have conversation_id that matches user's conversations
            query_sql += """
                AND (
                    EXISTS (
                        SELECT 1 FROM messages m
                        WHERE m.id = e.message_id
                        AND m.user_id = :user_id
                    )
                    OR e.metadata->>'user_id' = :user_id_str
                    OR EXISTS (
                        SELECT 1 FROM messages m2
                        WHERE m2.conversation_id = e.metadata->>'conversation_id'
                        AND m2.user_id = :user_id
                    )
                )
            """
            params["user_id"] = self.user_id
            params["user_id_str"] = str(self.user_id)
        
        if self.conversation_id:
            query_sql += " AND (e.metadata->>'conversation_id' = :conversation_id OR e.metadata->>'thread_id' = :conversation_id)"
            params["conversation_id"] = self.conversation_id
        
        # Filter by included_sources (list) or source (single, for backward compatibility)
        # None = all sources included, [] = no sources, [source1, ...] = only these sources
        if self.included_sources is not None:
            if len(self.included_sources) == 0:
                # Empty list means no sources - return empty result by adding impossible condition
                query_sql += " AND 1 = 0"  # This will make the query return no results
            else:
                # Filter by list of sources
                source_conditions = []
                for idx, src in enumerate(self.included_sources):
                    param_name = f"source_{idx}"
                    source_conditions.append(f"(e.metadata->>'source' = :{param_name} OR EXISTS (SELECT 1 FROM messages m WHERE m.id = e.message_id AND m.source = :{param_name}))")
                    params[param_name] = src
                if source_conditions:
                    query_sql += " AND (" + " OR ".join(source_conditions) + ")"
        elif self.source:
            # Backward compatibility: single source filter
            query_sql += " AND (e.metadata->>'source' = :source OR EXISTS (SELECT 1 FROM messages m WHERE m.id = e.message_id AND m.source = :source))"
            params["source"] = self.source
        
        # Order by combined score: (similarity * chunk_boost * recency_weight)
        # This prioritizes: relevant chunks that are recent
        query_sql += """
            ORDER BY (similarity * chunk_boost * recency_weight) DESC
            LIMIT :limit
        """
        
        # Execute query
        result = self.db.execute(sql_text(query_sql), params)
        
        # Convert to Documents with calculated scores
        documents = []
        for row in result:
            metadata = row.metadata or {}
            metadata['embedding_id'] = row.id
            metadata['message_id'] = row.message_id
            
            # Calculate scores on-the-fly
            relevance_score = float(row.similarity)
            recency_weight = float(row.recency_weight) if hasattr(row, 'recency_weight') else 1.0
            chunk_boost = float(row.chunk_boost) if hasattr(row, 'chunk_boost') else 1.0
            combined_score = relevance_score * chunk_boost * recency_weight
            
            # Store calculated scores in metadata (for debugging/monitoring)
            metadata['similarity'] = relevance_score
            metadata['relevance_score'] = relevance_score  # Alias for clarity
            metadata['recency_weight'] = recency_weight
            metadata['chunk_boost'] = chunk_boost
            metadata['combined_score'] = combined_score
            
            doc = Document(
                page_content=row.text,
                metadata=metadata
            )
            documents.append(doc)
        
        return documents


def get_vector_store_retriever(
    db: Session,
    user_id: Optional[int] = None,
    conversation_id: Optional[str] = None,
    source: Optional[str] = None,  # Deprecated: use included_sources instead
    included_sources: Optional[List[str]] = None,
    limit: int = 15,  # Increased from 10 to 15 for better context
    threshold: float = 0.15  # Lowered from 0.2 to 0.15 for better recall (especially for proper names and user info)
) -> MinimeeVectorStoreRetriever:
    """
    Create a retriever using Minimee's existing embeddings table
    
    Args:
        db: Database session
        user_id: Filter by user_id
        conversation_id: Filter by conversation_id
        source: Filter by source (whatsapp, gmail, etc.) - Deprecated: use included_sources instead
        included_sources: List of sources to include (whatsapp, gmail). None = all sources, [] = no sources, [source1, ...] = only these sources.
        limit: Maximum number of results
        threshold: Minimum similarity threshold (0-1)
    
    Returns:
        MinimeeVectorStoreRetriever instance
    """
    return MinimeeVectorStoreRetriever(
        db=db,
        user_id=user_id,
        conversation_id=conversation_id,
        source=source,
        included_sources=included_sources,
        limit=limit,
        threshold=threshold
    )


def create_documents_from_embeddings(
    db: Any,
    user_id: Optional[int] = None,
    conversation_id: Optional[str] = None,
    source: Optional[str] = None,
    limit: Optional[int] = None
) -> list[Document]:
    """
    Create LangChain Documents from existing embeddings in database
    
    This function reads from the existing embeddings table and converts
    them to LangChain Document format for use with the vector store.
    
    Args:
        db: Database session
        user_id: Filter by user_id (via metadata)
        conversation_id: Filter by conversation_id (via metadata)
        source: Filter by source (via metadata)
        limit: Limit number of documents
    
    Returns:
        List of LangChain Documents
    """
    from models import Embedding, Message
    from sqlalchemy import and_
    
    query = db.query(Embedding)
    
    # Build filters based on metadata
    filters = []
    if user_id:
        # Filter by user_id via message relationship or metadata
        filters.append(
            Embedding.meta_data['conversation_id'].astext.in_(
                db.query(Message.conversation_id).filter(Message.user_id == user_id).distinct()
            )
        )
    
    if conversation_id:
        filters.append(
            Embedding.meta_data['conversation_id'].astext == conversation_id
        )
    
    if source:
        filters.append(
            Embedding.meta_data['source'].astext == source
        )
    
    if filters:
        query = query.filter(and_(*filters))
    
    if limit:
        query = query.limit(limit)
    
    embeddings = query.all()
    
    documents = []
    for emb in embeddings:
        # Create Document with text and metadata
        metadata = emb.meta_data or {}
        metadata['embedding_id'] = emb.id
        metadata['message_id'] = emb.message_id
        
        doc = Document(
            page_content=emb.text,
            metadata=metadata
        )
        documents.append(doc)
    
    return documents

