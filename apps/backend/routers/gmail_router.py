"""
Gmail integration endpoints
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from db.database import get_db
from models import User, OAuthToken
from schemas import GmailFetchRequest, GmailThreadResponse
from services.gmail_service import (
    get_oauth_flow, store_oauth_token, fetch_gmail_threads
)
from config import settings

router = APIRouter()


@router.get("/auth/gmail/start")
async def start_gmail_oauth(
    user_id: int = 1,  # TODO: Get from auth
    db: Session = Depends(get_db)
):
    """
    Initiate Gmail OAuth flow
    Returns authorization URL
    """
    try:
        flow = get_oauth_flow()
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true'
        )
        # TODO: Store state in session/DB for verification
        return {"authorization_url": authorization_url, "state": state}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/auth/gmail/callback")
async def gmail_oauth_callback(
    code: str,
    state: str,
    user_id: int = 1,  # TODO: Get from auth/session
    db: Session = Depends(get_db)
):
    """
    Handle Gmail OAuth callback
    """
    try:
        flow = get_oauth_flow()
        flow.fetch_token(code=code)
        
        credentials = flow.credentials
        
        store_oauth_token(
            db=db,
            user_id=user_id,
            access_token=credentials.token,
            refresh_token=credentials.refresh_token,
            expires_at=credentials.expiry
        )
        
        return {"message": "Gmail OAuth successful", "status": "connected"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/gmail/status")
async def gmail_status(
    user_id: int = 1,  # TODO: Get from auth
    db: Session = Depends(get_db)
):
    """
    Check Gmail OAuth connection status
    """
    try:
        from services.gmail_service import get_user_credentials
        
        credentials = get_user_credentials(db, user_id)
        has_token = credentials is not None
        
        return {
            "connected": has_token,
            "has_token": has_token
        }
    except Exception as e:
        return {
            "connected": False,
            "has_token": False,
            "error": str(e)
        }


@router.get("/gmail/fetch", response_model=List[GmailThreadResponse])
async def fetch_gmail(
    days: int = 30,
    only_replied: bool = True,
    user_id: int = 1,  # TODO: Get from auth
    db: Session = Depends(get_db)
):
    """
    Fetch Gmail threads from last N days
    Only includes threads where user has replied if only_replied=True
    Automatically indexes threads with embeddings
    """
    try:
        threads = await fetch_gmail_threads(
            db=db,
            user_id=user_id,
            days=days,
            only_replied=only_replied
        )
        return threads
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/gmail/draft-proposals")
async def get_draft_proposals(
    thread_id: str,
    user_id: int = 1,  # TODO: Get from auth
    db: Session = Depends(get_db)
):
    """
    Generate email draft reply options for a Gmail thread
    Returns MessageOptions format with A/B/C options
    """
    try:
        from services.email_draft import generate_email_drafts_sync
        from schemas import MessageOptions
        
        drafts = generate_email_drafts_sync(db, thread_id, user_id, num_options=3)
        
        # Create a temporary message ID (0) for the draft proposals
        # In real implementation, this might be stored differently
        return MessageOptions(
            options=drafts,
            message_id=0,  # Placeholder - email drafts don't have message_id
            conversation_id=thread_id
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

