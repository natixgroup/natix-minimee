"""
Metrics endpoints for monitoring and observability
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from db.database import get_db
from services.metrics import get_metrics_summary

router = APIRouter()


@router.get("/metrics")
async def get_metrics(
    window_minutes: int = Query(60, ge=1, le=1440, description="Time window in minutes"),
    db: Session = Depends(get_db)
):
    """
    Get metrics summary
    Returns JSON with latency percentiles, RAG hits, LLM calls, embedding stats, error rates
    """
    try:
        summary = get_metrics_summary(db, window_minutes=window_minutes)
        return summary
    except Exception as e:
        return {
            "error": str(e),
            "window_minutes": window_minutes
        }

