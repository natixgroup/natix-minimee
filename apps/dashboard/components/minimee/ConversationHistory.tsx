"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ArrowLeft, Loader2 } from "lucide-react";

interface ConversationHistoryProps {
  session: any;
  userId: number;
  onBack: () => void;
}

export function ConversationHistory({ session, userId, onBack }: ConversationHistoryProps) {
  const [messages, setMessages] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadMessages();
  }, [session.id]);

  const loadMessages = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.getSessionMessages(session.id, userId);
      setMessages(data);
    } catch (err: any) {
      setError(err.message || "Failed to load messages");
    } finally {
      setLoading(false);
    }
  };

  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString("fr-FR", {
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  return (
    <div className="flex flex-col h-full">
      <div className="border-b p-4 flex items-center gap-4">
        <Button variant="ghost" size="sm" onClick={onBack}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back
        </Button>
        <div>
          <h2 className="font-semibold">{session.title || `Session ${session.id}`}</h2>
          <p className="text-sm text-muted-foreground">
            {session.session_type === "getting_to_know" ? "Getting to Know Session" : "Normal Conversation"}
          </p>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {loading ? (
          <div className="flex items-center justify-center h-full">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : error ? (
          <Card className="border-destructive">
            <CardContent className="pt-6">
              <p className="text-destructive">{error}</p>
            </CardContent>
          </Card>
        ) : messages.length === 0 ? (
          <div className="text-center text-muted-foreground py-8">
            No messages in this conversation
          </div>
        ) : (
          messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex ${
                msg.sender === "User" ? "justify-end" : "justify-start"
              }`}
            >
              <div
                className={`max-w-[80%] rounded-lg px-4 py-2 ${
                  msg.sender === "User"
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted"
                }`}
              >
                {msg.source && (
                  <Badge variant="secondary" className="mb-1 text-xs">
                    {msg.source}
                  </Badge>
                )}
                <div className="whitespace-pre-wrap">{msg.content}</div>
                <div className="text-xs opacity-70 mt-1">
                  {formatTime(msg.timestamp)}
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}


