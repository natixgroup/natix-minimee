"""
Logs retrieval endpoints
"""
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
import json
import asyncio
from db.database import get_db
from services.logs_service import get_logs
from schemas import LogResponse, LogQuery, ActionLogResponse, ActionLogQuery
from models import ActionLog

router = APIRouter()

# Standard log levels as defined in the system
STANDARD_LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR"]


@router.get("/logs/metadata")
async def get_logs_metadata(db: Session = Depends(get_db)):
    """
    Get available log levels and services for filtering
    Returns standard levels (always) and actual services from database
    """
    # Get unique services from database
    from models import Log
    services = db.query(Log.service).distinct().filter(Log.service.isnot(None)).order_by(Log.service).all()
    unique_services = [s[0] for s in services]
    
    return {
        "levels": STANDARD_LOG_LEVELS,
        "services": unique_services
    }


@router.get("/logs")
async def get_logs_endpoint(
    level: Optional[str] = Query(None, description="Filter by level (comma-separated for multiple)"),
    service: Optional[str] = Query(None, description="Filter by service (comma-separated for multiple)"),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    order_by: Optional[str] = Query("timestamp", description="Field to order by (id, level, message, service, timestamp)"),
    order_dir: Optional[str] = Query("desc", description="Order direction (asc, desc)"),
    group_by_request: bool = Query(False, description="Group logs by request_id (for vectorization processes)"),
    db: Session = Depends(get_db)
):
    """
    Query logs with filters, pagination, sorting and optional grouping
    Returns paginated response with total count
    """
    import json
    from typing import Dict, List
    
    # Validate order_by field
    valid_order_fields = {"id", "level", "message", "service", "timestamp"}
    if order_by not in valid_order_fields:
        order_by = "timestamp"
    
    # Validate order_dir
    if order_dir not in {"asc", "desc"}:
        order_dir = "desc"
    
    logs, total = get_logs(
        db=db,
        level=level,
        service=service,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
        order_by=order_by,
        order_dir=order_dir
    )
    
    # Convert metadata from JSONB to dict for Pydantic validation
    result = []
    for log in logs:
        # Access metadata using the Python attribute name (meta_data)
        metadata_dict = None
        if hasattr(log, 'meta_data') and log.meta_data is not None:
            if isinstance(log.meta_data, dict):
                metadata_dict = log.meta_data
            else:
                try:
                    metadata_dict = dict(log.meta_data) if log.meta_data else None
                except:
                    metadata_dict = None
        
        log_dict = {
            "id": log.id,
            "level": log.level,
            "message": log.message,
            "metadata": metadata_dict,
            "service": log.service,
            "timestamp": log.timestamp.isoformat() if log.timestamp else None
        }
        result.append(log_dict)
    
    # Group by request_id if requested (for vectorization processes)
    if group_by_request:
        grouped: Dict[str, List] = {}
        ungrouped = []
        
        for log in result:
            request_id = log.get("metadata", {}).get("request_id") if log.get("metadata") else None
            # Group logs that have the same request_id (typically vectorization processes)
            # Also check if message contains vectorization-related keywords
            if request_id and (
                "vectorization" in log.get("message", "").lower() or
                "embedding" in log.get("message", "").lower() or
                "vectorized" in log.get("message", "").lower() or
                log.get("service") == "ingestion"
            ):
                if request_id not in grouped:
                    grouped[request_id] = []
                grouped[request_id].append(log)
            else:
                ungrouped.append(log)
        
        # Format grouped results: first log of each group represents the group
        grouped_result = []
        for request_id, group_logs in grouped.items():
            # Sort group logs by timestamp
            group_logs.sort(key=lambda x: x["timestamp"] or "", reverse=(order_dir == "desc"))
            
            # Create group summary
            group_summary = {
                **group_logs[0],  # Use first log as summary
                "is_group": True,
                "group_id": request_id,
                "group_count": len(group_logs),
                "group_logs": group_logs  # All logs in the group
            }
            grouped_result.append(group_summary)
        
        # Add ungrouped logs
        grouped_result.extend(ungrouped)
        
        # Sort grouped result
        if order_by == "timestamp":
            grouped_result.sort(
                key=lambda x: x.get("timestamp") or "",
                reverse=(order_dir == "desc")
            )
        
        return {
            "logs": grouped_result,
            "total": total,
            "page": (offset // limit) + 1,
            "limit": limit,
            "total_pages": (total + limit - 1) // limit
        }
    
    return {
        "logs": result,
        "total": total,
        "page": (offset // limit) + 1,
        "limit": limit,
        "total_pages": (total + limit - 1) // limit
    }


@router.delete("/logs")
async def delete_logs(
    level: Optional[str] = Query(None, description="Filter by level (comma-separated for multiple)"),
    service: Optional[str] = Query(None, description="Filter by service (comma-separated for multiple)"),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Delete logs matching the specified filters
    Uses the same filters as GET /logs to ensure consistency.
    Returns count of deleted logs.
    """
    from models import Log
    from services.logs_service import log_to_db
    from sqlalchemy import or_
    
    try:
        query = db.query(Log)
        
        # Support multiple levels (comma-separated)
        if level:
            levels = [l.strip().upper() for l in level.split(",") if l.strip()]
            if levels:
                query = query.filter(Log.level.in_(levels))
        
        # Support multiple services (comma-separated)
        if service:
            services = [s.strip() for s in service.split(",") if s.strip()]
            if services:
                query = query.filter(Log.service.in_(services))
        
        if start_date:
            query = query.filter(Log.timestamp >= start_date)
        if end_date:
            query = query.filter(Log.timestamp <= end_date)
        
        # Count before deletion
        count = query.count()
        
        if count == 0:
            return {
                "deleted": 0,
                "message": "No logs found matching the filters"
            }
        
        # Delete logs
        deleted_count = query.delete(synchronize_session=False)
        db.commit()
        
        log_to_db(
            db,
            "INFO",
            f"Deleted {deleted_count} logs",
            service="logs",
            metadata={
                "deleted_count": deleted_count,
                "filters": {
                    "level": level,
                    "service": service,
                    "start_date": start_date.isoformat() if start_date else None,
                    "end_date": end_date.isoformat() if end_date else None,
                }
            }
        )
        
        return {
            "deleted": deleted_count,
            "message": f"Successfully deleted {deleted_count} log(s)"
        }
    
    except Exception as e:
        db.rollback()
        log_to_db(db, "ERROR", f"Error deleting logs: {str(e)}", service="logs")
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"Error deleting logs: {str(e)}")


@router.get("/action-logs", response_model=list[ActionLogResponse])
async def get_action_logs_endpoint(
    action_type: Optional[str] = Query(None),
    request_id: Optional[str] = Query(None),
    message_id: Optional[int] = Query(None),
    conversation_id: Optional[str] = Query(None),
    user_id: Optional[int] = Query(None),
    source: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """
    Query action logs with filters
    """
    try:
        query = db.query(ActionLog)
        
        if action_type:
            query = query.filter(ActionLog.action_type == action_type)
        if request_id:
            query = query.filter(ActionLog.request_id == request_id)
        if message_id:
            query = query.filter(ActionLog.message_id == message_id)
        if conversation_id:
            query = query.filter(ActionLog.conversation_id == conversation_id)
        if user_id:
            query = query.filter(ActionLog.user_id == user_id)
        if source:
            query = query.filter(ActionLog.source == source)
        if status:
            query = query.filter(ActionLog.status == status)
        if start_date:
            query = query.filter(ActionLog.timestamp >= start_date)
        if end_date:
            query = query.filter(ActionLog.timestamp <= end_date)
        
        query = query.order_by(ActionLog.timestamp.desc())
        
        logs = query.offset(offset).limit(limit).all()
        
        # Convert to response format manually to handle meta_data -> metadata mapping
        result = []
        for log in logs:
            result.append(ActionLogResponse(
                id=log.id,
                action_type=log.action_type,
                duration_ms=log.duration_ms,
                model=log.model,
                input_data=log.input_data,
                output_data=log.output_data,
                metadata=log.meta_data,  # Map meta_data to metadata
                message_id=log.message_id,
                conversation_id=log.conversation_id,
                request_id=log.request_id,
                user_id=log.user_id,
                source=log.source,
                status=log.status,
                error_message=log.error_message,
                timestamp=log.timestamp
            ))
        return result
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"Error fetching action logs: {str(e)}")


@router.get("/logs/stream")
async def stream_logs(
    action_type: Optional[str] = Query(None),
    request_id: Optional[str] = Query(None),
    message_id: Optional[int] = Query(None)
):
    """
    Stream action logs in real-time using Server-Sent Events (SSE)
    """
    from db.database import get_db
    
    async def event_generator():
        last_id = None
        db = next(get_db())
        consecutive_empty_polls = 0
        max_empty_polls = 20  # Stop polling aggressively after 20 empty polls (~1 minute)
        
        try:
            while True:
                # Query for new logs
                query = db.query(ActionLog)
                
                if action_type:
                    query = query.filter(ActionLog.action_type == action_type)
                if request_id:
                    query = query.filter(ActionLog.request_id == request_id)
                if message_id:
                    query = query.filter(ActionLog.message_id == message_id)
                
                if last_id:
                    query = query.filter(ActionLog.id > last_id)
                
                query = query.order_by(ActionLog.timestamp.asc())
                logs = query.limit(100).all()
                
                if logs:
                    consecutive_empty_polls = 0
                    for log in logs:
                        last_id = log.id
                        log_dict = {
                            "id": log.id,
                            "action_type": log.action_type,
                            "duration_ms": log.duration_ms,
                            "model": log.model,
                            "input_data": log.input_data,
                            "output_data": log.output_data,
                            "metadata": log.meta_data,  # Use meta_data from model
                            "message_id": log.message_id,
                            "conversation_id": log.conversation_id,
                            "request_id": log.request_id,
                            "user_id": log.user_id,
                            "source": log.source,
                            "status": log.status,
                            "error_message": log.error_message,
                            "timestamp": log.timestamp.isoformat()
                        }
                        
                        yield f"data: {json.dumps(log_dict)}\n\n"
                else:
                    consecutive_empty_polls += 1
                    # Send heartbeat every 5 seconds to keep connection alive
                    if consecutive_empty_polls % 5 == 0:
                        yield ": heartbeat\n\n"
                
                # Adaptive polling: slower when no new data
                if consecutive_empty_polls > max_empty_polls:
                    # Reduce to polling every 10 seconds after many empty polls
                    await asyncio.sleep(10)
                elif consecutive_empty_polls > 10:
                    # Poll every 5 seconds after 10 empty polls
                    await asyncio.sleep(5)
                else:
                    # Poll every 2 seconds initially (reduced from 1 second)
                    await asyncio.sleep(2)
        finally:
            db.close()
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )

