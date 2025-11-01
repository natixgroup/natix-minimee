"""
Gmail integration service
"""
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List, Optional
from models import GmailThread, Message, OAuthToken, User
from services.logs_service import log_to_db
from config import settings


SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']


def get_oauth_flow() -> Flow:
    """Create OAuth flow for Gmail"""
    if not settings.gmail_client_id or not settings.gmail_client_secret:
        raise ValueError("Gmail OAuth credentials not configured")
    
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": settings.gmail_client_id,
                "client_secret": settings.gmail_client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [settings.gmail_redirect_uri]
            }
        },
        scopes=SCOPES,
        redirect_uri=settings.gmail_redirect_uri
    )
    return flow


def get_user_credentials(db: Session, user_id: int) -> Optional[Credentials]:
    """Get OAuth credentials for user"""
    oauth_token = db.query(OAuthToken).filter(
        OAuthToken.user_id == user_id,
        OAuthToken.provider == "gmail"
    ).first()
    
    if not oauth_token:
        return None
    
    credentials = Credentials(
        token=oauth_token.access_token,
        refresh_token=oauth_token.refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.gmail_client_id,
        client_secret=settings.gmail_client_secret
    )
    
    if credentials.expired and credentials.refresh_token:
        from google.auth.transport.requests import Request
        credentials.refresh(Request())
        # Update token in DB
        oauth_token.access_token = credentials.token
        if credentials.refresh_token:
            oauth_token.refresh_token = credentials.refresh_token
        oauth_token.expires_at = credentials.expiry
        db.commit()
    
    return credentials


def store_oauth_token(
    db: Session,
    user_id: int,
    access_token: str,
    refresh_token: Optional[str],
    expires_at: Optional[datetime]
):
    """Store or update OAuth token"""
    oauth_token = db.query(OAuthToken).filter(
        OAuthToken.user_id == user_id,
        OAuthToken.provider == "gmail"
    ).first()
    
    if oauth_token:
        oauth_token.access_token = access_token
        if refresh_token:
            oauth_token.refresh_token = refresh_token
        if expires_at:
            oauth_token.expires_at = expires_at
    else:
        oauth_token = OAuthToken(
            provider="gmail",
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
            user_id=user_id
        )
        db.add(oauth_token)
    
    db.commit()
    return oauth_token


async def fetch_gmail_threads(
    db: Session,
    user_id: int,
    days: int = 30,
    only_replied: bool = True
) -> List[GmailThread]:
    """
    Fetch Gmail threads from last N days
    Only includes threads where user has replied if only_replied=True
    """
    try:
        credentials = get_user_credentials(db, user_id)
        if not credentials:
            raise ValueError("Gmail OAuth not configured for user")
        
        service = build('gmail', 'v1', credentials=credentials)
        
        # Calculate date threshold
        date_threshold = datetime.now() - timedelta(days=days)
        query = f"after:{int(date_threshold.timestamp())}"
        
        if only_replied:
            query += " from:me"  # Only emails user has sent
        
        results = service.users().threads().list(
            userId='me',
            q=query,
            maxResults=100
        ).execute()
        
        threads_data = results.get('threads', [])
        stored_threads = []
        
        for thread_data in threads_data:
            thread_id = thread_data['id']
            
            # Check if already stored
            existing = db.query(GmailThread).filter(
                GmailThread.thread_id == thread_id
            ).first()
            
            if existing:
                stored_threads.append(existing)
                continue
            
            # Get thread details
            thread = service.users().threads().get(
                userId='me',
                id=thread_id
            ).execute()
            
            messages = thread.get('messages', [])
            if not messages:
                continue
            
            # Get subject and participants
            first_msg = messages[0]
            headers = first_msg.get('payload', {}).get('headers', [])
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), None)
            participants = []
            for msg in messages:
                msg_headers = msg.get('payload', {}).get('headers', [])
                from_addr = next((h['value'] for h in msg_headers if h['name'] == 'From'), None)
                if from_addr and from_addr not in participants:
                    participants.append(from_addr)
            
            last_message = messages[-1]
            last_date = datetime.fromtimestamp(int(last_message['internalDate']) / 1000)
            
            # Store thread
            gmail_thread = GmailThread(
                thread_id=thread_id,
                subject=subject,
                participants=participants,
                last_message_date=last_date,
                user_id=user_id
            )
            db.add(gmail_thread)
            db.flush()
            
            # Store messages
            for msg in messages:
                msg_headers = msg.get('payload', {}).get('headers', [])
                from_addr = next((h['value'] for h in msg_headers if h['name'] == 'From'), None)
                date_str = next((h['value'] for h in msg_headers if h['name'] == 'Date'), None)
                
                # Extract body (simplified - real implementation needs to handle MIME)
                body = ""
                payload = msg.get('payload', {})
                if 'parts' in payload:
                    for part in payload['parts']:
                        if part.get('mimeType') == 'text/plain':
                            body = part.get('body', {}).get('data', '')
                            break
                
                msg_date = datetime.fromtimestamp(int(msg['internalDate']) / 1000) if msg.get('internalDate') else datetime.now()
                
                message = Message(
                    content=body or "[Email body not parsed]",
                    sender=from_addr or "unknown",
                    timestamp=msg_date,
                    source="gmail",
                    conversation_id=thread_id,
                    user_id=user_id
                )
                db.add(message)
            
            stored_threads.append(gmail_thread)
        
        db.commit()
        
        # Index threads with embeddings (import here to avoid circular dependency)
        from services.gmail_indexing import index_gmail_thread
        
        # Index each thread
        for thread_data in threads_data:
            thread_id = thread_data['id']
            thread = service.users().threads().get(userId='me', id=thread_id).execute()
            messages = thread.get('messages', [])
            
            if messages:
                try:
                    index_gmail_thread(db, thread_id, messages, user_id)
                except Exception as e:
                    log_to_db(db, "ERROR", f"Failed to index thread {thread_id}: {str(e)}", service="gmail_service")
        
        for thread in stored_threads:
            db.refresh(thread)
        
        log_to_db(db, "INFO", f"Fetched and indexed {len(stored_threads)} Gmail threads", service="gmail_service")
        
        return stored_threads
    
    except Exception as e:
        db.rollback()
        log_to_db(db, "ERROR", f"Gmail fetch error: {str(e)}", service="gmail_service")
        raise

