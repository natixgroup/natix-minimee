"""
Enhanced ingestion service
Orchestrates the full ingestion pipeline: parse → chunk → embed
Note: Summaries generation has been disabled as they are not required for RAG functionality
"""
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Dict, Optional, Callable
import time
from models import Message, Embedding
from services.whatsapp_parser import parse_whatsapp_export
from services.language_detector import detect_language
from services.conversational_chunking import create_conversational_blocks
from services.embeddings import store_embedding, build_embedding_metadata
from services.topic_generator import generate_latent_topic_sync
from services.logs_service import log_to_db


def _format_eta(eta_seconds: float) -> str:
    """
    Format ETA seconds into human-readable string
    """
    if eta_seconds is None or eta_seconds < 0:
        return ""
    
    if eta_seconds < 60:
        return f" (~{int(eta_seconds)}s remaining)"
    elif eta_seconds < 3600:
        minutes = int(eta_seconds / 60)
        seconds = int(eta_seconds % 60)
        return f" (~{minutes}m {seconds}s remaining)"
    else:
        hours = int(eta_seconds / 3600)
        minutes = int((eta_seconds % 3600) / 60)
        return f" (~{hours}h {minutes}m remaining)"


def _calculate_eta(current: int, total: int, start_time: Optional[float], last_update_time: Optional[float]) -> Optional[float]:
    """
    Calculate estimated time remaining based on current progress
    Returns ETA in seconds or None if not enough data
    """
    if start_time is None or current == 0:
        return None
    
    now = time.time()
    elapsed = now - start_time
    
    if elapsed <= 0 or current <= 0:
        return None
    
    # Calculate rate: items per second
    rate = current / elapsed
    if rate <= 0:
        return None
    
    # Calculate remaining items
    remaining = total - current
    if remaining <= 0:
        return 0.0
    
    # ETA = remaining / rate
    eta_seconds = remaining / rate
    return eta_seconds


def _calculate_progress_percent(step: str, current: int, total: int) -> float:
    """
    Calculate overall progress percentage based on step and current/total
    Step weights:
    - parsing: 0-10%
    - saving_messages: 10-30%
    - chunking: 30-35%
    - topic_generation: 35-40%
    - embedding: 40-100%
    """
    step_ranges = {
        "parsing": (0, 10),
        "saving_messages": (10, 30),
        "chunking": (30, 35),
        "topic_generation": (35, 40),
        "embedding": (40, 100),
    }
    
    if step not in step_ranges:
        return 0.0
    
    start_percent, end_percent = step_ranges[step]
    step_range = end_percent - start_percent
    
    if total > 0 and current >= 0:
        step_progress = min(1.0, max(0.0, current / total))
    else:
        # If no total, use midpoint of range
        step_progress = 0.5 if current == 0 else 1.0
    
    percent = start_percent + (step_range * step_progress)
    return round(percent, 1)


def ingest_whatsapp_file(
    db: Session,
    file_content: str,
    user_id: int,
    conversation_id: Optional[str] = None,
    progress_callback: Optional[Callable[[str, Dict], None]] = None,
    job_id: Optional[int] = None,
    llm_log_callback: Optional[Callable[[Dict], None]] = None
) -> Dict:
    """
    Complete ingestion pipeline for WhatsApp file
    
    Returns:
        {
            'messages_created': int,
            'chunks_created': int,
            'embeddings_created': int,
            'conversation_id': str,
            'summaries_skipped': int  # Always set to chunks count (summaries disabled)
        }
    """
    
    def _emit_progress(step: str, data: Dict):
        """Helper to emit progress with calculated percentage"""
        if progress_callback:
            current = data.get('current', 0)
            total = data.get('total', 0)
            percent = _calculate_progress_percent(step, current, total)
            data['percent'] = percent
            progress_callback(step, data)
    
    if not conversation_id:
        conversation_id = f"whatsapp_{datetime.now().timestamp()}"
    
    stats = {
        'messages_created': 0,
        'chunks_created': 0,
        'summaries_created': 0,
        'embeddings_created': 0,
        'embeddings_skipped': 0,
        'summaries_skipped': 0,
        'conversation_id': conversation_id,
    }
    
    try:
        log_to_db(db, "INFO", "Starting WhatsApp ingestion", service="ingestion")
        
        _emit_progress("parsing", {"step": "parsing", "message": "Parsing WhatsApp file...", "current": 0, "total": 0})
        
        # Step 1: Parse WhatsApp file
        # Try to get user WhatsApp ID from conversation_id if it matches pattern
        # For WhatsApp exports, conversation_id often contains the contact ID
        user_whatsapp_id = None
        if conversation_id and '@' not in conversation_id:
            # conversation_id might be a phone number, try to construct WhatsApp ID
            # This is a heuristic - in production, get this from user settings or auth
            pass
        
        # Parse with progress updates for large files
        # Get total lines for progress tracking
        total_lines = len(file_content.split('\n'))
        
        # Shared state for heartbeat mechanism
        parsing_state = {
            'lines_processed': 0,
            'messages_found': 0,
            'is_parsing': True
        }
        
        # Create wrapper callback to convert parser progress to ingestion format
        def parser_progress_callback(lines_processed: int, total_lines: int, messages_found: int):
            """Convert parser progress format to ingestion progress format"""
            parsing_state['lines_processed'] = lines_processed
            parsing_state['messages_found'] = messages_found
            
            _emit_progress("parsing", {
                "step": "parsing",
                "message": f"Parsing... {lines_processed}/{total_lines} lines, {messages_found} messages found",
                "current": lines_processed,
                "total": total_lines
            })
        
        # Heartbeat mechanism: send periodic updates during parsing
        import threading
        import time
        
        def parsing_heartbeat():
            """Send heartbeat updates every 2 seconds during parsing"""
            while parsing_state['is_parsing']:
                time.sleep(2)
                if parsing_state['is_parsing']:
                    lines = parsing_state['lines_processed']
                    messages = parsing_state['messages_found']
                    _emit_progress("parsing", {
                        "step": "parsing",
                        "message": f"Parsing in progress... {lines}/{total_lines} lines processed, {messages} messages found",
                        "current": lines,
                        "total": total_lines
                    })
        
        # Start heartbeat thread
        heartbeat_thread = threading.Thread(target=parsing_heartbeat, daemon=True)
        heartbeat_thread.start()
        
        # Initial progress update
        _emit_progress("parsing", {
            "step": "parsing", 
            "message": f"Starting to parse {total_lines} lines...", 
            "current": 0, 
            "total": total_lines
        })
        
        try:
            parsed_messages = parse_whatsapp_export(
                file_content, 
                user_whatsapp_id=user_whatsapp_id,
                progress_callback=parser_progress_callback if progress_callback else None
            )
        finally:
            # Stop heartbeat thread
            parsing_state['is_parsing'] = False
            heartbeat_thread.join(timeout=1)  # Wait max 1 second for thread to finish
        
        # Check if job was cancelled after parsing
        if job_id:
            from models import IngestionJob
            job_check = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
            if job_check and job_check.status == 'cancelled':
                _emit_progress("cancelled", {
                    "step": "cancelled",
                    "message": "Import cancelled by user",
                    "current": 0,
                    "total": len(parsed_messages) if parsed_messages else 0
                })
                return stats
        
        log_to_db(db, "INFO", f"Parsed {len(parsed_messages)} messages", service="ingestion")
        
        # Emit parsing complete immediately
        _emit_progress("parsing", {
            "step": "parsing", 
            "message": f"Parsed {len(parsed_messages)} messages. Starting to save...", 
            "current": len(parsed_messages), 
            "total": len(parsed_messages)
        })
        
        if not parsed_messages:
            return stats
        
        # If conversation_id is a phone number, try to use it as recipient for 1-1 chats
        # This is a fallback if parser couldn't determine recipient
        if conversation_id and '@' not in conversation_id:
            # Check if it's a 1-1 conversation (2 unique senders)
            unique_senders = set(msg['sender'] for msg in parsed_messages)
            if len(unique_senders) == 2:
                # Use conversation_id as recipient hint
                for msg in parsed_messages:
                    if not msg.get('recipient'):
                        # If sender is not the conversation_id, recipient might be conversation_id
                        if conversation_id not in msg['sender']:
                            msg['recipient'] = f"{conversation_id}@s.whatsapp.net"
        
        # Step 2: Detect language and create message records
        _emit_progress("saving_messages", {"step": "saving_messages", "message": "Saving messages to database...", "current": 0, "total": len(parsed_messages)})
        
        message_records = []
        total_messages = len(parsed_messages)
        BATCH_SIZE = 100  # Commit every 100 messages instead of flush() for each
        
        # Track timing for ETA calculation
        saving_timing = {'start_time': time.time()}
        
        for idx, parsed_msg in enumerate(parsed_messages):
            # Check if job was cancelled (every 50 messages to avoid too many DB queries)
            if job_id and idx % 50 == 0:
                from models import IngestionJob
                job_check = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
                if job_check and job_check.status == 'cancelled':
                    _emit_progress("cancelled", {
                        "step": "cancelled",
                        "message": "Import cancelled by user",
                        "current": idx,
                        "total": total_messages
                    })
                    return stats
            
            # Skip language detection for now to speed up processing (can be done later if needed)
            # language = detect_language(parsed_msg['content'])
            language = None  # Will be detected during embedding if needed
            
            msg = Message(
                content=parsed_msg['content'],
                sender=parsed_msg['sender'],
                recipient=parsed_msg.get('recipient'),
                recipients=parsed_msg.get('recipients'),  # JSONB array
                timestamp=parsed_msg['timestamp'],
                source="whatsapp",
                conversation_id=conversation_id,
                user_id=user_id
            )
            db.add(msg)
            
            # Store language in embedding metadata later
            message_records.append({
                'db_message': msg,
                'parsed': parsed_msg,
                'language': language,
            })
            stats['messages_created'] += 1
            
            # Batch commit every BATCH_SIZE messages instead of flush() for each
            if (idx + 1) % BATCH_SIZE == 0:
                db.commit()
                if progress_callback:
                    # Calculate ETA every BATCH_SIZE messages
                    eta_seconds = _calculate_eta(idx + 1, total_messages, saving_timing['start_time'], None)
                    eta_message = _format_eta(eta_seconds) if eta_seconds is not None else ""
                    _emit_progress("saving_messages", {
                        "step": "saving_messages", 
                        "message": f"Saving messages... {idx + 1}/{total_messages}{eta_message}", 
                        "current": idx + 1, 
                        "total": total_messages,
                        "eta_seconds": eta_seconds
                    })
        
        # Final commit for remaining messages
        db.commit()
        log_to_db(db, "INFO", f"Created {stats['messages_created']} messages in DB", service="ingestion")
        
        _emit_progress("saving_messages", {"step": "saving_messages", "message": f"Saved {stats['messages_created']} messages", "current": stats['messages_created'], "total": stats['messages_created']})
        
        # Check if job was cancelled before chunking
        if job_id:
            from models import IngestionJob
            job_check = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
            if job_check and job_check.status == 'cancelled':
                _emit_progress("cancelled", {
                    "step": "cancelled",
                    "message": "Import cancelled by user",
                    "current": stats['messages_created'],
                    "total": total_messages
                })
                return stats
        
        # Step 3: Create conversational blocks (temporal/logical grouping)
        _emit_progress("chunking", {"step": "chunking", "message": "Creating conversational blocks...", "current": 0, "total": 0})
        
        blocks = create_conversational_blocks(
            parsed_messages,
            time_window_minutes=20,
            silence_threshold_hours=1.0
        )
        
        # Update blocks with message IDs
        for block in blocks:
            block['message_ids'] = [
                message_records[idx]['db_message'].id 
                for idx in block['messages']
            ]
        
        stats['chunks_created'] = len(blocks)  # Keep 'chunks_created' for compatibility
        log_to_db(db, "INFO", f"Created {len(blocks)} conversational blocks", service="ingestion")
        
        _emit_progress("chunking", {"step": "chunking", "message": f"Created {stats['chunks_created']} conversational blocks", "current": stats['chunks_created'], "total": stats['chunks_created']})
        
        # Step 4: Generate latent topics for each block
        _emit_progress("topic_generation", {"step": "topic_generation", "message": "Generating latent topics...", "current": 0, "total": len(blocks)})
        
        total_blocks = len(blocks)
        for block_idx, block in enumerate(blocks):
            try:
                topic = generate_latent_topic_sync(
                    block_text=block['text'],
                    db=db,
                    user_id=user_id,
                    job_id=job_id,
                    llm_log_callback=llm_log_callback
                )
                block['latent_topic'] = topic
                
                if progress_callback:
                    _emit_progress("topic_generation", {
                        "step": "topic_generation",
                        "message": f"Generating topics... {block_idx + 1}/{total_blocks}",
                        "current": block_idx + 1,
                        "total": total_blocks
                    })
            except Exception as e:
                log_to_db(db, "WARNING", f"Failed to generate topic for block {block_idx}: {str(e)}", service="ingestion")
                block['latent_topic'] = "conversation"  # Fallback
        
        log_to_db(db, "INFO", f"Generated topics for {len(blocks)} blocks", service="ingestion")
        
        # Step 5: Skip summaries generation (not needed for RAG - embeddings are sufficient)
        # Summaries were taking 2+ hours for large files and are not required for RAG functionality
        log_to_db(db, "INFO", f"Skipping summaries generation (not required for RAG). {len(blocks)} blocks will proceed directly to embedding.", service="ingestion")
        blocks_with_topics = blocks.copy()
        stats['summaries_skipped'] = len(blocks)
        
        # Step 6: Generate embeddings for blocks (resilient to embedding failures)
        blocks_to_process = blocks_with_topics if blocks_with_topics else blocks
        total_blocks = len(blocks_to_process)
        
        _emit_progress("embedding", {"step": "embedding", "message": "Generating embeddings...", "current": 0, "total": total_blocks, "embeddings_created": 0})
        
        # Track timing for ETA calculation
        embedding_timing = {'start_time': time.time()}
        
        block_idx = 0
        for block in blocks_to_process:
            
            # Generate embedding for block with metadata (resilient to model failures)
            try:
                # Skip language detection for blocks to speed up (can be done later)
                block_language = None
                
                # Extract unique recipients/participants from block messages
                block_message_indices = block.get('messages', [])
                block_messages = [parsed_messages[idx] for idx in block_message_indices]
                block_recipients = set()
                block_recipient_lists = []
                for msg in block_messages:
                    if msg.get('recipient'):
                        block_recipients.add(msg['recipient'])
                    if msg.get('recipients'):
                        block_recipient_lists.extend(msg['recipients'])
                
                # Get first message for base metadata
                first_msg_idx = block_message_indices[0] if block_message_indices else 0
                first_db_message = message_records[first_msg_idx]['db_message'] if first_msg_idx < len(message_records) else None
                
                # Build metadata for block embedding with temporal info
                if first_db_message:
                    block_metadata = build_embedding_metadata(
                        message=first_db_message,
                        language=block_language,
                        chunk=True,
                        start_timestamp=block.get('start_timestamp'),
                        end_timestamp=block.get('end_timestamp'),
                        user_id=user_id,
                        latent_topic=block.get('latent_topic', 'conversation'),
                        duration_minutes=block.get('duration_minutes'),
                        participants=block.get('participants', [])
                    )
                else:
                    # Fallback if no message available
                    block_metadata = {
                        'chunk': 'true',
                        'conversation_id': conversation_id,
                        'source': 'whatsapp',
                        'user_id': user_id,
                        'latent_topic': block.get('latent_topic', 'conversation'),
                        'duration_minutes': block.get('duration_minutes'),
                        'participants': block.get('participants', [])
                    }
                    # Add temporal metadata
                    if block.get('start_timestamp'):
                        # Import here to avoid circular import
                        from services.embeddings import _calculate_temporal_metadata
                        temporal_meta = _calculate_temporal_metadata(block['start_timestamp'])
                        block_metadata.update(temporal_meta)
                        if block.get('end_timestamp'):
                            block_metadata['time_range'] = f"{block['start_timestamp'].date().isoformat()} → {block['end_timestamp'].date().isoformat()}"
                
                # Add recipient info if available
                if block_recipients:
                    block_metadata['recipient'] = list(block_recipients)[0] if len(block_recipients) == 1 else None
                    block_metadata['recipients'] = list(block_recipients) if len(block_recipients) > 1 else None
                
                # Store block embedding
                embedding = store_embedding(
                    db=db,
                    text=block['text'],
                    message_id=None,  # Blocks don't link to single message
                    metadata=block_metadata,
                    user_id=user_id
                )
                stats['embeddings_created'] += 1
                
                # Batch commit every 10 blocks to avoid too many DB operations
                if (block_idx + 1) % 10 == 0:
                    db.commit()
                
                # Calculate ETA every 10 blocks (recalculates as requested)
                eta_seconds = _calculate_eta(block_idx + 1, total_blocks, embedding_timing['start_time'], None)
                eta_message = _format_eta(eta_seconds) if eta_seconds is not None else ""
                
                # Update progress for block embedding
                _emit_progress("embedding", {
                    "step": "embedding",
                    "message": f"Vectorizing blocks... {block_idx + 1}/{total_blocks}{eta_message}",
                    "current": block_idx + 1,
                    "total": total_blocks,
                    "embeddings_created": stats['embeddings_created'],
                    "eta_seconds": eta_seconds
                })
                
                # Skip individual message embeddings for now to speed up processing
                # They can be generated later in background if needed
                # This significantly reduces processing time for large files
                stats['embeddings_skipped'] += len(block.get('message_ids', []))
            
                block_idx += 1
                
            except Exception as e:
                log_to_db(
                    db,
                    "WARNING",
                    f"Failed to create embedding for block (embedding model may not be ready): {str(e)}",
                    service="ingestion"
                )
                stats['embeddings_skipped'] += 1
                # Count skipped message embeddings for this block
                block_message_count = len(block.get('message_ids', []))
                stats['embeddings_skipped'] += block_message_count
                block_idx += 1
        
        # Final commit for any remaining embeddings
        db.commit()
        
        _emit_progress("complete", {
            "step": "complete",
            "message": "Import complete!",
            "stats": stats,
            "percent": 100.0
        })
        
        log_to_db(
            db,
            "INFO",
            f"Ingestion complete: {stats['messages_created']} messages, "
            f"{stats['chunks_created']} blocks, {stats['embeddings_created']} embeddings. "
            f"Skipped: {stats.get('embeddings_skipped', 0)} embeddings (summaries generation disabled)",
            service="ingestion"
        )
        
        # Auto-classify contact after import
        try:
            from services.contact_classifier import auto_classify_and_notify
            classification_result = auto_classify_and_notify(
                db=db,
                user_id=user_id,
                conversation_id=conversation_id,
                source='whatsapp',
                confidence_threshold=0.7
            )
            if classification_result and classification_result.get('needs_validation'):
                # Classification needs user validation - could emit notification here
                log_to_db(
                    db,
                    "INFO",
                    f"Contact classification suggested for conversation {conversation_id}: {classification_result.get('suggested_category_label')}",
                    service="ingestion",
                    user_id=user_id,
                    metadata={"conversation_id": conversation_id, "classification": classification_result}
                )
        except Exception as e:
            # Don't fail import if classification fails
            log_to_db(
                db,
                "WARNING",
                f"Failed to classify contact for conversation {conversation_id}: {str(e)}",
                service="ingestion",
                user_id=user_id
            )
        
        return stats
    
    except Exception as e:
        db.rollback()
        error_msg = f"WhatsApp ingestion error: {str(e)}"
        log_to_db(db, "ERROR", error_msg, service="ingestion")
        raise

