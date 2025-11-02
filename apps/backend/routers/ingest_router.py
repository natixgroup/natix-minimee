"""
Data ingestion endpoints
Enhanced with chunking, language detection, summarization
"""
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from datetime import datetime
import json
import asyncio
from db.database import get_db
from services.ingestion import ingest_whatsapp_file
from services.logs_service import log_to_db

router = APIRouter()


@router.post("/ingest/whatsapp-upload")
async def upload_whatsapp(
    file: UploadFile = File(...),
    user_id: int = Form(default=1),  # Get from FormData, default to 1
    db: Session = Depends(get_db)
):
    """
    Upload and parse WhatsApp conversation .txt file
    Enhanced pipeline:
    - Parse messages with proper date handling and emoji preservation
    - Detect language for each message
    - Chunk messages (3-5 per chunk)
    - Generate embeddings for chunks and messages (if available)
    - Generate summaries (TL;DR + tags) for chunks (if LLM available)
    
    Returns detailed statistics including any warnings about skipped steps.
    """
    # Validate file type
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    
    if not file.filename.endswith('.txt'):
        raise HTTPException(
            status_code=400, 
            detail="File must be a .txt file. Please export your WhatsApp conversation as a text file."
        )
    
    # Validate file size (max 50MB)
    file_size = 0
    try:
        content = await file.read()
        file_size = len(content)
        if file_size > 50 * 1024 * 1024:  # 50MB
            raise HTTPException(
                status_code=400,
                detail="File too large. Maximum size is 50MB. Please split your conversation into smaller files."
            )
        
        # Decode content
        try:
            text_content = content.decode('utf-8')
        except UnicodeDecodeError:
            # Try other common encodings
            try:
                text_content = content.decode('latin-1')
            except UnicodeDecodeError:
                raise HTTPException(
                    status_code=400,
                    detail="File encoding not supported. Please ensure your file is UTF-8 encoded."
                )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Error reading file: {str(e)}"
        )
    
    # Validate user_id
    if user_id < 1:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid user_id: {user_id}"
        )
    
    try:
        log_to_db(
            db,
            "INFO",
            f"Starting WhatsApp upload: file={file.filename}, size={file_size} bytes, user_id={user_id}",
            service="ingest"
        )
        
        # Use enhanced ingestion service
        stats = ingest_whatsapp_file(
            db=db,
            file_content=text_content,
            user_id=user_id
        )
        
        # Build response with warnings if any steps were skipped
        warnings = []
        if stats.get('embeddings_skipped', 0) > 0:
            warnings.append(f"{stats['embeddings_skipped']} embeddings skipped (embedding model may not be ready)")
        if stats.get('summaries_skipped', 0) > 0:
            warnings.append(f"{stats['summaries_skipped']} summaries skipped (LLM may not be ready)")
        
        log_to_db(
            db,
            "INFO",
            f"WhatsApp upload complete: {stats['messages_created']} messages, "
            f"{stats['chunks_created']} chunks, {stats.get('summaries_created', 0)} summaries, "
            f"{stats.get('embeddings_created', 0)} embeddings. Warnings: {len(warnings)}",
            service="ingest"
        )
        
        response = {
            "message": "Successfully imported WhatsApp conversation",
            "conversation_id": stats['conversation_id'],
            "stats": {
                "messages_created": stats['messages_created'],
                "chunks_created": stats['chunks_created'],
                "summaries_created": stats.get('summaries_created', 0),
                "embeddings_created": stats.get('embeddings_created', 0),
            }
        }
        
        if warnings:
            response["warnings"] = warnings
        
        return response
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        error_detail = f"WhatsApp upload error: {str(e)}"
        log_to_db(db, "ERROR", error_detail, service="ingest")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process WhatsApp file: {str(e)}"
        )


@router.post("/ingest/whatsapp-upload-stream")
async def upload_whatsapp_stream(
    file: UploadFile = File(...),
    user_id: int = Form(default=1),
    db: Session = Depends(get_db)
):
    """
    Upload and parse WhatsApp conversation .txt file with real-time progress updates via SSE
    
    Streams progress updates including:
    - Parsing progress (x/y messages)
    - Saving messages progress
    - Chunking progress
    - Embedding progress (x/y vectorized)
    - Summarization progress
    """
    # Validate file type
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    
    if not file.filename.endswith('.txt'):
        raise HTTPException(
            status_code=400, 
            detail="File must be a .txt file. Please export your WhatsApp conversation as a text file."
        )
    
    # Validate file size (max 50MB)
    file_size = 0
    try:
        content = await file.read()
        file_size = len(content)
        if file_size > 50 * 1024 * 1024:  # 50MB
            raise HTTPException(
                status_code=400,
                detail="File too large. Maximum size is 50MB. Please split your conversation into smaller files."
            )
        
        # Decode content
        try:
            text_content = content.decode('utf-8')
        except UnicodeDecodeError:
            try:
                text_content = content.decode('latin-1')
            except UnicodeDecodeError:
                raise HTTPException(
                    status_code=400,
                    detail="File encoding not supported. Please ensure your file is UTF-8 encoded."
                )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Error reading file: {str(e)}"
        )
    
    # Validate user_id
    if user_id < 1:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid user_id: {user_id}"
        )
    
    async def event_generator():
        """Generator that streams progress updates"""
        progress_queue = asyncio.Queue()
        error_occurred = [False]
        final_result = [None]
        loop = asyncio.get_event_loop()
        
        def progress_callback(step: str, data: dict):
            """Callback to send progress updates to queue (thread-safe)"""
            try:
                # Schedule put in event loop (works from sync code)
                asyncio.run_coroutine_threadsafe(
                    progress_queue.put({
                        "type": "progress",
                        "step": step,
                        "data": data
                    }),
                    loop
                )
            except Exception:
                pass  # Ignore if queue issues
        
        def process_upload_sync():
            """Process upload synchronously in thread"""
            try:
                # Create a new DB session for this thread
                from db.database import SessionLocal
                thread_db = SessionLocal()
                try:
                    stats = ingest_whatsapp_file(
                        db=thread_db,
                        file_content=text_content,
                        user_id=user_id,
                        progress_callback=progress_callback
                    )
                    
                    warnings = []
                    if stats.get('embeddings_skipped', 0) > 0:
                        warnings.append(f"{stats['embeddings_skipped']} embeddings skipped (embedding model may not be ready)")
                    if stats.get('summaries_skipped', 0) > 0:
                        warnings.append(f"{stats['summaries_skipped']} summaries skipped (LLM may not be ready)")
                    
                    result = {
                        "type": "complete",
                        "message": "Successfully imported WhatsApp conversation",
                        "conversation_id": stats['conversation_id'],
                        "stats": {
                            "messages_created": stats['messages_created'],
                            "chunks_created": stats['chunks_created'],
                            "summaries_created": stats.get('summaries_created', 0),
                            "embeddings_created": stats.get('embeddings_created', 0),
                        },
                        "warnings": warnings if warnings else None
                    }
                    final_result[0] = result
                    asyncio.run_coroutine_threadsafe(progress_queue.put(result), loop)
                    
                finally:
                    thread_db.close()
                    
            except Exception as e:
                error_occurred[0] = True
                error_msg = {
                    "type": "error",
                    "message": f"Failed to process WhatsApp file: {str(e)}"
                }
                asyncio.run_coroutine_threadsafe(progress_queue.put(error_msg), loop)
        
        # Run ingestion in thread pool to avoid blocking
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            loop.run_in_executor(executor, process_upload_sync)
        
        # Stream updates
        try:
            while True:
                try:
                    # Wait for progress update with timeout (increased to reduce CPU)
                    update = await asyncio.wait_for(progress_queue.get(), timeout=0.5)
                    
                    yield f"data: {json.dumps(update)}\n\n"
                    
                    # If complete or error, break
                    if update.get("type") in ("complete", "error"):
                        break
                        
                except asyncio.TimeoutError:
                    # Send heartbeat less frequently to reduce CPU (every ~5 seconds)
                    # We check every 0.5s but only send heartbeat every 5 seconds
                    import time
                    if not hasattr(event_generator, '_last_heartbeat'):
                        event_generator._last_heartbeat = time.time()
                    
                    current_time = time.time()
                    if current_time - event_generator._last_heartbeat >= 5:
                        yield ": heartbeat\n\n"
                        event_generator._last_heartbeat = current_time
                    
                    continue
                    
        finally:
            # Ensure final message is sent
            if final_result[0] and not error_occurred[0]:
                yield f"data: {json.dumps(final_result[0])}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
