"""
Centralized logging service
"""
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional, Dict, Any
from models import Log


def log_to_db(
    db: Session,
    level: str,
    message: str,
    service: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
):
    """
    Write log entry to database
    """
    log_entry = Log(
        level=level.upper(),
        message=message,
        metadata=metadata,
        service=service,
        timestamp=datetime.utcnow()
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)
    return log_entry


def get_logs(
    db: Session,
    level: Optional[str] = None,
    service: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = 100,
    offset: int = 0
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
    
    query = query.order_by(Log.timestamp.desc())
    total = query.count()
    
    logs = query.offset(offset).limit(limit).all()
    
    return logs, total

