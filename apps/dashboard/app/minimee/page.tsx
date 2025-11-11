"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Loader2, CheckCircle2, XCircle, AlertCircle, Cpu, Plus, UserCircle, MessageSquare } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/hooks/useAuth";
import { ChatInterface } from "@/components/minimee/ChatInterface";
import { DataSourceControls } from "@/components/minimee/DataSourceControls";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { GettingToKnowSession } from "@/components/minimee/GettingToKnowSession";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

interface ModelStatus {
  available: boolean;
  provider: string;
  model?: string;
  error?: string;
  size?: string;
  modified?: string;
}

export default function MinimeePage() {
  const { user } = useAuth();
  const userId = user?.id || 1;
  const [currentSession, setCurrentSession] = useState<any | null>(null);
  const [sessions, setSessions] = useState<any[]>([]);
  const [loadingSessions, setLoadingSessions] = useState(false);
  const [isGettingToKnowOpen, setIsGettingToKnowOpen] = useState(false);
  const [gettingToKnowSession, setGettingToKnowSession] = useState<any | null>(null);
  
  // Use session conversation_id if available, otherwise default
  const conversationId = currentSession?.conversation_id || `dashboard-minimee-${userId}`;
  const [modelStatus, setModelStatus] = useState<ModelStatus | null>(null);
  const [isCheckingModel, setIsCheckingModel] = useState(true);
  // State for included sources: null = all sources included, [] = no sources, [source1, source2] = only these sources
  const [includedSources, setIncludedSources] = useState<string[] | null>(null);

  useEffect(() => {
    const checkModelStatus = async () => {
      try {
        const status = await api.getModelStatus();
        setModelStatus(status);
      } catch (error) {
        setModelStatus({
          available: false,
          provider: "unknown",
          error: error instanceof Error ? error.message : "Unknown error",
        });
      } finally {
        setIsCheckingModel(false);
      }
    };
    
    checkModelStatus();
    // Refresh every 60 seconds (reduced frequency to save CPU)
    const interval = setInterval(checkModelStatus, 60000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    loadSessions();
  }, [userId]);

  const loadSessions = async () => {
    try {
      setLoadingSessions(true);
      const data = await api.getConversationSessions(userId);
      setSessions(data);
    } catch (err) {
      console.error("Failed to load sessions:", err);
    } finally {
      setLoadingSessions(false);
    }
  };

  const handleNewSession = async () => {
    try {
      const session = await api.createConversationSession(userId, {
        session_type: "normal",
        title: `New Conversation ${new Date().toLocaleDateString()}`,
        conversation_id: `session-${userId}-${Date.now()}`,
      });
      setCurrentSession(session);
      await loadSessions();
    } catch (err: any) {
      alert(err.message || "Failed to create new session");
    }
  };

  const handleStartGettingToKnow = async () => {
    try {
      const session = await api.startGettingToKnowSession(userId);
      setGettingToKnowSession(session);
      setIsGettingToKnowOpen(true);
    } catch (err: any) {
      alert(err.message || "Failed to start getting to know session");
    }
  };

  const handleGettingToKnowComplete = async () => {
    setIsGettingToKnowOpen(false);
    setGettingToKnowSession(null);
    await loadSessions();
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString("fr-FR", {
      day: "numeric",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  return (
    <DashboardLayout>
      <div className="flex h-[calc(100vh-8rem)] gap-4">
        {/* Sidebar with sessions */}
        <div className="w-64 border-r flex flex-col">
          <div className="p-4 border-b space-y-2">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold">Conversations</h2>
            </div>
            <div className="flex gap-2">
              <Button size="sm" variant="outline" onClick={handleNewSession} className="flex-1">
                <Plus className="h-4 w-4 mr-1" />
                New
              </Button>
              <Button size="sm" variant="outline" onClick={handleStartGettingToKnow} className="flex-1">
                <UserCircle className="h-4 w-4 mr-1" />
                Se connaître
              </Button>
            </div>
          </div>
          
          <div className="flex-1 overflow-y-auto">
            {loadingSessions ? (
              <div className="p-4 text-sm text-muted-foreground">Loading...</div>
            ) : sessions.length === 0 ? (
              <div className="p-4 text-sm text-muted-foreground text-center">
                No conversations yet
              </div>
            ) : (
              <div className="space-y-1 p-2">
                {sessions.map((session) => (
                  <button
                    key={session.id}
                    onClick={() => setCurrentSession(session)}
                    className={`w-full text-left p-3 rounded-lg transition-colors ${
                      currentSession?.id === session.id
                        ? "bg-primary text-primary-foreground"
                        : "hover:bg-muted"
                    }`}
                  >
                    <div className="font-medium truncate">
                      {session.title || `Session ${session.id}`}
                    </div>
                    <div className={`text-xs mt-1 ${
                      currentSession?.id === session.id
                        ? "text-primary-foreground/80"
                        : "text-muted-foreground"
                    }`}>
                      {formatDate(session.created_at)}
                    </div>
                    {session.session_type === "getting_to_know" && (
                      <Badge variant="default" className="text-xs mt-1">
                        Se connaître
                      </Badge>
                    )}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Main content area */}
        <div className="flex-1 flex flex-col min-w-0">
          <div className="space-y-6 flex-1 flex flex-col min-h-0">
            <div className="flex items-center justify-between flex-shrink-0">
              <div>
                <h1 className="text-3xl font-bold">Minimee</h1>
                <p className="text-muted-foreground">
                  Chat with Minimee - Your personal AI assistant
                </p>
              </div>
            </div>

            {/* Model Status Card */}
            <Card className="flex-shrink-0">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Cpu className="h-5 w-5" />
                  Model Status
                </CardTitle>
                <CardDescription>Current LLM provider and model availability</CardDescription>
              </CardHeader>
              <CardContent>
                {isCheckingModel ? (
                  <div className="flex items-center gap-2">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span className="text-sm">Checking model status...</span>
                  </div>
                ) : modelStatus ? (
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium">Provider:</span>
                      <Badge variant={modelStatus.available ? "default" : "destructive"}>
                        {modelStatus.provider}
                      </Badge>
                    </div>
                    {modelStatus.model && (
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-medium">Model:</span>
                        <span className="text-sm text-muted-foreground">{modelStatus.model}</span>
                      </div>
                    )}
                    {modelStatus.size && (
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-medium">Size:</span>
                        <span className="text-sm text-muted-foreground">{modelStatus.size}</span>
                      </div>
                    )}
                    {modelStatus.modified && (
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-medium">Modified:</span>
                        <span className="text-sm text-muted-foreground">{modelStatus.modified}</span>
                      </div>
                    )}
                    <div className="flex items-center gap-2 pt-2">
                      {modelStatus.available ? (
                        <>
                          <CheckCircle2 className="h-4 w-4 text-green-600" />
                          <span className="text-sm text-green-600">Model is loaded and ready</span>
                        </>
                      ) : (
                        <>
                          <XCircle className="h-4 w-4 text-red-600" />
                          <span className="text-sm text-red-600">
                            {modelStatus.error || "Model not available"}
                          </span>
                        </>
                      )}
                    </div>
                  </div>
                ) : (
                  <div className="flex items-center gap-2">
                    <AlertCircle className="h-4 w-4 text-yellow-600" />
                    <span className="text-sm text-yellow-600">Unable to check model status</span>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Data Source Controls */}
            <DataSourceControls
              includedSources={includedSources}
              onSourcesChange={setIncludedSources}
              userId={userId}
            />

            {/* Chat Interface */}
            <div className="flex-1 min-h-0">
              <ChatInterface 
                userId={userId} 
                conversationId={conversationId}
                includedSources={includedSources === null ? undefined : includedSources}
                sessionId={currentSession?.id}
              />
            </div>
          </div>
        </div>
      </div>

      {/* Getting to Know Dialog */}
      <Dialog open={isGettingToKnowOpen} onOpenChange={setIsGettingToKnowOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Getting to Know You</DialogTitle>
            <DialogDescription>
              Let Minimee learn more about you through a series of questions
            </DialogDescription>
          </DialogHeader>
          {gettingToKnowSession && (
            <GettingToKnowSession
              sessionId={gettingToKnowSession.id}
              userId={userId}
              onComplete={handleGettingToKnowComplete}
            />
          )}
        </DialogContent>
      </Dialog>
    </DashboardLayout>
  );
}

