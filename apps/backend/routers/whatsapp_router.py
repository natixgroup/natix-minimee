"""
WhatsApp Bridge Router
Handles WhatsApp connection status and QR code retrieval for both user and minimee accounts
"""
import os
import subprocess
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from db.database import get_db
from services.logs_service import log_structured
from services.bridge_client import get_user_bridge_status, get_minimee_bridge_status
from typing import Optional

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])


def check_bridge_status() -> dict:
    """
    Check if the WhatsApp bridge container is running
    """
    try:
        result = subprocess.run(
            ["docker", "ps", "--filter", "name=minimee-bridge", "--format", "{{.Status}}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        is_running = bool(result.stdout.strip())
        
        if is_running:
            # Check if connected by looking at recent logs
            log_result = subprocess.run(
                ["docker", "logs", "minimee-bridge", "--tail", "20"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            logs = log_result.stdout.lower()
            is_connected = "whatsapp connected successfully" in logs or "connection open" in logs
            has_qr = "qr code generated" in logs or "scan the qr code" in logs
            
            return {
                "running": True,
                "connected": is_connected,
                "has_qr": has_qr and not is_connected,
            }
        else:
            return {
                "running": False,
                "connected": False,
                "has_qr": False,
            }
    except Exception as e:
        return {
            "running": False,
            "connected": False,
            "has_qr": False,
            "error": str(e),
        }


def extract_qr_from_logs(logs: str) -> Optional[str]:
    """
    Extract QR code ASCII art from logs
    Returns the QR code section as a string
    """
    lines = logs.split('\n')
    
    for i, line in enumerate(lines):
        # Start capturing when we see QR code indication
        if 'qr code generated' in line.lower() or 'scan the qr code' in line.lower():
            # Look backwards for the QR code (it's usually printed before the message)
            start_idx = max(0, i - 25)
            # Find QR code pattern (ASCII art with block characters)
            qr_start = None
            for j in range(start_idx, i):
                if lines[j].strip() and ('█' in lines[j] or '▀' in lines[j] or '▄' in lines[j]):
                    qr_start = j
                    break
            
            if qr_start is not None:
                # Include QR code and instructions (up to 10 lines after the message)
                end_idx = min(len(lines), i + 10)
                qr_lines = lines[qr_start:end_idx]
                return '\n'.join(qr_lines)
    
    return None


@router.get("/status")
async def get_whatsapp_status(db: Session = Depends(get_db)):
    """
    Get WhatsApp bridge connection status (legacy endpoint - returns user status)
    """
    try:
        status = await get_user_bridge_status(db)
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/user/status")
async def get_user_whatsapp_status(db: Session = Depends(get_db)):
    """
    Get user WhatsApp bridge connection status
    """
    try:
        status = await get_user_bridge_status(db)
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/minimee/status")
async def get_minimee_whatsapp_status(db: Session = Depends(get_db)):
    """
    Get Minimee WhatsApp bridge connection status
    """
    try:
        status = await get_minimee_bridge_status(db)
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/qr")
async def get_whatsapp_qr(db: Session = Depends(get_db)):
    """
    Get WhatsApp QR code (legacy endpoint - returns user QR)
    """
    return await get_user_whatsapp_qr(db)


@router.get("/user/qr")
async def get_user_whatsapp_qr(db: Session = Depends(get_db)):
    """
    Get user WhatsApp QR code from bridge
    """
    try:
        import httpx
        from config import settings
        
        endpoint = f"{settings.bridge_api_url}/user/qr"
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(endpoint)
            response.raise_for_status()
            return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get user QR code: {str(e)}")


@router.get("/minimee/qr")
async def get_minimee_whatsapp_qr(db: Session = Depends(get_db)):
    """
    Get Minimee WhatsApp QR code from bridge
    """
    try:
        import httpx
        from config import settings
        
        endpoint = f"{settings.bridge_api_url}/minimee/qr"
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(endpoint)
            response.raise_for_status()
            return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get Minimee QR code: {str(e)}")


@router.post("/restart")
async def restart_whatsapp_bridge(db: Session = Depends(get_db)):
    """
    Restart the WhatsApp bridge (legacy endpoint - restarts user session)
    """
    return await restart_user_whatsapp_bridge(db)


@router.post("/user/restart")
async def restart_user_whatsapp_bridge(db: Session = Depends(get_db)):
    """
    Restart the user WhatsApp bridge session to generate a new QR code
    """
    try:
        import httpx
        from config import settings
        
        endpoint = f"{settings.bridge_api_url}/user/restart"
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(endpoint)
            response.raise_for_status()
            result = response.json()
            
            log_structured(
                db=db,
                level="INFO",
                message="User WhatsApp bridge restarted",
                service="whatsapp",
            )
            return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/minimee/restart")
async def restart_minimee_whatsapp_bridge(db: Session = Depends(get_db)):
    """
    Restart the Minimee WhatsApp bridge session to generate a new QR code
    """
    try:
        import httpx
        from config import settings
        
        endpoint = f"{settings.bridge_api_url}/minimee/restart"
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(endpoint)
            response.raise_for_status()
            result = response.json()
            
            log_structured(
                db=db,
                level="INFO",
                message="Minimee WhatsApp bridge restarted",
                service="whatsapp",
            )
            return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/start")
async def start_whatsapp_bridge(db: Session = Depends(get_db)):
    """
    Start the WhatsApp bridge (legacy endpoint - starts user session)
    """
    return await restart_user_whatsapp_bridge(db)  # Restart = start if not running

