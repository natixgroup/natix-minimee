"""
WebSocket connection manager for real-time WhatsApp message broadcasting and ingestion progress
"""
from typing import Set, Dict, List, Optional, TYPE_CHECKING
from fastapi import WebSocket
import json
import asyncio

if TYPE_CHECKING:
    from asyncio import AbstractEventLoop


class WebSocketManager:
    """Manages WebSocket connections for real-time updates"""
    
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        # Map job_id -> list of WebSocket connections listening to that job
        self.ingestion_listeners: Dict[int, List[WebSocket]] = {}
        # Store main event loop for thread-safe broadcasting
        self.main_loop: Optional["AbstractEventLoop"] = None
    
    def set_main_loop(self, loop: "AbstractEventLoop"):
        """Set the main event loop for thread-safe broadcasting"""
        self.main_loop = loop
        print(f"[WebSocket] Main event loop registered")
    
    async def connect(self, websocket: WebSocket):
        """Accept and store a new WebSocket connection"""
        await websocket.accept()
        self.active_connections.add(websocket)
        print(f"[WebSocket] New client connected. Total connections: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection"""
        self.active_connections.discard(websocket)
        print(f"[WebSocket] Client disconnected. Total connections: {len(self.active_connections)}")
    
    async def broadcast_whatsapp_message(self, message_data: dict):
        """Broadcast a WhatsApp message to all connected clients"""
        print(f"[WebSocket] Broadcasting WhatsApp message to {len(self.active_connections)} clients")
        
        if not self.active_connections:
            print("[WebSocket] No active connections, skipping broadcast")
            return
        
        message = json.dumps({
            "type": "whatsapp_message",
            "data": message_data
        })
        
        # Send to all connected clients
        disconnected = set()
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
                print(f"[WebSocket] Message sent to client successfully")
            except Exception as e:
                # Connection is closed, mark for removal
                print(f"[WebSocket] Error sending to client: {str(e)}")
                disconnected.add(connection)
        
        # Remove disconnected connections
        for connection in disconnected:
            self.disconnect(connection)
            print(f"[WebSocket] Removed disconnected client")
    
    def register_ingestion_listener(self, job_id: int, websocket: WebSocket):
        """Register a WebSocket connection to listen to a specific ingestion job"""
        if job_id not in self.ingestion_listeners:
            self.ingestion_listeners[job_id] = []
        if websocket not in self.ingestion_listeners[job_id]:
            self.ingestion_listeners[job_id].append(websocket)
        print(f"[WebSocket] Registered listener for job {job_id}. Total listeners: {len(self.ingestion_listeners[job_id])}")
    
    def unregister_ingestion_listener(self, job_id: int, websocket: WebSocket):
        """Unregister a WebSocket connection from listening to an ingestion job"""
        if job_id in self.ingestion_listeners:
            self.ingestion_listeners[job_id] = [ws for ws in self.ingestion_listeners[job_id] if ws != websocket]
            if not self.ingestion_listeners[job_id]:
                del self.ingestion_listeners[job_id]
        print(f"[WebSocket] Unregistered listener for job {job_id}")
    
    async def broadcast_ingestion_progress(self, job_id: int, progress_data: dict):
        """Broadcast ingestion progress to all listeners of a specific job"""
        if job_id not in self.ingestion_listeners:
            # Debug: log when no listeners
            if 'thread_log' in progress_data or 'message_log' in progress_data or 'indexing_log' in progress_data:
                print(f"[WebSocket] No listeners for job {job_id}, but logs are present")
            return  # No listeners for this job
        
        # Debug: log when broadcasting logs
        has_logs = 'thread_log' in progress_data or 'message_log' in progress_data or 'indexing_log' in progress_data
        if has_logs:
            print(f"[WebSocket] Broadcasting progress with logs for job {job_id} to {len(self.ingestion_listeners[job_id])} listeners")
        
        message = json.dumps({
            "type": "ingestion_progress",
            "job_id": job_id,
            "data": progress_data
        })
        
        listeners = self.ingestion_listeners[job_id].copy()
        disconnected = []
        sent_count = 0
        
        for connection in listeners:
            try:
                await connection.send_text(message)
                sent_count += 1
                if has_logs:
                    print(f"[WebSocket] Successfully sent log message to listener for job {job_id}")
            except Exception as e:
                print(f"[WebSocket] Error sending ingestion progress to listener: {str(e)}")
                disconnected.append(connection)
        
        if has_logs and sent_count > 0:
            print(f"[WebSocket] Sent log messages to {sent_count} listener(s) for job {job_id}")
        
        # Remove disconnected connections
        for connection in disconnected:
            self.unregister_ingestion_listener(job_id, connection)
            self.disconnect(connection)


# Global WebSocket manager instance
websocket_manager = WebSocketManager()

