"""
Embeddings listing and search endpoints
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from typing import Optional
from datetime import datetime
from db.database import get_db
from models import Embedding, Message
from schemas import EmbeddingResponse, EmbeddingsListResponse, EmbeddingMessageInfo

router = APIRouter(prefix="/embeddings", tags=["embeddings"])


@router.get("/models")
async def get_embedding_models():
    """
    Get all available embedding models with their details
    """
    models = [
        {
            "model": "sentence-transformers/all-MiniLM-L6-v2",
            "dimensions": 384,
            "description": "Fast and efficient model, best for speed",
            "size": "~90 MB",
            "available": True,
            "use_case": "Fast semantic search and similarity",
            "location_type": "local",
            "cost": "free"
        },
        {
            "model": "sentence-transformers/all-mpnet-base-v2",
            "dimensions": 768,
            "description": "Highest quality model, best for accuracy",
            "size": "~420 MB",
            "available": True,
            "use_case": "Best quality semantic search",
            "location_type": "local",
            "cost": "free"
        },
        {
            "model": "sentence-transformers/all-MiniLM-L12-v2",
            "dimensions": 384,
            "description": "Better quality than L6, still fast",
            "size": "~130 MB",
            "available": True,
            "use_case": "Balance between speed and quality",
            "location_type": "local",
            "cost": "free"
        },
        {
            "model": "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
            "dimensions": 768,
            "description": "Multilingual model supporting 50+ languages",
            "size": "~420 MB",
            "available": True,
            "use_case": "Multilingual semantic search",
            "location_type": "local",
            "cost": "free"
        },
        {
            "model": "sentence-transformers/distiluse-base-multilingual-cased",
            "dimensions": 512,
            "description": "Lightweight multilingual model",
            "size": "~170 MB",
            "available": True,
            "use_case": "Lightweight multilingual search",
            "location_type": "local",
            "cost": "free"
        },
    ]
    
    return {"models": models}


@router.get("", response_model=EmbeddingsListResponse)
async def get_embeddings(
    source: Optional[str] = Query(None, description="Filter by source: whatsapp, gmail, dashboard, or empty for all"),
    search: Optional[str] = Query(None, description="Search text in embedding content"),
    message_start_date: Optional[datetime] = Query(None, description="Filter by message timestamp (start date)"),
    message_end_date: Optional[datetime] = Query(None, description="Filter by message timestamp (end date)"),
    embedding_start_date: Optional[datetime] = Query(None, description="Filter by embedding created_at (start date)"),
    embedding_end_date: Optional[datetime] = Query(None, description="Filter by embedding created_at (end date)"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(50, ge=1, le=500, description="Items per page"),
    db: Session = Depends(get_db)
):
    """
    List embeddings with pagination, filtering, and search
    
    - **source**: Filter by source (whatsapp/gmail/dashboard). If not in metadata, tries to get from associated message
    - **search**: Search text in the embedding content (case-insensitive)
    - **message_start_date**: Filter messages by timestamp (start date)
    - **message_end_date**: Filter messages by timestamp (end date)
    - **embedding_start_date**: Filter embeddings by created_at (start date)
    - **embedding_end_date**: Filter embeddings by created_at (end date)
    - **page**: Page number (starts at 1)
    - **limit**: Items per page (max 500)
    """
    # Use shared query builder
    query = _build_embedding_query(
        db=db,
        source=source,
        search=search,
        message_start_date=message_start_date,
        message_end_date=message_end_date,
        embedding_start_date=embedding_start_date,
        embedding_end_date=embedding_end_date
    )
    
    # Get total count before pagination (need to reset query)
    total_query = query
    total = total_query.count()
    
    # Calculate pagination
    offset = (page - 1) * limit
    total_pages = (total + limit - 1) // limit if total > 0 else 0
    
    # Apply pagination and ordering
    results = query.order_by(Embedding.created_at.desc()).offset(offset).limit(limit).all()
    
    # Transform results to response format
    embeddings_data = []
    for embedding in results:
        # Determine source: priority to metadata->>'source', then message.source
        determined_source = None
        if embedding.meta_data and isinstance(embedding.meta_data, dict):
            determined_source = embedding.meta_data.get('source')
        
        if not determined_source and embedding.message:
            determined_source = embedding.message.source
        
        # Build message info if exists
        message_info = None
        if embedding.message_id and embedding.message:
            msg = embedding.message
            message_info = EmbeddingMessageInfo(
                id=msg.id,
                content=msg.content,
                sender=msg.sender,
                recipient=msg.recipient,
                recipients=msg.recipients if isinstance(msg.recipients, list) else None,
                source=msg.source,
                conversation_id=msg.conversation_id,
                timestamp=msg.timestamp
            )
        
        # Serialize metadata properly (handle SQLAlchemy JSONB)
        metadata_dict = None
        if embedding.meta_data is not None:
            if isinstance(embedding.meta_data, dict):
                metadata_dict = embedding.meta_data
            else:
                # Try to convert if it's a custom type
                try:
                    import json
                    metadata_dict = json.loads(str(embedding.meta_data)) if hasattr(embedding.meta_data, '__str__') else None
                except:
                    metadata_dict = None
        
        embeddings_data.append(
            EmbeddingResponse(
                id=embedding.id,
                text=embedding.text,
                source=determined_source,
                metadata=metadata_dict,
                message_id=embedding.message_id,
                message=message_info,
                created_at=embedding.created_at
            )
        )
    
    return EmbeddingsListResponse(
        embeddings=embeddings_data,
        total=total,
        page=page,
        limit=limit,
        total_pages=total_pages
    )


def _build_embedding_query(
    db: Session,
    source: Optional[str] = None,
    search: Optional[str] = None,
    message_start_date: Optional[datetime] = None,
    message_end_date: Optional[datetime] = None,
    embedding_start_date: Optional[datetime] = None,
    embedding_end_date: Optional[datetime] = None
):
    """
    Build embedding query with filters (used by both GET and DELETE endpoints)
    """
    from sqlalchemy.orm import joinedload
    from sqlalchemy import or_
    
    query = db.query(Embedding).options(joinedload(Embedding.message))
    query = query.outerjoin(Message, Embedding.message_id == Message.id)
    
    # Apply source filter
    if source:
        query = query.filter(
            or_(
                Embedding.meta_data['source'].astext == source,
                Message.source == source
            )
        )
    
    # Apply message date filters
    if message_start_date:
        query = query.filter(Message.timestamp >= message_start_date)
    if message_end_date:
        query = query.filter(Message.timestamp <= message_end_date)
    
    # Apply embedding date filters
    if embedding_start_date:
        query = query.filter(Embedding.created_at >= embedding_start_date)
    if embedding_end_date:
        query = query.filter(Embedding.created_at <= embedding_end_date)
    
    # Apply text search filter
    if search:
        query = query.filter(
            Embedding.text.ilike(f"%{search}%")
        )
    
    return query


@router.delete("")
async def delete_embeddings(
    source: Optional[str] = Query(None, description="Filter by source: whatsapp, gmail, dashboard, or empty for all"),
    search: Optional[str] = Query(None, description="Search text in embedding content"),
    message_start_date: Optional[datetime] = Query(None, description="Filter by message timestamp (start date)"),
    message_end_date: Optional[datetime] = Query(None, description="Filter by message timestamp (end date)"),
    embedding_start_date: Optional[datetime] = Query(None, description="Filter by embedding created_at (start date)"),
    embedding_end_date: Optional[datetime] = Query(None, description="Filter by embedding created_at (end date)"),
    db: Session = Depends(get_db)
):
    """
    Delete embeddings matching the specified filters
    
    Uses the same filters as GET /embeddings to ensure consistency.
    Returns count of deleted embeddings.
    """
    from services.logs_service import log_to_db
    
    try:
        # Build query with same filters
        query = _build_embedding_query(
            db=db,
            source=source,
            search=search,
            message_start_date=message_start_date,
            message_end_date=message_end_date,
            embedding_start_date=embedding_start_date,
            embedding_end_date=embedding_end_date
        )
        
        # Count before deletion
        count = query.count()
        
        if count == 0:
            return {
                "deleted": 0,
                "message": "No embeddings found matching the filters"
            }
        
        # Delete embeddings
        deleted_count = query.delete(synchronize_session=False)
        db.commit()
        
        log_to_db(
            db,
            "INFO",
            f"Deleted {deleted_count} embeddings",
            service="embeddings",
            metadata={
                "deleted_count": deleted_count,
                "filters": {
                    "source": source,
                    "search": search,
                    "message_start_date": message_start_date.isoformat() if message_start_date else None,
                    "message_end_date": message_end_date.isoformat() if message_end_date else None,
                    "embedding_start_date": embedding_start_date.isoformat() if embedding_start_date else None,
                    "embedding_end_date": embedding_end_date.isoformat() if embedding_end_date else None,
                }
            }
        )
        
        return {
            "deleted": deleted_count,
            "message": f"Successfully deleted {deleted_count} embedding(s)"
        }
    
    except Exception as e:
        db.rollback()
        log_to_db(db, "ERROR", f"Error deleting embeddings: {str(e)}", service="embeddings")
        raise HTTPException(status_code=500, detail=f"Error deleting embeddings: {str(e)}")

