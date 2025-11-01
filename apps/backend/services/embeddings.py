"""
Embedding generation service using sentence-transformers
"""
import time
from sentence_transformers import SentenceTransformer
from sqlalchemy.orm import Session
from typing import Optional
from models import Embedding, Message
from config import settings
from services.metrics import record_embedding_generation


# Load model once (singleton pattern)
_model: Optional[SentenceTransformer] = None


def get_embedding_model() -> SentenceTransformer:
    """Get or load embedding model"""
    global _model
    if _model is None:
        _model = SentenceTransformer(settings.embedding_model)
    return _model


def generate_embedding(text: str, db: Optional[Session] = None) -> list[float]:
    """
    Generate embedding vector for text
    Returns list of floats (384 dimensions by default)
    Tracks metrics: latency, text length
    """
    start_time = time.time()
    text_length = len(text)
    
    model = get_embedding_model()
    embedding = model.encode(text, convert_to_numpy=True)
    
    # Record metrics
    latency_ms = (time.time() - start_time) * 1000
    if db:
        record_embedding_generation(db, latency_ms, text_length)
    
    return embedding.tolist()


def store_embedding(
    db: Session,
    text: str,
    message_id: Optional[int] = None,
    metadata: Optional[dict] = None
) -> Embedding:
    """
    Generate and store embedding in database
    Supports both individual messages and chunks
    """
    vector = generate_embedding(text, db=db)
    
    # Convert list to pgvector format string
    vector_str = "[" + ",".join(map(str, vector)) + "]"
    
    # Serialize metadata to JSONB
    import json
    metadata_json = json.dumps(metadata) if metadata else None
    
    # Create embedding record using raw SQL for pgvector
    from sqlalchemy import text as sql_text
    result = db.execute(
        sql_text("""
            INSERT INTO embeddings (text, vector, metadata, message_id, created_at)
            VALUES (:text, :vector::vector, :metadata::jsonb, :message_id, NOW())
            RETURNING id
        """),
        {
            "text": text,
            "vector": vector_str,
            "metadata": metadata_json,
            "message_id": message_id
        }
    )
    embedding_id = result.scalar()
    
    # Note: Don't commit here - let caller manage transaction
    # This allows batch operations
    
    # Fetch the created embedding (without commit, use refresh if needed)
    embedding = db.query(Embedding).filter(Embedding.id == embedding_id).first()
    return embedding


def find_similar_messages(
    db: Session,
    query_text: str,
    limit: int = 10,
    threshold: float = 0.7
) -> list[tuple[Message, float]]:
    """
    Find similar messages using cosine similarity
    Returns list of (Message, similarity_score) tuples
    """
    query_vector = generate_embedding(query_text, db=db)
    vector_str = "[" + ",".join(map(str, query_vector)) + "]"

    # Use pgvector cosine similarity
    from sqlalchemy import text as sql_text
    query = sql_text("""
        SELECT m.id, m.content, m.sender, m.timestamp, m.source, 
               m.conversation_id, m.user_id, m.created_at,
               1 - (e.vector <=> :query_vector::vector) as similarity
        FROM embeddings e
        JOIN messages m ON e.message_id = m.id
        WHERE 1 - (e.vector <=> :query_vector::vector) >= :threshold
        ORDER BY e.vector <=> :query_vector::vector
        LIMIT :limit
    """)
    
    results = db.execute(
        query,
        {
            "query_vector": vector_str,
            "threshold": threshold,
            "limit": limit
        }
    )
    
    messages_with_scores = []
    for row in results:
        msg = Message(
            id=row.id,
            content=row.content,
            sender=row.sender,
            timestamp=row.timestamp,
            source=row.source,
            conversation_id=row.conversation_id,
            user_id=row.user_id,
            created_at=row.created_at
        )
        messages_with_scores.append((msg, float(row.similarity)))
    
    return messages_with_scores

