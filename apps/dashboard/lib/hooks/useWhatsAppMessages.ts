import { useEffect, useRef, useCallback } from "react";
import { getEnv } from "../env";
import type { ChatMessage } from "./useConversationHistory";

interface UseWhatsAppMessagesOptions {
  enabled: boolean;
  onMessage: (message: ChatMessage) => void;
}

// Check if backend is available by attempting a health check
async function checkBackendAvailability(apiUrl: string): Promise<boolean> {
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 2000); // 2 second timeout
    
    const response = await fetch(`${apiUrl}/health`, {
      method: "GET",
      signal: controller.signal,
    });
    
    clearTimeout(timeoutId);
    return response.ok;
  } catch {
    return false;
  }
}

export function useWhatsAppMessages({ enabled, onMessage }: UseWhatsAppMessagesOptions) {
  const wsRef = useRef<WebSocket | null>(null);
  const pingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const isConnectingRef = useRef(false);
  const isMountedRef = useRef(true);

  // Cleanup function
  const cleanup = useCallback(() => {
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current);
      pingIntervalRef.current = null;
    }
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    if (wsRef.current) {
      try {
        wsRef.current.onerror = null;
        wsRef.current.onclose = null;
        wsRef.current.close();
      } catch {
        // Ignore errors during cleanup
      }
      wsRef.current = null;
    }
  }, []);

  // Connect to WebSocket with exponential backoff
  const connect = useCallback(async () => {
    if (!enabled || !isMountedRef.current || isConnectingRef.current) return;

    const apiUrl = getEnv().apiUrl;
    
    // Check backend availability first
    const isAvailable = await checkBackendAvailability(apiUrl);
    if (!isAvailable) {
      // Backend not available, retry with exponential backoff
      const delay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 30000); // Max 30s
      reconnectAttemptsRef.current += 1;
      
      if (isMountedRef.current && enabled) {
        reconnectTimeoutRef.current = setTimeout(() => {
          if (isMountedRef.current && enabled) {
            connect();
          }
        }, delay);
      }
      return;
    }

    // Reset reconnect attempts on successful availability check
    reconnectAttemptsRef.current = 0;
    isConnectingRef.current = true;

    // Convert http:// to ws:// and https:// to wss://
    const wsUrl = apiUrl.replace(/^http/, "ws") + "/minimee/ws";
    
    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        if (!isMountedRef.current) {
          ws.close();
          return;
        }
        
        isConnectingRef.current = false;
        reconnectAttemptsRef.current = 0; // Reset on successful connection
        
        // Send ping to keep connection alive
        pingIntervalRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN && isMountedRef.current) {
            try {
              ws.send("ping");
            } catch {
              // Ignore send errors
            }
          } else {
            if (pingIntervalRef.current) {
              clearInterval(pingIntervalRef.current);
              pingIntervalRef.current = null;
            }
          }
        }, 30000); // Ping every 30 seconds
      };

      ws.onmessage = (event) => {
        if (!isMountedRef.current) return;

        // Handle keepalive "pong" first (not JSON)
        if (event.data === "pong") {
          return;
        }

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
          }
        } catch (error) {
          // Only log parsing errors for non-pong messages that aren't JSON
          if (event.data !== "pong" && typeof event.data === "string" && event.data.trim().startsWith("{")) {
            // Silently ignore - likely malformed JSON
          }
        }
      };

      ws.onerror = () => {
        // Don't log errors - they're expected when backend is unavailable
        // The onclose handler will handle reconnection
        isConnectingRef.current = false;
      };

      ws.onclose = (event) => {
        isConnectingRef.current = false;
        
        if (!isMountedRef.current || !enabled) return;

        // Only attempt reconnect if not a clean close and still enabled
        if (!event.wasClean) {
          const delay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 30000); // Max 30s
          reconnectAttemptsRef.current += 1;
          
          reconnectTimeoutRef.current = setTimeout(() => {
            if (isMountedRef.current && enabled) {
              connect();
            }
          }, delay);
        }
      };
    } catch (error) {
      isConnectingRef.current = false;
      // Don't log connection errors - they're expected when backend is unavailable
      
      // Retry with exponential backoff
      if (isMountedRef.current && enabled) {
        const delay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 30000);
        reconnectAttemptsRef.current += 1;
        
        reconnectTimeoutRef.current = setTimeout(() => {
          if (isMountedRef.current && enabled) {
            connect();
          }
        }, delay);
      }
    }
  }, [enabled, onMessage]);

  useEffect(() => {
    isMountedRef.current = true;
    
    if (enabled) {
      connect();
    } else {
      cleanup();
    }

    return () => {
      isMountedRef.current = false;
      cleanup();
    };
  }, [enabled, connect, cleanup]);
}

