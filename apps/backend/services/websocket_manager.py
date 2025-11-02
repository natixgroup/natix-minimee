"""
WebSocket connection manager for real-time WhatsApp message broadcasting
"""
from typing import Set
from fastapi import WebSocket
import json


class WebSocketManager:
    """Manages WebSocket connections for real-time updates"""
    
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
    
    async def connect(self, websocket: WebSocket):
        """Accept and store a new WebSocket connection"""
        await websocket.accept()
        self.active_connections.add(websocket)
    
    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection"""
        self.active_connections.discard(websocket)
    
    async def broadcast_whatsapp_message(self, message_data: dict):
        """Broadcast a WhatsApp message to all connected clients"""
        if not self.active_connections:
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
            except Exception:
                # Connection is closed, mark for removal
                disconnected.add(connection)
        
        # Remove disconnected connections
        for connection in disconnected:
            self.disconnect(connection)


# Global WebSocket manager instance
websocket_manager = WebSocketManager()

