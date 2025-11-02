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


# Global WebSocket manager instance
websocket_manager = WebSocketManager()

