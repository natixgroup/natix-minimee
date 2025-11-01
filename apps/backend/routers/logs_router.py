"""
Logs retrieval endpoints
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
from db.database import get_db
from services.logs_service import get_logs
from schemas import LogResponse, LogQuery

router = APIRouter()


@router.get("/logs", response_model=list[LogResponse])
async def get_logs_endpoint(
    level: Optional[str] = Query(None),
    service: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """
    Query logs with filters
    """
    logs, total = get_logs(
        db=db,
        level=level,
        service=service,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset
    )
    return logs

