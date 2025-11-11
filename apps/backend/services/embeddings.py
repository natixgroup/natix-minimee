"""
Embedding generation service using sentence-transformers
"""
import time
from sentence_transformers import SentenceTransformer
from sqlalchemy.orm import Session
from typing import Optional, Dict
from datetime import datetime
from models import Embedding, Message
from config import settings
from services.metrics import record_embedding_generation
from services.action_logger import log_action_context
from services.language_detector import detect_language


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


def _calculate_temporal_metadata(timestamp: datetime) -> Dict:
    """
    Calculate temporal metadata from timestamp
    Returns: period_label, time_range, year, month, season
    """
    year = timestamp.year
    month = timestamp.month
    
    # Determine season
    if month in [12, 1, 2]:
        season = "hiver"
        season_en = "winter"
    elif month in [3, 4, 5]:
        season = "printemps"
        season_en = "spring"
    elif month in [6, 7, 8]:
        season = "été"
        season_en = "summer"
    else:  # 9, 10, 11
        season = "automne"
        season_en = "autumn"
    
    # Period label (e.g., "printemps 2023")
    period_label = f"{season} {year}"
    
    # Time range for the season
    if month in [12, 1, 2]:
        start_month = 12
        end_month = 2
        start_year = year if month != 12 else year - 1
        end_year = year if month != 12 else year
    elif month in [3, 4, 5]:
        start_month = 3
        end_month = 5
        start_year = year
        end_year = year
    elif month in [6, 7, 8]:
        start_month = 6
        end_month = 8
        start_year = year
        end_year = year
    else:  # 9, 10, 11
        start_month = 9
        end_month = 11
        start_year = year
        end_year = year
    
    # Format time range (e.g., "2023-03-01 → 2023-05-31")
    from datetime import date
    start_date = date(start_year, start_month, 1)
    # Get last day of end month
    if end_month == 12:
        end_date = date(end_year, end_month, 31)
    else:
        from calendar import monthrange
        last_day = monthrange(end_year, end_month)[1]
        end_date = date(end_year, end_month, last_day)
    
    time_range = f"{start_date.isoformat()} → {end_date.isoformat()}"
    
    return {
        'period_label': period_label,
        'time_range': time_range,
        'year': year,
        'month': month,
        'season': season
    }


def build_embedding_metadata(
    message: Message,
    language: Optional[str] = None,
    chunk: bool = False,
    start_timestamp: Optional[datetime] = None,
    end_timestamp: Optional[datetime] = None,
    **extra_metadata
) -> Dict:
    """
    Build standard metadata dict for embedding from a Message object
    Includes: sender, recipient, recipients, source, conversation_id, language, timestamp, chunk
    Also includes temporal metadata: period_label, time_range, year, month, season
    """
    msg_timestamp = message.timestamp if message.timestamp else datetime.utcnow()
    
    metadata = {
        'sender': message.sender,
        'source': message.source,
        'conversation_id': message.conversation_id,
        'chunk': 'true' if chunk else 'false',
        'timestamp': msg_timestamp.isoformat(),
    }
    
    # Add temporal metadata
    temporal_meta = _calculate_temporal_metadata(msg_timestamp)
    metadata.update(temporal_meta)
    
    # If block has start/end timestamps, use them for time_range
    if start_timestamp and end_timestamp:
        metadata['time_range'] = f"{start_timestamp.date().isoformat()} → {end_timestamp.date().isoformat()}"
        # Recalculate period_label based on start timestamp
        start_temporal = _calculate_temporal_metadata(start_timestamp)
        metadata['period_label'] = start_temporal['period_label']
    
    # Add recipient info (for 1-1 conversations)
    if message.recipient:
        metadata['recipient'] = message.recipient
    
    # Add recipients list (for group conversations)
    if message.recipients:
        metadata['recipients'] = message.recipients
    
    # Add language (detect if not provided)
    if language is None and message.content:
        detected_lang = detect_language(message.content)
        if detected_lang:
            metadata['language'] = detected_lang
    elif language:
        metadata['language'] = language
    
    # Add any extra metadata
    metadata.update(extra_metadata)
    
    return metadata


def store_embedding(
    db: Session,
    text: str,
    message_id: Optional[int] = None,
    metadata: Optional[dict] = None,
    request_id: Optional[str] = None,
    user_id: Optional[int] = None,
    message: Optional[Message] = None
) -> Embedding:
    """
    Generate and store embedding in database
    Supports both individual messages and chunks
    
    Args:
        message: Optional Message object to auto-generate metadata from
        metadata: Optional dict to override or supplement auto-generated metadata
    """
    # Auto-generate metadata from message if provided and metadata not explicitly set
    if message and metadata is None:
        metadata = build_embedding_metadata(message)
    elif message and metadata:
        # Merge: start with auto-generated, then override with provided metadata
        auto_metadata = build_embedding_metadata(message)
        auto_metadata.update(metadata)
        metadata = auto_metadata
    
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

