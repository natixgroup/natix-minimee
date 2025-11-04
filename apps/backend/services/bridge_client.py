"""
Bridge client service for communicating with WhatsApp bridge
Handles sending approval requests and messages via HTTP
"""
import httpx
from typing import Dict, Any, Optional
from config import settings
from services.logs_service import log_to_db
from db.database import SessionLocal


async def send_approval_request_to_bridge(
    approval_data: Dict[str, Any],
    db = None
) -> Dict[str, Any]:
    """
    Send approval request to WhatsApp bridge
    Args:
        approval_data: Dict with keys: message_id, options (A/B/C), context_summary,
                      original_content, sender, source, recipient_info, email_subject (optional)
        db: Database session (optional, will create if not provided)
    Returns:
        Dict with bridge response including group_message_id
    """
    if db is None:
        db = SessionLocal()
        should_close = True
    else:
        should_close = False
    
    try:
        endpoint = f"{settings.bridge_api_url}/bridge/send-approval-request"
        
        log_to_db(
            db,
            "INFO",
            f"Sending approval request to bridge for message_id {approval_data.get('message_id')}",
            service="bridge_client",
            metadata={
                "message_id": approval_data.get('message_id'),
                "source": approval_data.get('source'),
                "endpoint": endpoint
            }
        )
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                endpoint,
                json=approval_data,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            result = response.json()
            
            log_to_db(
                db,
                "INFO",
                f"Approval request sent successfully, group_message_id: {result.get('group_message_id')}",
                service="bridge_client",
                metadata={
                    "message_id": approval_data.get('message_id'),
                    "group_message_id": result.get('group_message_id')
                }
            )
            
            return result
            
    except httpx.TimeoutException:
        error_msg = f"Bridge timeout when sending approval request for message_id {approval_data.get('message_id')}"
        log_to_db(db, "ERROR", error_msg, service="bridge_client")
        raise Exception(error_msg)
    except httpx.HTTPStatusError as e:
        error_msg = f"Bridge HTTP error {e.response.status_code}: {str(e)}"
        log_to_db(
            db,
            "ERROR",
            error_msg,
            service="bridge_client",
            metadata={
                "message_id": approval_data.get('message_id'),
                "status_code": e.response.status_code,
                "response": e.response.text[:500] if e.response.text else None
            }
        )
        raise Exception(error_msg)
    except Exception as e:
        error_msg = f"Bridge client error: {str(e)}"
        log_to_db(
            db,
            "ERROR",
            error_msg,
            service="bridge_client",
            metadata={
                "message_id": approval_data.get('message_id'),
                "error": str(e)
            }
        )
        raise
    finally:
        if should_close:
            db.close()


async def send_message_via_bridge(
    recipient: str,
    message_text: str,
    source: str,  # 'whatsapp' or 'gmail'
    db = None,
    integration_type: str = 'user'  # 'user' or 'minimee' - which account to use
) -> Dict[str, Any]:
    """
    Send final message via bridge to recipient
    Args:
        recipient: JID for WhatsApp or email for Gmail
        message_text: Message content to send
        source: 'whatsapp' or 'gmail'
        db: Database session (optional)
        integration_type: 'user' or 'minimee' - which WhatsApp account to use
    Returns:
        Dict with bridge response
    """
    if db is None:
        db = SessionLocal()
        should_close = True
    else:
        should_close = False
    
    try:
        # Use the appropriate endpoint based on integration type
        endpoint = f"{settings.bridge_api_url}/{integration_type}/send"
        
        payload = {
            "recipient": recipient,
            "message": message_text,
            "source": source
        }
        
        log_to_db(
            db,
            "INFO",
            f"Sending message via bridge ({integration_type}) to {recipient}",
            service="bridge_client",
            metadata={
                "recipient": recipient,
                "source": source,
                "integration_type": integration_type,
                "message_preview": message_text[:100]
            }
        )
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                endpoint,
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            result = response.json()
            
            log_to_db(
                db,
                "INFO",
                f"Message sent successfully via bridge ({integration_type})",
                service="bridge_client",
                metadata={
                    "recipient": recipient,
                    "source": source,
                    "integration_type": integration_type,
                    "sent": result.get("sent", False)
                }
            )
            
            return result
            
    except httpx.TimeoutException:
        error_msg = f"Bridge timeout when sending message to {recipient}"
        log_to_db(db, "ERROR", error_msg, service="bridge_client")
        raise Exception(error_msg)
    except httpx.HTTPStatusError as e:
        error_msg = f"Bridge HTTP error {e.response.status_code} when sending message"
        log_to_db(
            db,
            "ERROR",
            error_msg,
            service="bridge_client",
            metadata={
                "recipient": recipient,
                "status_code": e.response.status_code
            }
        )
        raise Exception(error_msg)
    except Exception as e:
        error_msg = f"Bridge client error when sending message: {str(e)}"
        log_to_db(
            db,
            "ERROR",
            error_msg,
            service="bridge_client",
            metadata={
                "recipient": recipient,
                "error": str(e)
            }
        )
        raise
    finally:
        if should_close:
            db.close()


async def send_message_via_user_bridge(
    recipient: str,
    message_text: str,
    source: str = 'whatsapp',
    db = None
) -> Dict[str, Any]:
    """Send message via user WhatsApp account"""
    return await send_message_via_bridge(recipient, message_text, source, db, integration_type='user')


async def send_message_via_minimee_bridge(
    recipient: str,
    message_text: str,
    source: str = 'whatsapp',
    db = None
) -> Dict[str, Any]:
    """Send message via Minimee WhatsApp account"""
    return await send_message_via_bridge(recipient, message_text, source, db, integration_type='minimee')


async def get_user_bridge_status(db = None) -> Dict[str, Any]:
    """Get status of user WhatsApp bridge"""
    if db is None:
        db = SessionLocal()
        should_close = True
    else:
        should_close = False
    
    try:
        endpoint = f"{settings.bridge_api_url}/user/status"
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(endpoint)
            response.raise_for_status()
            return response.json()
    except Exception as e:
        return {"status": "error", "error": str(e)}
    finally:
        if should_close:
            db.close()


async def get_minimee_bridge_status(db = None) -> Dict[str, Any]:
    """Get status of Minimee WhatsApp bridge"""
    if db is None:
        db = SessionLocal()
        should_close = True
    else:
        should_close = False
    
    try:
        endpoint = f"{settings.bridge_api_url}/minimee/status"
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(endpoint)
            response.raise_for_status()
            return response.json()
    except Exception as e:
        return {"status": "error", "error": str(e)}
    finally:
        if should_close:
            db.close()

