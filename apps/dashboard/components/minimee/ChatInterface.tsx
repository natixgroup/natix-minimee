"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Send, Loader2, MessageSquare, Info, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { useChatStream } from "@/lib/hooks/useChatStream";
import { useConversationHistory, type ChatMessage } from "@/lib/hooks/useConversationHistory";
import { useWhatsAppMessages } from "@/lib/hooks/useWhatsAppMessages";
import { ApprovalDialog, type MessageOptions } from "./ApprovalDialog";
import { DebugModal } from "./DebugModal";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { api } from "@/lib/api";

interface ChatInterfaceProps {
  userId: number;
  conversationId: string;
  includedSources?: string[];
  sessionId?: number | null;
}

export function ChatInterface({ userId, conversationId, includedSources, sessionId }: ChatInterfaceProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [showWhatsApp, setShowWhatsApp] = useState(true); // Default to true to show WhatsApp messages
  const [streamingMessage, setStreamingMessage] = useState("");
  const [actions, setActions] = useState<any[]>([]);
  const [messageOptions, setMessageOptions] = useState<MessageOptions | null>(null);
  const [showApprovalDialog, setShowApprovalDialog] = useState(false);
  const [debugInfos, setDebugInfos] = useState<Map<number, any>>(new Map());
  const [selectedDebugMessageId, setSelectedDebugMessageId] = useState<number | null>(null);
  const [showPurgeConfirm, setShowPurgeConfirm] = useState(false);
  const [isPurging, setIsPurging] = useState(false);
  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const { sendMessage, isStreaming } = useChatStream();
  
  const { data: historyData, isLoading: isLoadingHistory, refetch: refetchHistory } = useConversationHistory(
    conversationId,
    userId,
    true
  );
  
  // Handler for purging conversation
  const handlePurge = async () => {
    setIsPurging(true);
    try {
      const result = await api.deleteConversationMessages(conversationId, userId);
      toast.success(result.message || `${result.deleted} message(s) supprimé(s)`);
      setShowPurgeConfirm(false);
      setMessages([]);
      setStreamingMessage("");
      // Refetch history to ensure UI is updated
      await refetchHistory();
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Erreur lors de la suppression"
      );
    } finally {
      setIsPurging(false);
    }
  };

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

    // Determine active sources: undefined/null = all sources, [] = no sources, [source1, ...] = only these sources
    const activeSources = includedSources === undefined ? null : includedSources;

    const userMessage: ChatMessage = {
      id: Date.now(), // Temporary ID
      content: input.trim(),
      sender: "User",
      timestamp: new Date().toISOString(),
      source: "dashboard",
      conversation_id: conversationId,
      active_sources: activeSources,
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
        // Determine active sources from debugInfo or includedSources
        // debugInfo.included_sources can be null (all sources), [] (no sources), or [source1, ...] (only these sources)
        const activeSources = debugInfo?.included_sources !== undefined 
          ? (debugInfo.included_sources === null ? null : debugInfo.included_sources)
          : (includedSources === undefined ? null : includedSources);

        const minimeeMessage: ChatMessage = {
          id: Date.now() + 1, // Temporary ID
          content: response,
          sender: "Minimee",
          timestamp: new Date().toISOString(),
          source: "minimee",
          conversation_id: conversationId,
          active_sources: activeSources,
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
      },
      includedSources
    );
  }, [input, userId, conversationId, isStreaming, sendMessage, includedSources]);

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
            <div className="flex items-center gap-4">
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
              <Button
                variant="destructive"
                size="sm"
                onClick={() => setShowPurgeConfirm(true)}
                disabled={isPurging || messages.length === 0}
                className="flex items-center gap-2"
              >
                <Trash2 className="h-4 w-4" />
                Purger
              </Button>
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
                      {/* Show active data sources */}
                      {msg.active_sources !== undefined && (
                        <div className="flex items-center gap-1 mb-1 flex-wrap">
                          <span className="text-xs text-muted-foreground">Sources RAG:</span>
                          {msg.active_sources === null ? (
                            <Badge variant="outline" className="text-xs">
                              Toutes
                            </Badge>
                          ) : msg.active_sources.length === 0 ? (
                            <Badge variant="outline" className="text-xs text-destructive">
                              Aucune
                            </Badge>
                          ) : (
                            msg.active_sources.map((source) => (
                              <Badge key={source} variant="outline" className="text-xs capitalize">
                                {source}
                              </Badge>
                            ))
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
                      {/* Show active data sources for streaming message */}
                      {(() => {
                        const activeSources = includedSources === undefined ? null : includedSources;
                        return (
                          <div className="flex items-center gap-1 mb-1 flex-wrap">
                            <span className="text-xs text-muted-foreground">Sources RAG:</span>
                            {activeSources === null ? (
                              <Badge variant="outline" className="text-xs">
                                Toutes
                              </Badge>
                            ) : activeSources.length === 0 ? (
                              <Badge variant="outline" className="text-xs text-destructive">
                                Aucune
                              </Badge>
                            ) : (
                              activeSources.map((source) => (
                                <Badge key={source} variant="outline" className="text-xs capitalize">
                                  {source}
                                </Badge>
                              ))
                            )}
                          </div>
                        );
                      })()}
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

      {/* Purge confirmation dialog */}
      <Dialog open={showPurgeConfirm} onOpenChange={setShowPurgeConfirm}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Confirmer la suppression</DialogTitle>
            <DialogDescription>
              Vous êtes sur le point de supprimer <strong>{messages.length} message(s)</strong> de cette conversation.
              <br />
              <br />
              Cette action est <strong className="text-destructive">irréversible</strong> et supprimera également les embeddings associés.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="flex gap-2 mt-4">
            <Button
              variant="outline"
              onClick={() => setShowPurgeConfirm(false)}
              disabled={isPurging}
            >
              Annuler
            </Button>
            <Button
              variant="destructive"
              onClick={handlePurge}
              disabled={isPurging}
              className="flex items-center gap-2"
            >
              {isPurging ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Suppression...
                </>
              ) : (
                <>
                  <Trash2 className="h-4 w-4" />
                  Supprimer {messages.length} message(s)
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

