"""
WhatsApp Bridge Router
Handles WhatsApp connection status and QR code retrieval
"""
import os
import subprocess
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from db.database import get_db
from services.logs_service import log_structured
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
    Get WhatsApp bridge connection status
    """
    try:
        status = check_bridge_status()
        return {
            "status": "connected" if status.get("connected") else ("pending" if status.get("has_qr") else "disconnected"),
            "running": status.get("running", False),
            "connected": status.get("connected", False),
            "has_qr": status.get("has_qr", False),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/qr")
async def get_whatsapp_qr(db: Session = Depends(get_db)):
    """
    Get WhatsApp QR code from bridge logs
    Returns the QR code section from logs if available
    """
    try:
        result = subprocess.run(
            ["docker", "logs", "minimee-bridge", "--tail", "100"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        
        logs = result.stdout
        
        # Check if QR code is present in logs
        if "qr code generated" in logs.lower() or "scan the qr code" in logs.lower():
            qr_section = extract_qr_from_logs(logs)
            if qr_section:
                return {
                    "qr_available": True,
                    "logs": qr_section,
                }
            else:
                # Fallback: return recent logs if QR section extraction fails
                recent_lines = logs.split('\n')[-50:]  # Last 50 lines
                return {
                    "qr_available": True,
                    "logs": '\n'.join(recent_lines),
                }
        else:
            return {
                "qr_available": False,
                "logs": None,
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get QR code: {str(e)}")


@router.post("/restart")
async def restart_whatsapp_bridge(db: Session = Depends(get_db)):
    """
    Restart the WhatsApp bridge container to generate a new QR code
    """
    try:
        result = subprocess.run(
            ["docker", "restart", "minimee-bridge"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        
        if result.returncode == 0:
            log_structured(
                db=db,
                level="INFO",
                message="WhatsApp bridge restarted",
                service="whatsapp",
            )
            return {"status": "restarted", "message": "Bridge restarted successfully"}
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to restart bridge: {result.stderr}"
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/start")
async def start_whatsapp_bridge(db: Session = Depends(get_db)):
    """
    Start the WhatsApp bridge container
    """
    try:
        result = subprocess.run(
            ["docker", "start", "minimee-bridge"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        
        if result.returncode == 0:
            log_structured(
                db=db,
                level="INFO",
                message="WhatsApp bridge started",
                service="whatsapp",
            )
            return {"status": "started", "message": "Bridge started successfully"}
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to start bridge: {result.stderr}"
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

