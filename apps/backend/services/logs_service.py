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
    request_id: Optional[str] = None,
    order_by: str = "timestamp",
    order_dir: str = "desc"
):
    """
    Query logs with filters, sorting and pagination
    Supports comma-separated values for level and service (multiple filters)
    """
    from sqlalchemy import desc, asc, or_
    
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
    if request_id:
        # Filter by request_id in metadata
        query = query.filter(Log.meta_data['request_id'].astext == request_id)
    
    # Apply sorting
    order_field = getattr(Log, order_by, Log.timestamp)
    if order_dir.lower() == "asc":
        query = query.order_by(asc(order_field))
    else:
        query = query.order_by(desc(order_field))
    
    # Get logs with limit first (most important)
    logs = query.offset(offset).limit(limit).all()
    
    # Count total separately (this can be expensive but needed for pagination)
    count_query = db.query(Log)
    
    if level:
        count_query = count_query.filter(Log.level == level.upper())
    if service:
        count_query = count_query.filter(Log.service == service)
    if start_date:
        count_query = count_query.filter(Log.timestamp >= start_date)
    if end_date:
        count_query = count_query.filter(Log.timestamp <= end_date)
    if request_id:
        count_query = count_query.filter(Log.meta_data['request_id'].astext == request_id)
    
    total = count_query.count()
    
    return logs, total
