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
    get_oauth_flow, store_oauth_token, fetch_gmail_threads, fetch_gmail_threads_sync
)
from services.ingestion_job import ingestion_job_manager
from config import settings
import asyncio

router = APIRouter()


@router.get("/auth/gmail/start")
async def start_gmail_oauth(
    user_id: int = 1,  # TODO: Get from auth
    force_consent: bool = False,  # Force re-authorization to get refresh_token
    db: Session = Depends(get_db)
):
    """
    Initiate Gmail OAuth flow
    Returns authorization URL
    
    Args:
        force_consent: If True, forces re-authorization to ensure refresh_token is obtained
    """
    try:
        flow = get_oauth_flow()
        
        # Check if user already has a token but no refresh_token
        oauth_token = db.query(OAuthToken).filter(
            OAuthToken.user_id == user_id,
            OAuthToken.provider == "gmail"
        ).first()
        
        # Force consent if refresh_token is missing or if explicitly requested
        prompt = 'consent' if (force_consent or (oauth_token and not oauth_token.refresh_token)) else None
        
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt=prompt
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
        
        # Validate that we have a refresh_token
        if not credentials.refresh_token:
            # Try to get existing refresh_token from DB
            existing_token = db.query(OAuthToken).filter(
                OAuthToken.user_id == user_id,
                OAuthToken.provider == "gmail"
            ).first()
            
            if existing_token and existing_token.refresh_token:
                # Keep existing refresh_token
                refresh_token = existing_token.refresh_token
            else:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "No refresh_token received from Google. "
                        "Please re-authenticate with force_consent=true to obtain a refresh token. "
                        "This is required to refresh the access token when it expires."
                    )
                )
        else:
            refresh_token = credentials.refresh_token
        
        store_oauth_token(
            db=db,
            user_id=user_id,
            access_token=credentials.token,
            refresh_token=refresh_token,
            expires_at=credentials.expiry
        )
        
        return {
            "message": "Gmail OAuth successful",
            "status": "connected",
            "has_refresh_token": bool(refresh_token)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/gmail/disconnect")
async def disconnect_gmail(
    user_id: int = 1,  # TODO: Get from auth
    db: Session = Depends(get_db)
):
    """
    Disconnect Gmail by removing OAuth token only (does NOT delete imported data)
    """
    try:
        oauth_token = db.query(OAuthToken).filter(
            OAuthToken.user_id == user_id,
            OAuthToken.provider == "gmail"
        ).first()
        
        if oauth_token:
            db.delete(oauth_token)
            db.commit()
            return {"message": "Gmail disconnected successfully"}
        else:
            return {"message": "No Gmail connection found"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/gmail/status")
async def gmail_status(
    user_id: int = 1,  # TODO: Get from auth
    db: Session = Depends(get_db)
):
    """
    Check Gmail OAuth connection status
    Returns detailed information about configuration and connection state
    """
    try:
        from services.gmail_service import get_user_credentials, get_gmail_client_credentials
        
        # Check client credentials configuration
        client_id, client_secret = get_gmail_client_credentials()
        has_client_credentials = bool(client_id and client_secret)
        
        # Check user OAuth token
        try:
            credentials = get_user_credentials(db, user_id)
            has_token = credentials is not None
            has_refresh_token = credentials.refresh_token is not None if credentials else False
        except ValueError as e:
            # This might be a missing refresh_token or missing client credentials
            error_msg = str(e)
            has_token = False
            has_refresh_token = False
            
            return {
                "connected": False,
                "has_token": False,
                "has_client_credentials": has_client_credentials,
                "has_refresh_token": has_refresh_token,
                "error": error_msg,
                "configuration_help": {
                    "client_credentials_missing": not has_client_credentials,
                    "instructions": "Configure Gmail credentials via Settings API or environment variables (GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET)"
                }
            }
        
        return {
            "connected": has_token and has_refresh_token,
            "has_token": has_token,
            "has_refresh_token": has_refresh_token,
            "has_client_credentials": has_client_credentials
        }
    except Exception as e:
        return {
            "connected": False,
            "has_token": False,
            "has_client_credentials": False,
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
    Fetch Gmail threads from last N days (synchronous - for backward compatibility)
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


@router.post("/gmail/fetch-async")
async def fetch_gmail_async(
    days: int = 30,
    only_replied: bool = True,
    user_id: int = 1,  # TODO: Get from auth
    db: Session = Depends(get_db)
):
    """
    Fetch Gmail threads asynchronously
    Creates a background job and returns job_id
    Progress can be tracked via WebSocket at /ingest/ws/{job_id}
    """
    try:
        # Create ingestion job with metadata
        job = ingestion_job_manager.create_job(
            db=db,
            user_id=user_id,
            conversation_id=None  # Gmail doesn't use conversation_id
        )
        
        # Store job metadata in progress
        job.progress = {
            "source": "gmail",
            "days": days,
            "only_replied": only_replied
        }
        db.commit()
        
        # Get the event loop for WebSocket broadcasting from background thread
        import asyncio
        try:
            main_loop = asyncio.get_event_loop()
        except RuntimeError:
            # If no loop in current thread, we'll handle it in update_job_progress
            main_loop = None
        
        # Create callback for progress updates
        # Note: This callback will be called from background thread, so it needs its own DB session
        def progress_callback(step: str, data: dict):
            from db.database import SessionLocal
            thread_db = SessionLocal()
            try:
                # Calculate percent based on step
                percent = None
                if step == "fetching":
                    current = data.get('current', 0)
                    total = data.get('total', 0)
                    if total > 0:
                        percent = (current / total) * 50  # Fetching is 50% of total
                elif step == "indexing":
                    current = data.get('current', 0)
                    total = data.get('total', 0)
                    if total > 0:
                        percent = 50 + (current / total) * 50  # Indexing is 50% of total
                elif step == "complete":
                    percent = 100
                elif step == "failed":
                    percent = 0
                
                ingestion_job_manager.update_job_progress(
                    db=thread_db,
                    job_id=job.id,
                    step=step,
                    current=data.get('current', 0),
                    total=data.get('total', 0),
                    message=data.get('message'),
                    percent=percent,
                    main_loop=main_loop,  # Pass the main loop for WebSocket broadcasting
                    **{k: v for k, v in data.items() if k not in ['step', 'current', 'total', 'message', 'percent']}
                )
            finally:
                thread_db.close()
        
        # Start job in background
        ingestion_job_manager.start_job_in_background(
            db=db,
            job_id=job.id,
            ingestion_function=fetch_gmail_threads_sync,
            user_id=user_id,
            days=days,
            only_replied=only_replied,
            progress_callback=progress_callback
        )
        
        return {"job_id": job.id, "status": job.status}
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

