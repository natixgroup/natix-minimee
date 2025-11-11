"""
Gmail integration service
"""
import base64
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List, Optional, Tuple, Callable, Dict
from models import GmailThread, Message, OAuthToken, User
from services.logs_service import log_to_db
from config import settings
from db.database import SessionLocal


SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']


def get_oauth_flow() -> Flow:
    """Create OAuth flow for Gmail"""
    client_id, client_secret = get_gmail_client_credentials()
    
    if not client_id or not client_secret:
        raise ValueError(
            "Gmail OAuth credentials not configured. "
            "Please configure GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET environment variables. "
            "This is a system configuration that must be set by the administrator."
        )
    
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [settings.gmail_redirect_uri]
            }
        },
        scopes=SCOPES,
        redirect_uri=settings.gmail_redirect_uri
    )
    return flow


def get_gmail_client_credentials() -> Tuple[Optional[str], Optional[str]]:
    """
    Get Gmail client_id and client_secret from DB settings first, then fallback to env vars
    Similar to get_openai_api_key pattern
    """
    # Try database first
    try:
        db = SessionLocal()
        try:
            from models import Setting
            client_id_setting = db.query(Setting).filter(
                Setting.key == "gmail_client_id",
                Setting.user_id == None
            ).first()
            client_secret_setting = db.query(Setting).filter(
                Setting.key == "gmail_client_secret",
                Setting.user_id == None
            ).first()
            
            client_id = None
            client_secret = None
            
            if client_id_setting and isinstance(client_id_setting.value, dict):
                client_id = client_id_setting.value.get("client_id")
            elif client_id_setting and isinstance(client_id_setting.value, str):
                client_id = client_id_setting.value
                
            if client_secret_setting and isinstance(client_secret_setting.value, dict):
                client_secret = client_secret_setting.value.get("client_secret")
            elif client_secret_setting and isinstance(client_secret_setting.value, str):
                client_secret = client_secret_setting.value
            
            if client_id and client_secret:
                return client_id, client_secret
        except Exception:
            pass
        finally:
            db.close()
    except Exception:
        pass
    
    # Fallback to environment variables
    client_id = settings.gmail_client_id
    client_secret = settings.gmail_client_secret
    
    return client_id, client_secret


def get_user_credentials(db: Session, user_id: int) -> Optional[Credentials]:
    """Get OAuth credentials for user"""
    oauth_token = db.query(OAuthToken).filter(
        OAuthToken.user_id == user_id,
        OAuthToken.provider == "gmail"
    ).first()
    
    if not oauth_token:
        return None
    
    # Get client credentials from DB or env
    client_id, client_secret = get_gmail_client_credentials()
    
    if not client_id or not client_secret:
        raise ValueError(
            "Gmail OAuth credentials not configured. "
            "Please configure GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET environment variables. "
            "This is a system configuration that must be set by the administrator."
        )
    
    if not oauth_token.refresh_token:
        raise ValueError(
            "Gmail refresh_token is missing. Please re-authenticate Gmail to obtain a refresh token. "
            "This is required to refresh the access token when it expires."
        )
    
    credentials = Credentials(
        token=oauth_token.access_token,
        refresh_token=oauth_token.refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret
    )
    
    if credentials.expired and credentials.refresh_token:
        from google.auth.transport.requests import Request
        try:
            credentials.refresh(Request())
            # Update token in DB
            oauth_token.access_token = credentials.token
            if credentials.refresh_token:
                oauth_token.refresh_token = credentials.refresh_token
            oauth_token.expires_at = credentials.expiry
            db.commit()
        except Exception as e:
            db.rollback()
            raise ValueError(
                f"Failed to refresh Gmail access token: {str(e)}. "
                "Please re-authenticate Gmail."
            ) from e
    
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


def fetch_gmail_threads_sync(
    db: Session,
    user_id: int,
    days: int = 30,
    only_replied: bool = True,
    progress_callback: Optional[Callable[[str, Dict], None]] = None,
    job_id: Optional[int] = None
) -> Dict:
    """
    Fetch Gmail threads from last N days (synchronous version with progress tracking)
    Only includes threads where user has replied if only_replied=True
    
    Returns:
        {
            'threads_created': int,
            'messages_created': int,
            'chunks_created': int,
            'embeddings_created': int,
            'thread_ids': List[int],
            'thread_count': int
        }
    """
    def _emit_progress(step: str, data: Dict):
        """Helper to emit progress"""
        if progress_callback:
            progress_callback(step, data)
    
    stats = {
        'threads_created': 0,
        'messages_created': 0,
        'chunks_created': 0,
        'embeddings_created': 0,
        'thread_ids': [],
        'thread_count': 0
    }
    
    try:
        _emit_progress("fetching", {
            "step": "fetching",
            "message": "Connecting to Gmail...",
            "current": 0,
            "total": 0
        })
        
        credentials = get_user_credentials(db, user_id)
        if not credentials:
            raise ValueError("Gmail OAuth not configured for user")
        
        service = build('gmail', 'v1', credentials=credentials)
        
        # Calculate date threshold
        date_threshold = datetime.now() - timedelta(days=days)
        query = f"after:{int(date_threshold.timestamp())}"
        
        if only_replied:
            query += " from:me"  # Only emails user has sent
        
        _emit_progress("fetching", {
            "step": "fetching",
            "message": "Fetching thread list from Gmail...",
            "current": 0,
            "total": 0
        })
        
        results = service.users().threads().list(
            userId='me',
            q=query,
            maxResults=100
        ).execute()
        
        threads_data = results.get('threads', [])
        total_threads = len(threads_data)
        
        _emit_progress("fetching", {
            "step": "fetching",
            "message": f"Found {total_threads} threads. Processing...",
            "current": 0,
            "total": total_threads
        })
        
        stored_threads = []
        
        for idx, thread_data in enumerate(threads_data):
            # Check if job was cancelled
            if job_id:
                from models import IngestionJob
                job_check = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
                if job_check and job_check.status == 'cancelled':
                    _emit_progress("cancelled", {
                        "step": "cancelled",
                        "message": "Import cancelled by user",
                        "current": idx,
                        "total": total_threads
                    })
                    return stats
            
            thread_id = thread_data['id']
            
            _emit_progress("fetching", {
                "step": "fetching",
                "message": f"Processing thread {idx + 1}/{total_threads}...",
                "current": idx + 1,
                "total": total_threads
            })
            
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
            
            # Emit detailed log for this thread
            _emit_progress("fetching", {
                "step": "fetching",
                "message": f"Processing thread {idx + 1}/{total_threads}...",
                "current": idx + 1,
                "total": total_threads,
                "thread_log": {
                    "thread_id": thread_id,
                    "subject": subject or "(No subject)",
                    "participants": participants[:3],  # Limit to first 3
                    "message_count": len(messages),
                    "last_date": last_date.isoformat()
                }
            })
            
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
            stats['threads_created'] += 1
            
            # Store messages
            for msg_idx, msg in enumerate(messages):
                msg_headers = msg.get('payload', {}).get('headers', [])
                from_addr = next((h['value'] for h in msg_headers if h['name'] == 'From'), None)
                date_str = next((h['value'] for h in msg_headers if h['name'] == 'Date'), None)
                
                # Extract body (simplified - real implementation needs to handle MIME)
                body = ""
                payload = msg.get('payload', {})
                if 'parts' in payload:
                    for part in payload['parts']:
                        if part.get('mimeType') == 'text/plain':
                            data = part.get('body', {}).get('data', '')
                            if data:
                                try:
                                    body = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                                except:
                                    body = data
                            break
                elif payload.get('mimeType') == 'text/plain':
                    data = payload.get('body', {}).get('data', '')
                    if data:
                        try:
                            body = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                        except:
                            body = data
                
                msg_date = datetime.fromtimestamp(int(msg['internalDate']) / 1000) if msg.get('internalDate') else datetime.now()
                
                # Emit detailed log for each message (only first 3 messages per thread to avoid spam)
                if msg_idx < 3:
                    body_preview = body[:100] + "..." if body and len(body) > 100 else (body or "[Email body not parsed]")
                    _emit_progress("fetching", {
                        "step": "fetching",
                        "message": f"Processing thread {idx + 1}/{total_threads}...",
                        "current": idx + 1,
                        "total": total_threads,
                        "message_log": {
                            "thread_id": thread_id,
                            "from": from_addr or "unknown",
                            "subject": subject or "(No subject)",
                            "body_preview": body_preview,
                            "date": msg_date.isoformat()
                        }
                    })
                
                message = Message(
                    content=body or "[Email body not parsed]",
                    sender=from_addr or "unknown",
                    timestamp=msg_date,
                    source="gmail",
                    conversation_id=thread_id,
                    user_id=user_id
                )
                db.add(message)
                stats['messages_created'] += 1
            
            stored_threads.append(gmail_thread)
        
        db.commit()
        
        # Index threads with embeddings
        from services.gmail_indexing import index_gmail_thread
        
        _emit_progress("indexing", {
            "step": "indexing",
            "message": "Indexing threads with embeddings...",
            "current": 0,
            "total": len(stored_threads)
        })
        
        # Index each thread
        for idx, thread_obj in enumerate(stored_threads):
            # Check if job was cancelled
            if job_id:
                from models import IngestionJob
                job_check = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
                if job_check and job_check.status == 'cancelled':
                    _emit_progress("cancelled", {
                        "step": "cancelled",
                        "message": "Import cancelled by user",
                        "current": idx,
                        "total": len(stored_threads)
                    })
                    return stats
            
            thread_id = thread_obj.thread_id
            thread = service.users().threads().get(userId='me', id=thread_id).execute()
            messages = thread.get('messages', [])
            
            if messages:
                try:
                    thread_obj = stored_threads[idx]
                    # Create a wrapper callback that preserves global thread progress
                    def thread_indexing_callback(step: str, data: Dict):
                        """Wrapper that emits indexing logs without changing global progress"""
                        # Only emit indexing_log, don't change current/total which are thread-based
                        if 'indexing_log' in data:
                            _emit_progress("indexing", {
                                "step": "indexing",
                                "message": f"Indexing thread {idx + 1}/{len(stored_threads)}...",
                                "current": idx + 1,  # Keep thread-based progress
                                "total": len(stored_threads),  # Keep thread-based progress
                                "indexing_log": data.get('indexing_log')
                            })
                        else:
                            # For other logs, just forward
                            _emit_progress(step, data)
                    
                    _emit_progress("indexing", {
                        "step": "indexing",
                        "message": f"Indexing thread {idx + 1}/{len(stored_threads)}...",
                        "current": idx + 1,
                        "total": len(stored_threads),
                        "indexing_log": {
                            "thread_id": thread_id,
                            "subject": thread_obj.subject or "(No subject)",
                            "participants": thread_obj.participants[:2] if thread_obj.participants else [],
                            "chunks": 0,  # Will be updated after indexing
                            "embeddings": 0  # Will be updated after indexing
                        }
                    })
                    
                    index_stats = index_gmail_thread(db, thread_id, messages, user_id, progress_callback=thread_indexing_callback)
                    chunks = index_stats.get('chunks_created', 0)
                    embeddings = index_stats.get('embeddings_created', 0)
                    stats['chunks_created'] += chunks
                    stats['embeddings_created'] += embeddings
                    
                    # Emit completion log for indexing
                    _emit_progress("indexing", {
                        "step": "indexing",
                        "message": f"Indexing thread {idx + 1}/{len(stored_threads)}...",
                        "current": idx + 1,
                        "total": len(stored_threads),
                        "indexing_log": {
                            "thread_id": thread_id,
                            "subject": thread_obj.subject or "(No subject)",
                            "chunks": chunks,
                            "embeddings": embeddings,
                            "status": "completed"
                        }
                    })
                except Exception as e:
                    log_to_db(db, "ERROR", f"Failed to index thread {thread_id}: {str(e)}", service="gmail_service")
                    _emit_progress("indexing", {
                        "step": "indexing",
                        "message": f"Error indexing thread {idx + 1}/{len(stored_threads)}...",
                        "current": idx + 1,
                        "total": len(stored_threads),
                        "indexing_log": {
                            "thread_id": thread_id,
                            "error": str(e),
                            "status": "failed"
                        }
                    })
        
        for thread in stored_threads:
            db.refresh(thread)
        
        # Store thread IDs instead of full objects (for JSON serialization)
        stats['thread_ids'] = [thread.id for thread in stored_threads]
        stats['thread_count'] = len(stored_threads)
        
        _emit_progress("complete", {
            "step": "complete",
            "message": f"Successfully imported {stats['threads_created']} threads",
            "current": len(stored_threads),
            "total": len(stored_threads),
            "stats": stats
        })
        
        log_to_db(db, "INFO", f"Fetched and indexed {len(stored_threads)} Gmail threads", service="gmail_service")
        
        return stats
    
    except Exception as e:
        db.rollback()
        _emit_progress("failed", {
            "step": "failed",
            "message": f"Error: {str(e)}",
            "error": str(e)
        })
        log_to_db(db, "ERROR", f"Gmail fetch error: {str(e)}", service="gmail_service")
        raise


async def fetch_gmail_threads(
    db: Session,
    user_id: int,
    days: int = 30,
    only_replied: bool = True
) -> List[GmailThread]:
    """
    Fetch Gmail threads from last N days (async wrapper for backward compatibility)
    Only includes threads where user has replied if only_replied=True
    """
    result = fetch_gmail_threads_sync(db, user_id, days, only_replied)
    # Fetch threads by IDs
    thread_ids = result.get('thread_ids', [])
    if thread_ids:
        threads = db.query(GmailThread).filter(GmailThread.id.in_(thread_ids)).all()
        return threads
    return []

