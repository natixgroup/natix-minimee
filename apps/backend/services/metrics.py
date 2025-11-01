"""
Metrics service for tracking performance and usage
Tracks: latency, RAG hits, LLM calls, embedding generation, error rates
"""
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import defaultdict
import json
from services.logs_service import get_logs, log_structured


# In-memory metrics storage (in production, use Redis or time-series DB)
_metrics_cache = defaultdict(list)


def record_metric(
    metric_name: str,
    value: float,
    labels: Optional[Dict[str, str]] = None
):
    """
    Record a metric value
    """
    timestamp = datetime.utcnow()
    _metrics_cache[metric_name].append({
        "value": value,
        "timestamp": timestamp,
        "labels": labels or {}
    })
    
    # Keep only last 1000 entries per metric
    if len(_metrics_cache[metric_name]) > 1000:
        _metrics_cache[metric_name] = _metrics_cache[metric_name][-1000:]


def record_rag_hit(db: Session, similarity: float, context_items: int):
    """Record successful RAG context retrieval"""
    record_metric("rag_hits", 1, {"similarity": str(similarity), "items": str(context_items)})
    log_structured(
        db=db,
        level="INFO",
        message="RAG hit",
        service="metrics",
        metric="rag_hits",
        similarity=similarity,
        context_items=context_items
    )


def record_llm_call(
    db: Session,
    provider: str,
    latency_ms: float,
    tokens: Optional[int] = None,
    success: bool = True
):
    """Record LLM API call"""
    record_metric("llm_calls", 1, {"provider": provider, "success": str(success)})
    record_metric("llm_latency", latency_ms, {"provider": provider})
    
    log_structured(
        db=db,
        level="INFO" if success else "ERROR",
        message=f"LLM call: {provider}",
        service="metrics",
        metric="llm_call",
        provider=provider,
        latency_ms=latency_ms,
        tokens=tokens,
        success=success
    )


def record_embedding_generation(db: Session, latency_ms: float, text_length: int):
    """Record embedding generation"""
    record_metric("embedding_generation", 1)
    record_metric("embedding_latency", latency_ms)
    
    log_structured(
        db=db,
        level="INFO",
        message="Embedding generated",
        service="metrics",
        metric="embedding",
        latency_ms=latency_ms,
        text_length=text_length
    )


def record_error(db: Session, service: str, error_type: str, message: str):
    """Record error occurrence"""
    record_metric("errors", 1, {"service": service, "error_type": error_type})
    log_structured(
        db=db,
        level="ERROR",
        message=f"Error in {service}: {message}",
        service="metrics",
        metric="error",
        error_service=service,
        error_type=error_type
    )


def calculate_percentiles(values: List[float], percentiles: List[float] = [50, 95, 99]) -> Dict[str, float]:
    """Calculate percentile values from a list"""
    if not values:
        return {f"p{p}": 0.0 for p in percentiles}
    
    sorted_values = sorted(values)
    result = {}
    for p in percentiles:
        index = int((p / 100) * len(sorted_values))
        index = min(index, len(sorted_values) - 1)
        result[f"p{p}"] = sorted_values[index]
    return result


def get_metrics_summary(
    db: Session,
    window_minutes: int = 60
) -> Dict[str, any]:
    """
    Get metrics summary for the last N minutes
    """
    cutoff_time = datetime.utcnow() - timedelta(minutes=window_minutes)
    
    # Get logs with metrics
    logs, _ = get_logs(
        db=db,
        service="metrics",
        start_date=cutoff_time,
        limit=1000
    )
    
    # Aggregate metrics from logs
    rag_hits = []
    llm_calls = defaultdict(list)
    embedding_latencies = []
    request_latencies = []
    errors_by_service = defaultdict(int)
    
    for log in logs:
        if not log.metadata:
            continue
        
        metric = log.metadata.get("metric")
        
        if metric == "rag_hits":
            rag_hits.append(log.metadata.get("similarity", 0))
        
        elif metric == "llm_call":
            provider = log.metadata.get("provider", "unknown")
            latency = log.metadata.get("latency_ms", 0)
            llm_calls[provider].append(latency)
        
        elif metric == "embedding":
            embedding_latencies.append(log.metadata.get("latency_ms", 0))
        
        elif metric == "error":
            service = log.metadata.get("error_service", "unknown")
            errors_by_service[service] += 1
    
    # Get request latencies from API logs
    api_logs, _ = get_logs(
        db=db,
        service="api",
        start_date=cutoff_time,
        limit=1000
    )
    
    for log in api_logs:
        if log.metadata and "latency_ms" in log.metadata:
            request_latencies.append(log.metadata["latency_ms"])
    
    # Calculate statistics
    summary = {
        "window_minutes": window_minutes,
        "timestamp": datetime.utcnow().isoformat(),
        "rag": {
            "hits": len(rag_hits),
            "avg_similarity": sum(rag_hits) / len(rag_hits) if rag_hits else 0
        },
        "llm": {
            "calls_by_provider": {
                provider: len(latencies) 
                for provider, latencies in llm_calls.items()
            },
            "latency_by_provider": {
                provider: {
                    "avg": sum(latencies) / len(latencies) if latencies else 0,
                    **calculate_percentiles(latencies)
                }
                for provider, latencies in llm_calls.items()
            }
        },
        "embeddings": {
            "count": len(embedding_latencies),
            "latency": {
                "avg": sum(embedding_latencies) / len(embedding_latencies) if embedding_latencies else 0,
                **calculate_percentiles(embedding_latencies)
            }
        },
        "requests": {
            "count": len(request_latencies),
            "latency": calculate_percentiles(request_latencies) if request_latencies else {}
        },
        "errors": {
            "by_service": dict(errors_by_service),
            "total": sum(errors_by_service.values())
        }
    }
    
    return summary

