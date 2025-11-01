"""
Data ingestion endpoints
Enhanced with chunking, language detection, summarization
"""
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from db.database import get_db
from services.ingestion import ingest_whatsapp_file
from services.logs_service import log_to_db

router = APIRouter()


@router.post("/ingest/whatsapp-upload")
async def upload_whatsapp(
    file: UploadFile = File(...),
    user_id: int = 1,  # TODO: Get from auth
    db: Session = Depends(get_db)
):
    """
    Upload and parse WhatsApp conversation .txt file
    Enhanced pipeline:
    - Parse messages with proper date handling and emoji preservation
    - Detect language for each message
    - Chunk messages (3-5 per chunk)
    - Generate embeddings for chunks and messages
    - Generate summaries (TL;DR + tags) for chunks
    """
    if not file.filename or not file.filename.endswith('.txt'):
        raise HTTPException(status_code=400, detail="File must be .txt")
    
    try:
        content = await file.read()
        text_content = content.decode('utf-8')
        
        # Use enhanced ingestion service
        stats = ingest_whatsapp_file(
            db=db,
            file_content=text_content,
            user_id=user_id
        )
        
        log_to_db(
            db,
            "INFO",
            f"WhatsApp upload complete: {stats['messages_created']} messages, "
            f"{stats['chunks_created']} chunks, {stats['summaries_created']} summaries",
            service="ingest"
        )
        
        return {
            "message": "Successfully imported WhatsApp conversation",
            "conversation_id": stats['conversation_id'],
            "stats": {
                "messages_created": stats['messages_created'],
                "chunks_created": stats['chunks_created'],
                "summaries_created": stats['summaries_created'],
                "embeddings_created": stats['embeddings_created'],
            }
        }
    
    except Exception as e:
        db.rollback()
        log_to_db(db, "ERROR", f"WhatsApp upload error: {str(e)}", service="ingest")
        raise HTTPException(status_code=500, detail=str(e))
