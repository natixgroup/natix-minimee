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
from services.action_logger import log_action_context


# Load model once (singleton pattern)
_model: Optional[SentenceTransformer] = None


def get_embedding_model() -> SentenceTransformer:
    """Get or load embedding model"""
    global _model
    if _model is None:
        _model = SentenceTransformer(settings.embedding_model)
    return _model


def generate_embedding(text: str, db: Optional[Session] = None, request_id: Optional[str] = None, user_id: Optional[int] = None) -> list[float]:
    """
    Generate embedding vector for text
    Returns list of floats (384 dimensions by default)
    Tracks metrics: latency, text length
    """
    model_instance = get_embedding_model()
    model_name = settings.embedding_model
    text_length = len(text)
    
    if db:
        with log_action_context(
            db=db,
            action_type="vectorization",
            model=model_name,
            input_data={
                "text": text[:500],  # Limiter la taille
                "text_length": text_length
            },
            request_id=request_id,
            user_id=user_id,
            metadata={"embedding_dim": 384}
        ) as log:
            embedding = model_instance.encode(text, convert_to_numpy=True)
            log.set_output({
                "embedding_dim": len(embedding),
                "text_length": text_length
            })
    else:
        embedding = model_instance.encode(text, convert_to_numpy=True)
    
    # Record metrics
    if db:
        # Note: duration déjà mesuré par log_action_context
        record_embedding_generation(db, 0, text_length)  # Metrics service garde sa logique
    
    return embedding.tolist()


def store_embedding(
    db: Session,
    text: str,
    message_id: Optional[int] = None,
    metadata: Optional[dict] = None,
    request_id: Optional[str] = None,
    user_id: Optional[int] = None
) -> Embedding:
    """
    Generate and store embedding in database
    Supports both individual messages and chunks
    """
    vector = generate_embedding(text, db=db, request_id=request_id, user_id=user_id)
    
    # Convert list to pgvector format string
    vector_str = "[" + ",".join(map(str, vector)) + "]"
    
    # Serialize metadata to JSONB
    import json
    metadata_json = json.dumps(metadata) if metadata else None
    
    # Create embedding record using raw SQL for pgvector
    from sqlalchemy import text as sql_text
    # Use bindparam to properly handle pgvector casting
    stmt = sql_text("""
        INSERT INTO embeddings (text, vector, metadata, message_id, created_at)
        VALUES (:text, CAST(:vector AS vector), CAST(:metadata AS jsonb), :message_id, NOW())
        RETURNING id
    """).bindparams(
        text=text,
        vector=vector_str,
        metadata=metadata_json if metadata_json else None,
        message_id=message_id
    )
    result = db.execute(stmt)
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
               1 - (e.vector <=> CAST(:query_vector AS vector)) as similarity
        FROM embeddings e
        JOIN messages m ON e.message_id = m.id
        WHERE 1 - (e.vector <=> CAST(:query_vector AS vector)) >= :threshold
        ORDER BY e.vector <=> CAST(:query_vector AS vector)
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

