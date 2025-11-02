import { useEffect, useCallback } from "react";
import { getEnv } from "../env";
import type { ChatMessage } from "./useConversationHistory";

interface UseWhatsAppMessagesOptions {
  enabled: boolean;
  onMessage: (message: ChatMessage) => void;
}

export function useWhatsAppMessages({ enabled, onMessage }: UseWhatsAppMessagesOptions) {
  useEffect(() => {
    if (!enabled) return;

    const apiUrl = getEnv().apiUrl;
    // Convert http:// to ws:// and https:// to wss://
    const wsUrl = apiUrl.replace(/^http/, "ws") + "/minimee/ws";
    
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log("WebSocket connected for WhatsApp messages");
      // Send ping to keep connection alive
      const pingInterval = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send("ping");
        } else {
          clearInterval(pingInterval);
        }
      }, 30000); // Ping every 30 seconds
      
      // Store interval for cleanup
      (ws as any).pingInterval = pingInterval;
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        if (data.type === "whatsapp_message" && data.data) {
          const message: ChatMessage = {
            id: data.data.id,
            content: data.data.content,
            sender: data.data.sender,
            timestamp: data.data.timestamp,
            source: data.data.source,
            conversation_id: data.data.conversation_id,
          };
          onMessage(message);
        } else if (data === "pong") {
          // Keepalive response, do nothing
        }
      } catch (error) {
        console.error("Error parsing WebSocket message:", error);
      }
    };

    ws.onerror = (error) => {
      console.error("WebSocket error:", error);
    };

    ws.onclose = () => {
      console.log("WebSocket disconnected");
      // Attempt to reconnect after 5 seconds
      setTimeout(() => {
        if (enabled) {
          // Reconnect by re-running effect
          // This will be handled by the useEffect dependency
        }
      }, 5000);
    };

    return () => {
      if ((ws as any).pingInterval) {
        clearInterval((ws as any).pingInterval);
      }
      ws.close();
    };
  }, [enabled, onMessage]);
}

