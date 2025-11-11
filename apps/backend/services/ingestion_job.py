"""
Ingestion job service
Manages background ingestion jobs with persistent state and WebSocket progress updates
"""
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any, Callable
from models import IngestionJob
from datetime import datetime
from services.logs_service import log_to_db
from services.websocket_manager import websocket_manager
import asyncio
import json
import threading


class IngestionJobManager:
    """Manages ingestion jobs with background execution and progress tracking"""
    
    def __init__(self):
        self.running_jobs: Dict[int, threading.Thread] = {}
    
    def create_job(
        self,
        db: Session,
        user_id: int,
        conversation_id: Optional[str] = None
    ) -> IngestionJob:
        """
        Create a new ingestion job in the database
        
        Returns:
            IngestionJob instance
        """
        job = IngestionJob(
            user_id=user_id,
            conversation_id=conversation_id,
            status='pending',
            progress=None,
            error=None
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        
        log_to_db(db, "INFO", f"Created ingestion job {job.id} for user {user_id}", 
                 service="ingestion_job", user_id=user_id, metadata={"job_id": job.id})
        
        return job
    
    def update_job_progress(
        self,
        db: Session,
        job_id: int,
        step: str,
        current: int,
        total: int,
        message: Optional[str] = None,
        percent: Optional[float] = None,
        main_loop: Optional[asyncio.AbstractEventLoop] = None,
        **extra_data
    ):
        """
        Update job progress and broadcast via WebSocket
        """
        job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
        if not job:
            return
        
        # Preserve existing metadata (source, days, contact_name, etc.)
        existing_progress = job.progress or {}
        metadata = {k: v for k, v in existing_progress.items() if k in ['source', 'days', 'only_replied', 'contact_name', 'conversation_id']}
        
        progress_data = {
            **metadata,  # Preserve metadata
            "step": step,
            "current": current,
            "total": total,
            "message": message or f"{step}: {current}/{total}",
            "percent": percent,
            **extra_data  # This includes thread_log, message_log, indexing_log
        }
        
        job.progress = progress_data
        job.status = 'running'
        job.updated_at = datetime.utcnow()
        db.commit()
        
        # Debug: log if we have logs to broadcast
        if 'thread_log' in extra_data or 'message_log' in extra_data or 'indexing_log' in extra_data:
            print(f"[IngestionJob] Broadcasting progress with logs for job {job_id}: thread_log={bool(extra_data.get('thread_log'))}, message_log={bool(extra_data.get('message_log'))}, indexing_log={bool(extra_data.get('indexing_log'))}")
        
        # Broadcast via WebSocket (use thread-safe approach)
        # Note: This is called from background thread, so we need to handle asyncio carefully
        try:
            # Use provided main_loop if available, otherwise try to get it from WebSocketManager
            loop = main_loop
            if loop is None:
                # Try to get loop from WebSocketManager
                if websocket_manager.main_loop:
                    loop = websocket_manager.main_loop
                else:
                    try:
                        loop = asyncio.get_event_loop()
                    except RuntimeError:
                        loop = None
            
            if loop and loop.is_running():
                # If loop is running, schedule coroutine thread-safely
                try:
                    future = asyncio.run_coroutine_threadsafe(
                        websocket_manager.broadcast_ingestion_progress(job_id, progress_data),
                        loop
                    )
                    # Check if future completed successfully (with timeout)
                    try:
                        future.result(timeout=1.0)  # Wait max 1 second
                    except Exception as future_error:
                        print(f"[IngestionJob] WebSocket broadcast future error: {str(future_error)}")
                except Exception as e:
                    print(f"[IngestionJob] Failed to schedule WebSocket broadcast: {str(e)}")
                    # If scheduling fails, try creating new event loop
                    try:
                        asyncio.run(websocket_manager.broadcast_ingestion_progress(job_id, progress_data))
                    except Exception as e2:
                        print(f"[IngestionJob] Failed to run WebSocket broadcast in new loop: {str(e2)}")
                        pass  # Skip if all methods fail
            elif loop:
                # Loop exists but not running, use run_until_complete
                loop.run_until_complete(websocket_manager.broadcast_ingestion_progress(job_id, progress_data))
            else:
                # No loop available, try to create one
                try:
                    asyncio.run(websocket_manager.broadcast_ingestion_progress(job_id, progress_data))
                except RuntimeError as e:
                    print(f"[IngestionJob] Failed to create new loop for WebSocket broadcast: {str(e)}")
                    pass  # Skip if all methods fail
        except Exception as e:
            # Skip WebSocket broadcast if all methods fail - progress is still in DB
            print(f"[IngestionJob] Exception during WebSocket broadcast: {str(e)}")
            pass
    
    def update_job_status(
        self,
        db: Session,
        job_id: int,
        status: str,
        error: Optional[str] = None
    ):
        """
        Update job status (completed/failed)
        """
        job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
        if not job:
            return
        
        job.status = status
        job.error = error
        job.updated_at = datetime.utcnow()
        db.commit()
        
        # Broadcast final status (use thread-safe approach)
        progress_data = {
            "step": "complete" if status == "completed" else "failed",
            "status": status,
            "error": error
        }
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(websocket_manager.broadcast_ingestion_progress(job_id, progress_data))
            else:
                loop.run_until_complete(websocket_manager.broadcast_ingestion_progress(job_id, progress_data))
        except RuntimeError:
            asyncio.run(websocket_manager.broadcast_ingestion_progress(job_id, progress_data))
    
    def cancel_job(self, db: Session, job_id: int) -> bool:
        """
        Cancel a running ingestion job
        Returns True if job was cancelled, False if not found or not running
        """
        job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
        if not job:
            return False
        
        if job.status not in ['pending', 'running']:
            return False  # Job already completed or failed
        
        # Update job status to cancelled
        job.status = 'cancelled'
        job.error = "Job cancelled by user"
        existing_progress = job.progress or {}
        metadata = {k: v for k, v in existing_progress.items() if k in ['source', 'days', 'only_replied', 'contact_name', 'conversation_id']}
        job.progress = {
            **metadata,
            "step": "cancelled",
            "status": "cancelled",
            "message": "Job cancelled by user"
        }
        db.commit()
        
        # Remove from running jobs (thread will check status and exit)
        if job_id in self.running_jobs:
            # Note: We can't force-stop a Python thread, but it will check status and exit
            del self.running_jobs[job_id]
        
        log_to_db(db, "INFO", f"Ingestion job {job_id} cancelled by user", 
                 service="ingestion_job", metadata={"job_id": job_id})
        
        return True
    
    def start_job_in_background(
        self,
        db: Session,
        job_id: int,
        ingestion_function: Callable,
        *args,
        **kwargs
    ):
        """
        Start ingestion job in background thread
        """
        def run_job():
            # Create new DB session for this thread
            from db.database import SessionLocal
            thread_db = SessionLocal()
            try:
                # Update job status to running
                job = thread_db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
                if job:
                    # Check if already cancelled
                    if job.status == 'cancelled':
                        return
                    job.status = 'running'
                    thread_db.commit()
                
                # Run ingestion function
                result = ingestion_function(thread_db, *args, **kwargs)
                
                # Check if job was cancelled during execution
                job = thread_db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
                if job and job.status == 'cancelled':
                    log_to_db(thread_db, "INFO", f"Ingestion job {job_id} was cancelled", 
                             service="ingestion_job", metadata={"job_id": job_id})
                    return
                
                # Update job status to completed
                if job:
                    job.status = 'completed'
                    
                    # Merge with existing progress to preserve metadata
                    existing_progress = job.progress or {}
                    metadata = {k: v for k, v in existing_progress.items() if k in ['source', 'days', 'only_replied', 'contact_name', 'conversation_id']}
                    
                    final_progress = {
                        **metadata,
                        "step": "complete",
                        "status": "completed",
                        "message": "Import terminé avec succès",
                        "percent": 100.0,
                        "current": existing_progress.get('total', existing_progress.get('current', 0)),
                        "total": existing_progress.get('total', existing_progress.get('current', 0))
                    }
                    
                    if result:
                        # Store final stats in progress (ensure JSON serializable)
                        # Remove any non-serializable objects
                        serializable_result = {}
                        for key, value in result.items():
                            if key == 'threads' or key == 'thread_ids':
                                # Skip threads list, keep only IDs if present
                                if 'thread_ids' in result:
                                    serializable_result['thread_ids'] = result['thread_ids']
                                if 'thread_count' in result:
                                    serializable_result['thread_count'] = result['thread_count']
                            elif isinstance(value, (str, int, float, bool, list, dict, type(None))):
                                # Only include JSON-serializable types
                                try:
                                    import json
                                    json.dumps(value)  # Test serialization
                                    serializable_result[key] = value
                                except (TypeError, ValueError):
                                    # Skip non-serializable values
                                    pass
                        
                        final_progress["stats"] = serializable_result
                    
                    job.progress = final_progress
                    thread_db.commit()
                    
                    # Broadcast completion via WebSocket
                    try:
                        loop = websocket_manager.main_loop
                        if loop and loop.is_running():
                            asyncio.run_coroutine_threadsafe(
                                websocket_manager.broadcast_ingestion_progress(job_id, final_progress),
                                loop
                            )
                        elif loop:
                            loop.run_until_complete(
                                websocket_manager.broadcast_ingestion_progress(job_id, final_progress)
                            )
                        else:
                            asyncio.run(
                                websocket_manager.broadcast_ingestion_progress(job_id, final_progress)
                            )
                        print(f"[IngestionJob] Broadcasted completion for job {job_id}")
                    except Exception as e:
                        print(f"[IngestionJob] Failed to broadcast completion for job {job_id}: {str(e)}")
                        import traceback
                        traceback.print_exc()
                
                log_to_db(thread_db, "INFO", f"Ingestion job {job_id} completed", 
                         service="ingestion_job", metadata={"job_id": job_id})
                
            except Exception as e:
                # Update job status to failed
                try:
                    job = thread_db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
                    if job:
                        job.status = 'failed'
                        job.error = str(e)
                        thread_db.commit()
                    
                    log_to_db(thread_db, "ERROR", f"Ingestion job {job_id} failed: {str(e)}", 
                             service="ingestion_job", metadata={"job_id": job_id})
                except Exception:
                    pass  # Ignore errors during error handling
            finally:
                thread_db.close()
                # Remove from running jobs
                if job_id in self.running_jobs:
                    del self.running_jobs[job_id]
        
        # Start thread
        thread = threading.Thread(target=run_job, daemon=True)
        thread.start()
        self.running_jobs[job_id] = thread
        
        log_to_db(db, "INFO", f"Started background thread for ingestion job {job_id}", 
                 service="ingestion_job", metadata={"job_id": job_id})


# Global job manager instance
ingestion_job_manager = IngestionJobManager()

