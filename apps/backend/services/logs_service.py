"""
Centralized logging service with structured JSON logging
"""
import json
import uuid
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional, Dict, Any
from models import Log


def generate_request_id() -> str:
    """Generate unique request ID"""
    return str(uuid.uuid4())


def log_to_db(
    db: Session,
    level: str,
    message: str,
    service: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
    trace_id: Optional[str] = None,
    user_id: Optional[int] = None,
    endpoint: Optional[str] = None
) -> Log:
    """
    Write log entry to database with structured metadata
    Supports structured JSON logging for better parsing/aggregation
    """
    # Build structured metadata
    structured_metadata = {
        "request_id": request_id,
        "trace_id": trace_id,
        "user_id": user_id,
        "endpoint": endpoint,
        **(metadata or {})
    }
    
    # Remove None values for cleaner JSON
    structured_metadata = {k: v for k, v in structured_metadata.items() if v is not None}
    
    log_entry = Log(
        level=level.upper(),
        message=message,
        metadata=structured_metadata if structured_metadata else None,
        service=service,
        timestamp=datetime.utcnow()
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)
    return log_entry


def log_structured(
    db: Session,
    level: str,
    message: str,
    **kwargs
) -> Log:
    """
    Log with structured data (JSON format)
    Usage: log_structured(db, "INFO", "User action", user_id=1, action="create_agent", duration=0.5)
    """
    metadata = {
        k: v for k, v in kwargs.items()
        if k not in ['service', 'request_id', 'trace_id', 'user_id', 'endpoint']
    }
    
    return log_to_db(
        db=db,
        level=level,
        message=message,
        service=kwargs.get('service'),
        metadata=metadata,
        request_id=kwargs.get('request_id'),
        trace_id=kwargs.get('trace_id'),
        user_id=kwargs.get('user_id'),
        endpoint=kwargs.get('endpoint')
    )


def get_logs(
    db: Session,
    level: Optional[str] = None,
    service: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = 100,
    offset: int = 0,
    request_id: Optional[str] = None
):
    """
    Query logs with filters
    """
    query = db.query(Log)
    
    if level:
        query = query.filter(Log.level == level.upper())
    if service:
        query = query.filter(Log.service == service)
    if start_date:
        query = query.filter(Log.timestamp >= start_date)
    if end_date:
        query = query.filter(Log.timestamp <= end_date)
    if request_id:
        # Filter by request_id in metadata
        query = query.filter(Log.metadata['request_id'].astext == request_id)
    
    query = query.order_by(Log.timestamp.desc())
    total = query.count()
    
    logs = query.offset(offset).limit(limit).all()
    
    return logs, total
