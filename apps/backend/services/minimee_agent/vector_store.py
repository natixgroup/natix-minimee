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
    source: Optional[str] = None
    limit: int = 10
    threshold: float = 0.2  # Lowered for better recall
    embeddings: Any = None  # MinimeeEmbeddings
    
    class Config:
        arbitrary_types_allowed = True
    
    def __init__(
        self,
        db: Session,
        user_id: Optional[int] = None,
        conversation_id: Optional[str] = None,
        source: Optional[str] = None,
        limit: int = 10,
        threshold: float = 0.2,  # Lowered from 0.3 to 0.2 for better recall
        **kwargs
    ):
        super().__init__(**kwargs)
        self.db = db
        self.user_id = user_id
        self.conversation_id = conversation_id
        self.source = source
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
        query_sql = """
            SELECT
                e.id,
                e.text,
                e.metadata,
                e.message_id,
                1 - (e.vector <=> CAST(:query_vector AS vector)) as similarity
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
        
        if self.source:
            query_sql += " AND (e.metadata->>'source' = :source OR EXISTS (SELECT 1 FROM messages m WHERE m.id = e.message_id AND m.source = :source))"
            params["source"] = self.source
        
        # Order by similarity and limit
        query_sql += """
            ORDER BY e.vector <=> CAST(:query_vector AS vector)
            LIMIT :limit
        """
        
        # Execute query
        result = self.db.execute(sql_text(query_sql), params)
        
        # Convert to Documents
        documents = []
        for row in result:
            metadata = row.metadata or {}
            metadata['embedding_id'] = row.id
            metadata['message_id'] = row.message_id
            metadata['similarity'] = float(row.similarity)
            
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
    source: Optional[str] = None,
    limit: int = 10,
    threshold: float = 0.2  # Lowered from 0.3 to 0.2 for better recall (especially for proper names)
) -> MinimeeVectorStoreRetriever:
    """
    Create a retriever using Minimee's existing embeddings table
    
    Args:
        db: Database session
        user_id: Filter by user_id
        conversation_id: Filter by conversation_id
        source: Filter by source (whatsapp, gmail, etc.)
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

