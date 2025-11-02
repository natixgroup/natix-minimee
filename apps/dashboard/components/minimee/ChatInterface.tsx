"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Send, Loader2, MessageSquare, Info } from "lucide-react";
import { toast } from "sonner";
import { useChatStream } from "@/lib/hooks/useChatStream";
import { useConversationHistory, type ChatMessage } from "@/lib/hooks/useConversationHistory";
import { useWhatsAppMessages } from "@/lib/hooks/useWhatsAppMessages";
import { ApprovalDialog, type MessageOptions } from "./ApprovalDialog";
import { DebugModal } from "./DebugModal";

interface ChatInterfaceProps {
  userId: number;
  conversationId: string;
}

export function ChatInterface({ userId, conversationId }: ChatInterfaceProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [showWhatsApp, setShowWhatsApp] = useState(true); // Default to true to show WhatsApp messages
  const [streamingMessage, setStreamingMessage] = useState("");
  const [actions, setActions] = useState<any[]>([]);
  const [messageOptions, setMessageOptions] = useState<MessageOptions | null>(null);
  const [showApprovalDialog, setShowApprovalDialog] = useState(false);
  const [debugInfos, setDebugInfos] = useState<Map<number, any>>(new Map());
  const [selectedDebugMessageId, setSelectedDebugMessageId] = useState<number | null>(null);
  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const { sendMessage, isStreaming } = useChatStream();
  
  const { data: historyData, isLoading: isLoadingHistory } = useConversationHistory(
    conversationId,
    userId,
    true
  );

  // Load history when available
  useEffect(() => {
    if (historyData) {
      // Sort messages by timestamp to ensure correct order
      const sorted = [...historyData].sort((a, b) => {
        const timeA = new Date(a.timestamp).getTime();
        const timeB = new Date(b.timestamp).getTime();
        return timeA - timeB;
      });
      setMessages(sorted);
    }
  }, [historyData]);

  // Handle WhatsApp messages received via WebSocket
  const handleWhatsAppMessage = useCallback((message: ChatMessage) => {
    console.log("handleWhatsAppMessage called with:", message);
    // Only add messages for this conversation
    if (message.conversation_id !== conversationId) {
      console.log("Message conversation_id mismatch, skipping:", message.conversation_id, "expected:", conversationId);
      return;
    }
    setMessages((prev) => {
      // Avoid duplicates
      if (prev.some((m) => m.id === message.id)) {
        console.log("Message already exists, skipping:", message.id);
        return prev;
      }
      console.log("Adding WhatsApp message to chat:", message);
      // Add message and sort by timestamp to maintain chronological order
      const updated = [...prev, message];
      return updated.sort((a, b) => {
        const timeA = new Date(a.timestamp).getTime();
        const timeB = new Date(b.timestamp).getTime();
        return timeA - timeB;
      });
    });
  }, [conversationId]);

  // Connect to WebSocket for WhatsApp messages
  useWhatsAppMessages({
    enabled: true, // Always enabled, filtered by toggle in display
    onMessage: handleWhatsAppMessage,
  });

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingMessage]);

  const handleSend = useCallback(() => {
    if (!input.trim() || isStreaming) return;

    const userMessage: ChatMessage = {
      id: Date.now(), // Temporary ID
      content: input.trim(),
      sender: "User",
      timestamp: new Date().toISOString(),
      source: "dashboard",
      conversation_id: conversationId,
    };

    // Add user message immediately
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setStreamingMessage("");
    setActions([]);

    // Send to backend and stream response
    sendMessage(
      input.trim(),
      userId,
      conversationId,
      (token) => {
        setStreamingMessage((prev) => prev + token);
      },
      (response, responseActions, debugInfo) => {
        const minimeeMessage: ChatMessage = {
          id: Date.now() + 1, // Temporary ID
          content: response,
          sender: "Minimee",
          timestamp: new Date().toISOString(),
          source: "minimee",
          conversation_id: conversationId,
        };

        setMessages((prev) => [...prev, minimeeMessage]);
        setStreamingMessage("");
        
        // Store debug info
        if (debugInfo) {
          setDebugInfos((prev) => {
            const newMap = new Map(prev);
            newMap.set(minimeeMessage.id, debugInfo);
            return newMap;
          });
        }
        
        if (responseActions && responseActions.length > 0) {
          setActions(responseActions);
          setMessageOptions({
            message_id: minimeeMessage.id,
            conversation_id: conversationId,
            options: responseActions.map((a: any) => a.text || a.options?.join(" / ") || ""),
          });
          setShowApprovalDialog(true);
        }
        
        // Remettre le focus sur l'input après la réponse
        setTimeout(() => {
          inputRef.current?.focus();
        }, 100);
      }
    );
  }, [input, userId, conversationId, isStreaming, sendMessage]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // Filter messages based on WhatsApp toggle
  const displayedMessages = showWhatsApp
    ? messages
    : messages.filter((msg) => msg.source !== "whatsapp");
  
  // Debug log
  useEffect(() => {
    console.log("Messages state:", messages.length, "Displayed:", displayedMessages.length, "ShowWhatsApp:", showWhatsApp);
  }, [messages, displayedMessages, showWhatsApp]);

  return (
    <div className="flex flex-col h-full">
      <Card className="flex-1 flex flex-col min-h-0">
        <CardHeader className="flex-shrink-0">
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              <MessageSquare className="h-5 w-5" />
              Chat Minimee
            </CardTitle>
            <div className="flex items-center gap-2">
              <Label htmlFor="whatsapp-toggle" className="text-sm">
                Afficher WhatsApp
              </Label>
              <Switch
                id="whatsapp-toggle"
                checked={showWhatsApp}
                onCheckedChange={setShowWhatsApp}
              />
            </div>
          </div>
        </CardHeader>
        
        <CardContent className="flex-1 flex flex-col min-h-0 p-4">
          {/* Messages area */}
          <div className="flex-1 overflow-y-auto space-y-4 mb-4">
            {isLoadingHistory ? (
              <div className="flex items-center justify-center h-full">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            ) : (
              <>
                {displayedMessages.map((msg) => (
                  <div
                    key={msg.id}
                    className={`flex ${
                      msg.sender === "User" || (msg.source === "whatsapp" && msg.sender !== "Minimee")
                        ? "justify-end"
                        : "justify-start"
                    }`}
                  >
                    <div
                      className={`max-w-[80%] rounded-lg px-4 py-2 relative ${
                        msg.sender === "User" || (msg.source === "whatsapp" && msg.sender !== "Minimee")
                          ? "bg-primary text-primary-foreground"
                          : "bg-muted"
                      }`}
                    >
                      {/* Show WhatsApp badge for all WhatsApp messages */}
                      {msg.source === "whatsapp" && (
                        <Badge variant="secondary" className="mb-1 text-xs">
                          WhatsApp
                        </Badge>
                      )}
                      {msg.sender === "Minimee" && (
                        <div className="flex items-center justify-between mb-1">
                          <div className="text-xs font-semibold">Minimee:</div>
                          {debugInfos.has(msg.id) && (
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-6 px-2 text-xs"
                              onClick={() => setSelectedDebugMessageId(msg.id)}
                            >
                              <Info className="h-3 w-3 mr-1" />
                              Debug
                            </Button>
                          )}
                        </div>
                      )}
                      <div className="whitespace-pre-wrap">{msg.content}</div>
                      <div className="text-xs opacity-70 mt-1">
                        {new Date(msg.timestamp).toLocaleTimeString()}
                      </div>
                    </div>
                  </div>
                ))}
                
                {/* Streaming message */}
                {streamingMessage && (
                  <div className="flex justify-start">
                    <div className="max-w-[80%] rounded-lg px-4 py-2 bg-muted">
                      <div className="text-xs font-semibold mb-1">Minimee:</div>
                      <div className="whitespace-pre-wrap">
                        {streamingMessage}
                        <span className="animate-pulse">▊</span>
                      </div>
                    </div>
                  </div>
                )}
                
                <div ref={messagesEndRef} />
              </>
            )}
          </div>

          {/* Input area */}
          <div className="flex-shrink-0 space-y-2">
            <div className="flex gap-2">
              <Textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Type your message... (Enter to send, Shift+Enter for new line)"
                rows={3}
                disabled={isStreaming}
                className="resize-none"
              />
              <Button
                onClick={handleSend}
                disabled={!input.trim() || isStreaming}
                size="lg"
              >
                {isStreaming ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Send className="h-4 w-4" />
                )}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Approval dialog for actions */}
      <ApprovalDialog
        open={showApprovalDialog}
        onOpenChange={setShowApprovalDialog}
        messageOptions={messageOptions}
        onApproved={(optionIndex) => {
          toast.success(`Option ${["A", "B", "C"][optionIndex]} approved!`);
          setMessageOptions(null);
          setActions([]);
        }}
        onRejected={() => {
          setMessageOptions(null);
          setActions([]);
        }}
      />

      {/* Debug modal */}
      <DebugModal
        open={selectedDebugMessageId !== null}
        onOpenChange={(open) => {
          if (!open) setSelectedDebugMessageId(null);
        }}
        debugInfo={selectedDebugMessageId ? debugInfos.get(selectedDebugMessageId) || null : null}
      />
    </div>
  );
}

