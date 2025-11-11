"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Trash2, MessageSquare } from "lucide-react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { ConversationHistory } from "@/components/minimee/ConversationHistory";

export default function ConversationsPage() {
  const [sessions, setSessions] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedSession, setSelectedSession] = useState<any | null>(null);
  const userId = 1; // TODO: Get from auth context

  useEffect(() => {
    loadSessions();
  }, []);

  const loadSessions = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.getConversationSessions(userId);
      setSessions(data);
    } catch (err: any) {
      setError(err.message || "Failed to load conversations");
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteSession = async (sessionId: number) => {
    if (!confirm("Are you sure you want to delete this conversation? You can also choose to delete associated embeddings.")) {
      return;
    }
    
    const deleteEmbeddings = confirm("Do you also want to delete the embeddings associated with this conversation?");
    
    try {
      await api.deleteConversationSession(sessionId, userId, deleteEmbeddings);
      await loadSessions();
      if (selectedSession?.id === sessionId) {
        setSelectedSession(null);
      }
    } catch (err: any) {
      alert(err.message || "Failed to delete conversation");
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString("fr-FR", {
      day: "numeric",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  return (
    <DashboardLayout>
      <div className="flex h-full gap-4">
        {/* Sidebar with sessions list */}
        <div className="w-64 border-r flex flex-col">
          <div className="p-4 border-b">
            <h2 className="text-lg font-semibold">Conversations</h2>
            <p className="text-sm text-muted-foreground mt-1">
              {sessions.length} conversation{sessions.length !== 1 ? "s" : ""}
            </p>
          </div>
          
          <div className="flex-1 overflow-y-auto">
            {loading ? (
              <div className="p-4 text-sm text-muted-foreground">Loading...</div>
            ) : error ? (
              <div className="p-4 text-sm text-destructive">{error}</div>
            ) : sessions.length === 0 ? (
              <div className="p-4 text-sm text-muted-foreground text-center">
                No conversations yet
              </div>
            ) : (
              <div className="space-y-1 p-2">
                {sessions.map((session) => (
                  <button
                    key={session.id}
                    onClick={() => setSelectedSession(session)}
                    className={`w-full text-left p-3 rounded-lg transition-colors ${
                      selectedSession?.id === session.id
                        ? "bg-primary text-primary-foreground"
                        : "hover:bg-muted"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1 min-w-0">
                        <div className="font-medium truncate">
                          {session.title || `Session ${session.id}`}
                        </div>
                        <div className={`text-xs mt-1 ${
                          selectedSession?.id === session.id
                            ? "text-primary-foreground/80"
                            : "text-muted-foreground"
                        }`}>
                          {formatDate(session.created_at)}
                        </div>
                        <div className="flex gap-1 mt-1">
                          <Badge
                            variant={session.session_type === "getting_to_know" ? "default" : "outline"}
                            className="text-xs"
                          >
                            {session.session_type === "getting_to_know" ? "Se connaître" : "Normal"}
                          </Badge>
                        </div>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 w-6 p-0"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteSession(session.id);
                        }}
                      >
                        <Trash2 className="h-3 w-3" />
                      </Button>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Main content area */}
        <div className="flex-1 flex flex-col">
          {selectedSession ? (
            <ConversationHistory
              session={selectedSession}
              userId={userId}
              onBack={() => setSelectedSession(null)}
            />
          ) : (
            <div className="flex-1 flex items-center justify-center text-muted-foreground">
              <div className="text-center">
                <MessageSquare className="h-12 w-12 mx-auto mb-4 opacity-50" />
                <p>Select a conversation to view messages</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </DashboardLayout>
  );
}

