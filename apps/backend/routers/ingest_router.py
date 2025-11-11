"""
Data ingestion endpoints
Enhanced with chunking, language detection, summarization
"""
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Form, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, distinct
from datetime import datetime
from typing import Optional, List
import json
import asyncio
from db.database import get_db
from services.ingestion import ingest_whatsapp_file
from services.logs_service import log_to_db
from services.contact_detector import detect_contact_from_messages
from services.whatsapp_parser import parse_whatsapp_export
from services.ingestion_job import ingestion_job_manager
from services.websocket_manager import websocket_manager
from models import Message, Embedding, Summary, Contact, IngestionJob, RelationType
from schemas import ContactCreate, ContactResponse, ContactDetectionResponse, IngestionJobResponse, RelationTypeResponse

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
        
        # Send initial update immediately to establish SSE connection
        initial_update = {
            "type": "progress",
            "step": "parsing",
            "data": {
                "step": "parsing",
                "message": "File received. Starting processing...",
                "current": 0,
                "total": 0,
                "percent": 0.0
            }
        }
        yield f"data: {json.dumps(initial_update)}\n\n"
        
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
                
                # Capture detailed error information
                import traceback
                error_type = type(e).__name__
                error_message = str(e)
                traceback_summary = ''.join(traceback.format_exception(type(e), e, e.__traceback__)[-3:])  # Last 3 lines
                
                # Log error to database if possible
                try:
                    from services.logs_service import log_to_db
                    log_to_db(
                        thread_db,
                        "ERROR",
                        f"WhatsApp upload failed: {error_type}: {error_message}",
                        service="ingest",
                        metadata={
                            "error_type": error_type,
                            "error_message": error_message,
                            "traceback": traceback_summary
                        }
                    )
                except Exception:
                    # If logging fails, continue anyway
                    pass
                
                # Send detailed error message to queue
                error_msg = {
                    "type": "error",
                    "message": f"Failed to process WhatsApp file: {error_type}: {error_message}",
                    "error_type": error_type,
                    "error_details": traceback_summary if len(traceback_summary) < 500 else traceback_summary[:500] + "..."
                }
                asyncio.run_coroutine_threadsafe(progress_queue.put(error_msg), loop)
        
        # Run ingestion in thread pool to avoid blocking
        # Limit to 1 thread to avoid CPU saturation
        import concurrent.futures
        executor = None
        future = None
        timeout_task = None
        
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                # Start processing in background thread
                future = loop.run_in_executor(executor, process_upload_sync)
                
                # Monitor future with timeout (10 minutes)
                async def monitor_timeout():
                    """Monitor the future and send timeout error if it takes too long"""
                    try:
                        # Wait for future to complete with 10 minute timeout
                        await asyncio.wait_for(asyncio.wrap_future(future), timeout=600)
                    except asyncio.TimeoutError:
                        # Timeout occurred - send error to queue
                        error_occurred[0] = True
                        timeout_error = {
                            "type": "error",
                            "message": "Upload timeout after 10 minutes. File may be too large. Please try with a smaller file or split your conversation."
                        }
                        await progress_queue.put(timeout_error)
                    except Exception as e:
                        # Other error - already handled in process_upload_sync
                        pass
                
                # Start timeout monitor task
                timeout_task = asyncio.create_task(monitor_timeout())
                
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
                            
                            # Check if timeout task completed (error occurred)
                            if timeout_task.done():
                                try:
                                    await timeout_task
                                except Exception:
                                    pass
                                if error_occurred[0]:
                                    break
                            
                            continue
                            
                finally:
                    # Cancel timeout task if still running
                    if timeout_task and not timeout_task.done():
                        timeout_task.cancel()
                        try:
                            await timeout_task
                        except asyncio.CancelledError:
                            pass
                    
                    # Ensure final message is sent
                    if final_result[0] and not error_occurred[0]:
                        yield f"data: {json.dumps(final_result[0])}\n\n"
        except Exception as e:
            # If executor fails to start, send error
            error_occurred[0] = True
            error_msg = {
                "type": "error",
                "message": f"Failed to start upload processing: {str(e)}"
            }
            yield f"data: {json.dumps(error_msg)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("/ingest/whatsapp-history")
async def get_whatsapp_import_history(
    user_id: Optional[int] = Query(None, description="Filter by user_id"),
    limit: int = Query(10, ge=1, le=100, description="Number of results per page"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: Session = Depends(get_db)
):
    """
    Get import history for WhatsApp conversations
    Returns aggregated stats per conversation_id
    """
    # Base query: messages with source='whatsapp'
    query = db.query(Message).filter(Message.source == "whatsapp")
    
    if user_id:
        query = query.filter(Message.user_id == user_id)
    
    # Group by conversation_id and aggregate
    # Use SQLAlchemy's func for aggregation
    results = (
        db.query(
            Message.conversation_id,
            func.count(Message.id).label("messages_count"),
            func.min(Message.created_at).label("first_import"),
            func.max(Message.created_at).label("last_import"),
        )
        .filter(Message.source == "whatsapp")
        .group_by(Message.conversation_id)
    )
    
    if user_id:
        results = results.filter(Message.user_id == user_id)
    
    # Get total count for pagination
    total_count = results.count()
    
    # Apply pagination
    results = results.order_by(func.max(Message.created_at).desc()).offset(offset).limit(limit).all()
    
    # Build response with detailed stats
    history_items = []
    for result in results:
        conversation_id = result.conversation_id
        
        # Count embeddings for this conversation
        # Embeddings linked to messages via message_id
        embeddings_count = (
            db.query(func.count(Embedding.id))
            .join(Message, Embedding.message_id == Message.id)
            .filter(Message.conversation_id == conversation_id)
            .filter(Message.source == "whatsapp")
            .scalar() or 0
        )
        
        # Count summaries for this conversation
        summaries_count = (
            db.query(func.count(Summary.id))
            .filter(Summary.conversation_id == conversation_id)
            .scalar() or 0
        )
        
        # Estimate chunks: count embeddings with chunk metadata OR use summaries as proxy
        # Chunks are embeddings with metadata chunk=true (but can also be estimated from summaries)
        chunks_from_embeddings = (
            db.query(func.count(Embedding.id))
            .join(Message, Embedding.message_id == Message.id)
            .filter(Message.conversation_id == conversation_id)
            .filter(Message.source == "whatsapp")
            .filter(Embedding.meta_data['chunk'].astext == 'true')
            .scalar() or 0
        )
        
        # Use summaries count as chunks (1 summary = 1 chunk) or embeddings with chunk metadata
        chunks_count = max(chunks_from_embeddings, summaries_count)
        
        history_items.append({
            "conversation_id": conversation_id,
            "messages_count": result.messages_count,
            "embeddings_count": embeddings_count,
            "chunks_count": chunks_count,
            "summaries_count": summaries_count,
            "first_import": result.first_import.isoformat() if result.first_import else None,
            "last_import": result.last_import.isoformat() if result.last_import else None,
        })
    
    return {
        "items": history_items,
        "total": total_count,
        "limit": limit,
        "offset": offset,
        "has_more": (offset + limit) < total_count
    }


@router.post("/ingest/whatsapp-detect-contact", response_model=ContactDetectionResponse)
async def detect_contact(
    file: UploadFile = File(...),
    user_id: int = Form(default=1),
    db: Session = Depends(get_db)
):
    """
    Detect contact information from WhatsApp file after initial parsing
    Returns pre-filled contact data for the form
    """
    if not file.filename or not file.filename.endswith('.txt'):
        raise HTTPException(status_code=400, detail="File must be a .txt file")
    
    try:
        content = await file.read()
        text_content = content.decode('utf-8')
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error reading file: {str(e)}")
    
    # Parse messages (quick parse, no full ingestion)
    parsed_messages = parse_whatsapp_export(text_content)
    
    if not parsed_messages:
        raise HTTPException(status_code=400, detail="No messages found in file")
    
    # Detect contact
    contact_data = detect_contact_from_messages(parsed_messages, user_id)
    
    return ContactDetectionResponse(**contact_data)


@router.get("/ingest/relation-types", response_model=List[RelationTypeResponse])
async def get_relation_types(
    category: Optional[str] = Query(None, description="Filter by category: 'personnel' or 'professionnel'"),
    db: Session = Depends(get_db)
):
    """
    Get available relation types, optionally filtered by category
    """
    query = db.query(RelationType).filter(RelationType.is_active == True)
    
    if category:
        query = query.filter(RelationType.category == category)
    
    relation_types = query.order_by(RelationType.category, RelationType.display_order).all()
    return relation_types


@router.post("/ingest/whatsapp-save-contact", response_model=ContactResponse)
async def save_contact(
    contact_data: ContactCreate,
    db: Session = Depends(get_db)
):
    """
    Save enriched contact information
    """
    # Check if contact already exists
    existing = db.query(Contact).filter(
        Contact.user_id == contact_data.user_id,
        Contact.conversation_id == contact_data.conversation_id
    ).first()
    
    contact_dict = contact_data.dict(exclude={'relation_type_ids'})
    relation_type_ids = contact_data.relation_type_ids or []
    
    if existing:
        # Update existing contact
        for key, value in contact_dict.items():
            if value is not None:
                setattr(existing, key, value)
        
        # Update relation types
        if relation_type_ids is not None:
            # Clear existing relations
            existing.relation_types.clear()
            # Add new relations if any
            if relation_type_ids:
                relation_types = db.query(RelationType).filter(
                    RelationType.id.in_(relation_type_ids),
                    RelationType.is_active == True
                ).all()
                existing.relation_types = relation_types
        
        existing.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        return existing
    else:
        # Create new contact
        contact = Contact(**contact_dict)
        
        # Add relation types
        if relation_type_ids:
            relation_types = db.query(RelationType).filter(
                RelationType.id.in_(relation_type_ids),
                RelationType.is_active == True
            ).all()
            contact.relation_types = relation_types
        
        db.add(contact)
        db.commit()
        db.refresh(contact)
        return contact


@router.get("/ingest/contacts/{conversation_id}", response_model=ContactResponse)
async def get_contact(
    conversation_id: str,
    user_id: int = Query(...),
    db: Session = Depends(get_db)
):
    """
    Get contact for a conversation
    """
    from sqlalchemy.orm import joinedload
    
    contact = db.query(Contact).options(
        joinedload(Contact.relation_types)
    ).filter(
        Contact.conversation_id == conversation_id,
        Contact.user_id == user_id
    ).first()
    
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    return contact


@router.post("/ingest/whatsapp-upload-async")
async def upload_whatsapp_async(
    file: UploadFile = File(...),
    user_id: int = Form(default=1),
    conversation_id: Optional[str] = Form(None),
    contact_id: Optional[int] = Form(None),
    db: Session = Depends(get_db)
):
    """
    Upload WhatsApp file asynchronously
    Creates a background job and returns job_id
    """
    if not file.filename or not file.filename.endswith('.txt'):
        raise HTTPException(status_code=400, detail="File must be a .txt file")
    
    try:
        content = await file.read()
        text_content = content.decode('utf-8')
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error reading file: {str(e)}")
    
    # Get conversation_id from contact if provided
    if contact_id:
        contact = db.query(Contact).filter(Contact.id == contact_id).first()
        if contact:
            conversation_id = contact.conversation_id
    
    # Create ingestion job
    job = ingestion_job_manager.create_job(
        db=db,
        user_id=user_id,
        conversation_id=conversation_id
    )
    
    # Get contact name if contact_id is provided
    contact_name = None
    if contact_id:
        contact = db.query(Contact).filter(Contact.id == contact_id).first()
        if contact:
            contact_name = contact.first_name or contact.nickname or contact.phone_number
    elif conversation_id:
        # Try to get contact from conversation_id
        contact = db.query(Contact).filter(
            Contact.conversation_id == conversation_id,
            Contact.user_id == user_id
        ).first()
        if contact:
            contact_name = contact.first_name or contact.nickname or contact.phone_number
    
    # Store job metadata in progress
    job.progress = {
        "source": "whatsapp",
        "contact_name": contact_name,
        "conversation_id": conversation_id
    }
    db.commit()
    
    # Get the event loop for WebSocket broadcasting from background thread
    import asyncio
    try:
        main_loop = asyncio.get_event_loop()
    except RuntimeError:
        # If no loop in current thread, we'll handle it in update_job_progress
        main_loop = None
    
    # Create callback for progress updates
    # Note: This callback will be called from background thread, so it needs its own DB session
    def progress_callback(step: str, data: dict):
        from db.database import SessionLocal
        thread_db = SessionLocal()
        try:
            ingestion_job_manager.update_job_progress(
                db=thread_db,
                job_id=job.id,
                step=step,
                current=data.get('current', 0),
                total=data.get('total', 0),
                message=data.get('message'),
                percent=data.get('percent'),
                main_loop=main_loop,  # Pass the main loop for WebSocket broadcasting
                **{k: v for k, v in data.items() if k not in ['step', 'current', 'total', 'message', 'percent']}
            )
        finally:
            thread_db.close()
    
    # Create callback for LLM logs (thread-safe)
    def llm_log_callback(log_data: dict):
        # Broadcast LLM logs via WebSocket (thread-safe approach)
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(websocket_manager.broadcast_ingestion_progress(job.id, {
                    "type": "llm_log",
                    "data": log_data
                }))
            else:
                loop.run_until_complete(websocket_manager.broadcast_ingestion_progress(job.id, {
                    "type": "llm_log",
                    "data": log_data
                }))
        except RuntimeError:
            # No event loop, create one
            asyncio.run(websocket_manager.broadcast_ingestion_progress(job.id, {
                "type": "llm_log",
                "data": log_data
            }))
    
    # Start job in background
    ingestion_job_manager.start_job_in_background(
        db=db,
        job_id=job.id,
        ingestion_function=ingest_whatsapp_file,
        file_content=text_content,
        user_id=user_id,
        conversation_id=conversation_id,
        progress_callback=progress_callback,
        llm_log_callback=llm_log_callback
    )
    
    return {"job_id": job.id, "status": job.status}


@router.get("/ingest/jobs/{job_id}", response_model=IngestionJobResponse)
async def get_ingestion_job(
    job_id: int,
    db: Session = Depends(get_db)
):
    """
    Get ingestion job status
    """
    job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return job


@router.post("/ingest/jobs/{job_id}/cancel")
async def cancel_ingestion_job(
    job_id: int,
    db: Session = Depends(get_db)
):
    """
    Cancel a running ingestion job
    """
    from services.ingestion_job import ingestion_job_manager
    
    success = ingestion_job_manager.cancel_job(db, job_id)
    
    if not success:
        raise HTTPException(
            status_code=400, 
            detail="Job not found or cannot be cancelled (already completed/failed/cancelled)"
        )
    
    return {"message": "Job cancelled successfully", "job_id": job_id}


@router.websocket("/ingest/ws/{job_id}")
async def ingestion_websocket(websocket: WebSocket, job_id: int):
    """
    WebSocket endpoint for real-time ingestion progress
    """
    print(f"[WebSocket] Connection attempt for job {job_id}")
    await websocket_manager.connect(websocket)
    websocket_manager.register_ingestion_listener(job_id, websocket)
    print(f"[WebSocket] Registered listener for job {job_id}")
    
    # Send initial connection confirmation
    try:
        await websocket.send_text(json.dumps({
            "type": "ingestion_progress",
            "job_id": job_id,
            "data": {
                "step": "connected",
                "message": "WebSocket connected. Waiting for progress updates...",
                "current": 0,
                "total": 0
            }
        }))
    except Exception as e:
        print(f"[WebSocket] Error sending initial message: {str(e)}")
    
    try:
        # Keep connection alive - wait for messages or ping
        import asyncio
        while True:
            try:
                # Wait for message with timeout to allow periodic checks
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                # Handle ping/pong
                if data == "ping":
                    await websocket.send_text("pong")
                else:
                    # Echo back other messages
                    await websocket.send_text(json.dumps({"type": "pong", "data": data}))
            except asyncio.TimeoutError:
                # Send keepalive ping
                try:
                    await websocket.send_text(json.dumps({"type": "ping"}))
                except:
                    # Connection closed, break loop
                    break
    except WebSocketDisconnect:
        print(f"[WebSocket] Client disconnected for job {job_id}")
        websocket_manager.unregister_ingestion_listener(job_id, websocket)
        websocket_manager.disconnect(websocket)
    except Exception as e:
        print(f"[WebSocket] Error in WebSocket handler for job {job_id}: {str(e)}")
        import traceback
        traceback.print_exc()
        websocket_manager.unregister_ingestion_listener(job_id, websocket)
        websocket_manager.disconnect(websocket)
