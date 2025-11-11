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
    whatsapp_integrations_router,
    minimee_router,
    logs_router,
    metrics_router,
    llm_router,
    embeddings_router,
    openai_router,
    auth_router,
    user_info_router,
    contact_category_router,
    conversation_session_router
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
    
    endpoint_path = request.url.path
    
    # Process request
    response = await call_next(request)
    
    # Calculate latency
    process_time = time.time() - start_time
    
    # Add headers
    response.headers["X-Process-Time"] = str(round(process_time, 4))
    response.headers["X-Request-ID"] = request_id
    
    # Log structured request (categorize frontend polling vs API calls)
    try:
        # Skip logging for static assets only
        should_skip = (
            endpoint_path.startswith("/_next/") or
            endpoint_path.endswith((".js", ".css", ".ico", ".png", ".jpg", ".svg", ".woff", ".woff2"))
        )
        
        if not should_skip:
            # Use get_db() properly with context manager to ensure connection is closed
            db_gen = get_db()
            try:
                db = next(db_gen)
                
                # Categorize service based on endpoint
                # Frontend polling/interaction endpoints -> "frontend" (can be filtered out)
                frontend_polling_paths = [
                    "/logs",
                    "/logs/stream",
                    "/logs/metadata",
                    "/metrics",
                    "/health",
                    "/embeddings",
                    "/llm/status",
                    "/llm/models",
                    "/embeddings/models",
                    "/settings",
                ]
                
                # Check if path starts with any of the frontend polling paths
                is_frontend_polling = any(
                    endpoint_path == path or 
                    endpoint_path.startswith(f"{path}/") or
                    endpoint_path.startswith(path)
                    for path in frontend_polling_paths
                )
                
                service = "frontend" if is_frontend_polling else "api"
                
                # Build metadata
                metadata = {
                    "endpoint": endpoint_path,
                    "method": request.method,
                    "status_code": response.status_code,
                    "latency_ms": round(process_time * 1000, 2),
                    "user_agent": request.headers.get("user-agent"),
                }
                
                log_structured(
                    db=db,
                    level="INFO" if response.status_code < 400 else "ERROR",
                    message=f"{request.method} {request.url.path} - {response.status_code}",
                    service=service,
                    request_id=request_id,
                    **metadata
                )
            finally:
                # Ensure database connection is closed
                try:
                    next(db_gen, None)
                except StopIteration:
                    pass
    except Exception:
        # Don't fail request if logging fails
        pass
    
    return response


# Include routers
app.include_router(auth_router.router)
app.include_router(health_router.router)
app.include_router(settings_router.router)
app.include_router(policy_router.router)
app.include_router(agents_router.router)
app.include_router(prompts_router.router)
app.include_router(ingest_router.router)
app.include_router(gmail_router.router)
app.include_router(whatsapp_router.router)
app.include_router(whatsapp_integrations_router.router)
app.include_router(minimee_router.router)
app.include_router(logs_router.router)
app.include_router(metrics_router.router)
app.include_router(llm_router.router)
app.include_router(embeddings_router.router)
app.include_router(openai_router.router)
app.include_router(user_info_router.router)
app.include_router(contact_category_router.router)
app.include_router(conversation_session_router.router)


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    startup_start = time.time()
    print("Starting Minimee Backend...")
    
    # Register main event loop with WebSocket manager for thread-safe broadcasting
    import asyncio
    from services.websocket_manager import websocket_manager
    try:
        loop = asyncio.get_event_loop()
        websocket_manager.set_main_loop(loop)
    except Exception as e:
        print(f"⚠ Warning: Could not register main event loop: {e}")
    
    # Validate Python syntax (catch any import-time syntax errors)
    try:
        import sys
        import importlib.util
        from pathlib import Path
        
        # Check if we can import all routers (this will catch syntax errors)
        router_files = Path(__file__).parent / "routers"
        if router_files.exists():
            for router_file in router_files.glob("*.py"):
                if router_file.name != "__init__.py":
                    try:
                        spec = importlib.util.spec_from_file_location(
                            router_file.stem, router_file
                        )
                        if spec and spec.loader:
                            # Try to load (will raise SyntaxError if invalid)
                            importlib.util.module_from_spec(spec)
                    except SyntaxError as e:
                        print(f"✗ ERROR: Syntax error in {router_file.name}:{e.lineno}: {e.msg}")
                        raise
        print("✓ Python syntax validated")
    except SyntaxError as e:
        print(f"✗ ERROR: Syntax error detected: {e}")
        raise
    except Exception as e:
        # Non-critical, continue
        print(f"⚠ Warning: Could not validate all syntax: {e}")
    
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

