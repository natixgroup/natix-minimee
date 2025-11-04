"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Loader2, CheckCircle2, XCircle, AlertCircle, Cpu } from "lucide-react";
import { api } from "@/lib/api";
import { ChatInterface } from "@/components/minimee/ChatInterface";
import { DashboardLayout } from "@/components/layout/DashboardLayout";

interface ModelStatus {
  available: boolean;
  provider: string;
  model?: string;
  error?: string;
  size?: string;
  modified?: string;
}

export default function MinimeePage() {
  const userId = 1; // TODO: Get from auth
  // Use fixed conversation_id for dashboard chat with Minimee (syncs with WhatsApp Minimee)
  const conversationId = `dashboard-minimee-${userId}`;
  const [modelStatus, setModelStatus] = useState<ModelStatus | null>(null);
  const [isCheckingModel, setIsCheckingModel] = useState(true);

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

  return (
    <DashboardLayout>
      <div className="space-y-6 h-[calc(100vh-8rem)]">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold">Minimee</h1>
            <p className="text-muted-foreground">
              Chat with Minimee - Your personal AI assistant
            </p>
          </div>
        </div>

        {/* Model Status Card */}
        <Card>
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

        {/* Chat Interface */}
        <div className="flex-1 min-h-0">
          <ChatInterface userId={userId} conversationId={conversationId} />
        </div>
      </div>
    </DashboardLayout>
  );
}

