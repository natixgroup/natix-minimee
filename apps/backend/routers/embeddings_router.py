"""
Embeddings listing and search endpoints
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_, func, distinct
from typing import Optional, Dict, Any
from datetime import datetime
from db.database import get_db
from models import Embedding, Message, GmailThread, IngestionJob, Contact, ActionLog
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


@router.get("/stats-by-source")
async def get_embeddings_stats_by_source(
    user_id: int = Query(1, description="User ID"),
    db: Session = Depends(get_db)
):
    """
    Get statistics by data source (Gmail, WhatsApp, etc.)
    Returns: threads/conversations count, messages count, date ranges, last import info
    """
    stats: Dict[str, Any] = {}
    
    # Gmail stats - use SQL aggregation for efficiency
    gmail_threads_count = db.query(func.count(GmailThread.id)).filter(
        GmailThread.user_id == user_id
    ).scalar() or 0
    
    gmail_messages_count = db.query(func.count(Message.id)).filter(
        Message.source == "gmail",
        Message.user_id == user_id
    ).scalar() or 0
    
    if gmail_messages_count > 0:
        # Get date range using SQL aggregation
        gmail_date_range = db.query(
            func.min(Message.timestamp).label('oldest'),
            func.max(Message.timestamp).label('newest')
        ).filter(
            Message.source == "gmail",
            Message.user_id == user_id
        ).first()
        
        oldest_gmail = gmail_date_range.oldest if gmail_date_range else None
        newest_gmail = gmail_date_range.newest if gmail_date_range else None
        
        # Get last import job for Gmail
        last_gmail_job = db.query(IngestionJob).filter(
            IngestionJob.user_id == user_id,
            IngestionJob.progress['source'].astext == 'gmail'
        ).order_by(IngestionJob.created_at.desc()).first()
        
        stats["gmail"] = {
            "threads_count": gmail_threads_count,
            "messages_count": gmail_messages_count,
            "oldest_date": oldest_gmail.isoformat() if oldest_gmail else None,
            "newest_date": newest_gmail.isoformat() if newest_gmail else None,
            "last_import_date": last_gmail_job.created_at.isoformat() if last_gmail_job else None,
            "last_import_type": "bulk" if last_gmail_job else None
        }
    else:
        stats["gmail"] = {
            "threads_count": 0,
            "messages_count": 0,
            "oldest_date": None,
            "newest_date": None,
            "last_import_date": None,
            "last_import_type": None
        }
    
    # WhatsApp stats - use SQL aggregation for efficiency
    whatsapp_messages_count = db.query(func.count(Message.id)).filter(
        Message.source == "whatsapp",
        Message.user_id == user_id
    ).scalar() or 0
    
    if whatsapp_messages_count > 0:
        # Get unique conversation_ids count using SQL
        conversations_count = db.query(func.count(distinct(Message.conversation_id))).filter(
            Message.source == "whatsapp",
            Message.user_id == user_id,
            Message.conversation_id.isnot(None)
        ).scalar() or 0
        
        # Get unique interlocutors count (exclude self and system messages)
        unique_interlocutors = db.query(func.count(distinct(Message.sender))).filter(
            Message.source == "whatsapp",
            Message.user_id == user_id,
            Message.sender.isnot(None),
            Message.sender != 'Tarik',  # Exclude self
            ~Message.sender.like('%@s.whatsapp.net'),  # Exclude phone numbers
            ~Message.sender.like('Minimee%'),  # Exclude system
            ~Message.sender.like('dashboard-%')  # Exclude system
        ).scalar() or 0
        
        # Get date range using SQL aggregation
        whatsapp_date_range = db.query(
            func.min(Message.timestamp).label('oldest'),
            func.max(Message.timestamp).label('newest')
        ).filter(
            Message.source == "whatsapp",
            Message.user_id == user_id
        ).first()
        
        oldest_whatsapp = whatsapp_date_range.oldest if whatsapp_date_range else None
        newest_whatsapp = whatsapp_date_range.newest if whatsapp_date_range else None
        
        # Get last import job for WhatsApp
        last_whatsapp_job = db.query(IngestionJob).filter(
            IngestionJob.user_id == user_id,
            IngestionJob.progress['source'].astext == 'whatsapp'
        ).order_by(IngestionJob.created_at.desc()).first()
        
        stats["whatsapp"] = {
            "conversations_count": conversations_count,
            "interlocutors_count": unique_interlocutors,
            "messages_count": whatsapp_messages_count,
            "oldest_date": oldest_whatsapp.isoformat() if oldest_whatsapp else None,
            "newest_date": newest_whatsapp.isoformat() if newest_whatsapp else None,
            "last_import_date": last_whatsapp_job.created_at.isoformat() if last_whatsapp_job else None,
            "last_import_type": "bulk" if last_whatsapp_job else None
        }
    else:
        stats["whatsapp"] = {
            "conversations_count": 0,
            "interlocutors_count": 0,
            "messages_count": 0,
            "oldest_date": None,
            "newest_date": None,
            "last_import_date": None,
            "last_import_type": None
        }
    
    return {"stats": stats}


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
    user_id: int = Query(1, description="User ID"),
    db: Session = Depends(get_db)
):
    """
    Delete embeddings matching the specified filters
    
    If source is 'whatsapp', also deletes all WhatsApp messages and conversations associated with the deleted embeddings.
    Uses the same filters as GET /embeddings to ensure consistency.
    Returns count of deleted embeddings and related data.
    """
    from services.logs_service import log_to_db
    
    try:
        # Build query with same filters (this includes joins)
        query = _build_embedding_query(
            db=db,
            source=source,
            search=search,
            message_start_date=message_start_date,
            message_end_date=message_end_date,
            embedding_start_date=embedding_start_date,
            embedding_end_date=embedding_end_date
        )
        
        # Get embeddings with their messages before deletion
        embeddings_to_delete = query.all()
        count = len(embeddings_to_delete)
        
        if count == 0:
            return {
                "deleted": 0,
                "message": "No embeddings found matching the filters"
            }
        
        # If deleting WhatsApp embeddings, collect conversation_ids to delete
        whatsapp_conversation_ids = set()
        if source == "whatsapp" or (source is None and any(
            (emb.message and emb.message.source == "whatsapp") or 
            (emb.meta_data and isinstance(emb.meta_data, dict) and emb.meta_data.get('source') == 'whatsapp')
            for emb in embeddings_to_delete
        )):
            for emb in embeddings_to_delete:
                if emb.message and emb.message.source == "whatsapp" and emb.message.conversation_id:
                    whatsapp_conversation_ids.add(emb.message.conversation_id)
                elif emb.meta_data and isinstance(emb.meta_data, dict):
                    conv_id = emb.meta_data.get('conversation_id')
                    if conv_id:
                        whatsapp_conversation_ids.add(conv_id)
        
        # Delete embeddings
        embedding_ids = [emb.id for emb in embeddings_to_delete]
        deleted_embeddings = db.query(Embedding).filter(Embedding.id.in_(embedding_ids)).delete(synchronize_session=False)
        
        # If WhatsApp, delete associated messages and conversations
        deleted_messages = 0
        deleted_contacts = 0
        if whatsapp_conversation_ids:
            # Get all message IDs from these conversations
            whatsapp_messages = db.query(Message).filter(
                Message.conversation_id.in_(whatsapp_conversation_ids),
                Message.source == "whatsapp",
                Message.user_id == user_id
            ).all()
            message_ids = [msg.id for msg in whatsapp_messages]
            
            if message_ids:
                # Delete ActionLogs first
                db.query(ActionLog).filter(ActionLog.message_id.in_(message_ids)).delete(synchronize_session=False)
                
                # Delete remaining embeddings linked to these messages
                db.query(Embedding).filter(Embedding.message_id.in_(message_ids)).delete(synchronize_session=False)
                
                # Delete messages
                deleted_messages = db.query(Message).filter(
                    Message.id.in_(message_ids)
                ).delete(synchronize_session=False)
                
                # Delete contacts associated with these conversations
                deleted_contacts = db.query(Contact).filter(
                    Contact.conversation_id.in_(whatsapp_conversation_ids),
                    Contact.user_id == user_id
                ).delete(synchronize_session=False)
        
        db.commit()
        
        log_to_db(
            db,
            "INFO",
            f"Deleted {deleted_embeddings} embeddings" + 
            (f", {deleted_messages} WhatsApp messages, {deleted_contacts} contacts" if whatsapp_conversation_ids else ""),
            service="embeddings"
        )
        
        return {
            "deleted": deleted_embeddings,
            "deleted_messages": deleted_messages if whatsapp_conversation_ids else None,
            "deleted_contacts": deleted_contacts if whatsapp_conversation_ids else None,
            "deleted_conversations": len(whatsapp_conversation_ids) if whatsapp_conversation_ids else None,
            "message": f"Deleted {deleted_embeddings} embeddings" + 
                      (f", {deleted_messages} WhatsApp messages from {len(whatsapp_conversation_ids)} conversations" if whatsapp_conversation_ids else "")
        }
    
    except Exception as e:
        db.rollback()
        log_to_db(db, "ERROR", f"Error deleting embeddings: {str(e)}", service="embeddings")
        raise HTTPException(status_code=500, detail=f"Error deleting embeddings: {str(e)}")

