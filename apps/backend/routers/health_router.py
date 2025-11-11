"""
Health and status endpoints
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from db.database import get_db

router = APIRouter()


@router.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """
    Health check endpoint
    Returns {"status": "ok"} if healthy
    Includes basic validation to catch runtime errors
    """
    try:
        # Verify database connection
        db.execute(text("SELECT 1"))
        
        # Verify we can import main modules (catches import errors)
        try:
            from routers import (
                health_router, settings_router, policy_router,
                agents_router, prompts_router, ingest_router
            )
        except SyntaxError as e:
            return {
                "status": "error",
                "message": f"Syntax error detected: {str(e)}",
                "type": "syntax_error"
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Import error: {str(e)}",
                "type": "import_error"
            }
        
        return {"status": "ok"}
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "type": "database_error"
        }

