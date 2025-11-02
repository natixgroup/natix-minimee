"""
Minimee Backend - FastAPI Orchestration
Main entry point for the AI orchestration service
"""
import os
import time
import uuid
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from db.check_pgvector import check_pgvector
from db.database import DATABASE_URL, engine, get_db
from sqlalchemy import text
from services.logs_service import log_structured

# Import routers
from routers import (
    health_router,
    settings_router,
    policy_router,
    agents_router,
    prompts_router,
    ingest_router,
    gmail_router,
    whatsapp_router,
    minimee_router,
    logs_router,
    metrics_router,
    llm_router,
    embeddings_router,
    openai_router
)

app = FastAPI(
    title="Minimee API",
    description="AI agent orchestration backend",
    version="0.1.0"
)

# CORS middleware for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3002"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request logging middleware with structured logging
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    request_id = str(uuid.uuid4())
    
    # Add request_id to request state for use in handlers
    request.state.request_id = request_id
    request.state.start_time = start_time
    
    # Process request
    response = await call_next(request)
    
    # Calculate latency
    process_time = time.time() - start_time
    
    # Add headers
    response.headers["X-Process-Time"] = str(round(process_time, 4))
    response.headers["X-Request-ID"] = request_id
    
    # Log structured request
    try:
        db = next(get_db())
        # Categorize service based on endpoint
        # API endpoints (backend routes)
        service = "api"
        endpoint_path = request.url.path
        
        # Frontend static assets and Next.js routes
        if endpoint_path.startswith("/_next/") or endpoint_path.endswith((".js", ".css", ".ico", ".png", ".jpg", ".svg", ".woff", ".woff2")):
            service = "frontend"
        # Health and status endpoints
        elif endpoint_path in ["/health", "/"]:
            service = "api"
        # All other endpoints are API calls
        else:
            service = "api"
        
        log_structured(
            db=db,
            level="INFO" if response.status_code < 400 else "ERROR",
            message=f"{request.method} {request.url.path} - {response.status_code}",
            service=service,
            request_id=request_id,
            endpoint=endpoint_path,
            method=request.method,
            status_code=response.status_code,
            latency_ms=round(process_time * 1000, 2),
            user_agent=request.headers.get("user-agent"),
        )
    except Exception:
        # Don't fail request if logging fails
        pass
    
    return response


# Include routers
app.include_router(health_router.router)
app.include_router(settings_router.router)
app.include_router(policy_router.router)
app.include_router(agents_router.router)
app.include_router(prompts_router.router)
app.include_router(ingest_router.router)
app.include_router(gmail_router.router)
app.include_router(whatsapp_router.router)
app.include_router(minimee_router.router)
app.include_router(logs_router.router)
app.include_router(metrics_router.router)
app.include_router(llm_router.router)
app.include_router(embeddings_router.router)
app.include_router(openai_router.router)


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    startup_start = time.time()
    print("Starting Minimee Backend...")
    
    # Verify pgvector extension
    database_url = os.getenv("DATABASE_URL", DATABASE_URL)
    try:
        check_pgvector(database_url)
        print("✓ pgvector extension verified")
    except RuntimeError as e:
        print(f"✗ ERROR: {e}")
        raise
    
    # Verify database connection
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("✓ Database connection verified")
    except Exception as e:
        print(f"✗ ERROR: Database connection failed: {e}")
        raise
    
    startup_time = time.time() - startup_start
    print(f"✓ Backend started successfully in {startup_time:.2f}s")


@app.get("/")
async def root():
    return {"message": "Minimee API", "status": "running", "version": "0.1.0"}

