"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Loader2, Send, MessageSquare, CheckCircle2, XCircle, AlertCircle, Cpu } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { ApprovalDialog, type MessageOptions } from "@/components/minimee/ApprovalDialog";
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
  const [message, setMessage] = useState("");
  const [isProcessing, setIsProcessing] = useState(false);
  const [messageOptions, setMessageOptions] = useState<MessageOptions | null>(null);
  const [showApprovalDialog, setShowApprovalDialog] = useState(false);
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
    // Refresh every 30 seconds
    const interval = setInterval(checkModelStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  const handleSendMessage = async () => {
    if (!message.trim()) {
      toast.error("Please enter a message");
      return;
    }

    setIsProcessing(true);
    try {
      const response = await api.processMessage({
        content: message,
        sender: "User",
        timestamp: new Date().toISOString(),
        conversation_id: `conv_${Date.now()}`,
        user_id: 1,
        source: "dashboard",
      });

      setMessageOptions({
        message_id: response.message_id || 0,
        conversation_id: response.conversation_id,
        options: response.options || [],
      });
      setShowApprovalDialog(true);
      setMessage("");
      toast.success("Message processed! Review the response options.");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to process message");
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold">Minimee</h1>
            <p className="text-muted-foreground">
              Send a message and review AI-generated response options
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

      <Card>
        <CardHeader>
          <CardTitle>Send Message</CardTitle>
          <CardDescription>
            Type a message to generate multiple AI response options (A/B/C)
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="message">Your Message</Label>
            <Textarea
              id="message"
              placeholder="Type your message here..."
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              rows={4}
              disabled={isProcessing}
            />
          </div>
          <Button
            onClick={handleSendMessage}
            disabled={isProcessing || !message.trim()}
            className="w-full"
          >
            {isProcessing ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Processing...
              </>
            ) : (
              <>
                <Send className="mr-2 h-4 w-4" />
                Process Message
              </>
            )}
          </Button>
        </CardContent>
      </Card>

      {messageOptions && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <MessageSquare className="h-5 w-5" />
              Response Options
            </CardTitle>
            <CardDescription>
              Click the button below to review and approve response options
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button onClick={() => setShowApprovalDialog(true)} variant="outline" className="w-full">
              Review Options ({messageOptions.options.length})
            </Button>
          </CardContent>
        </Card>
      )}

      <ApprovalDialog
        open={showApprovalDialog}
        onOpenChange={setShowApprovalDialog}
        messageOptions={messageOptions}
        onApproved={(optionIndex) => {
          toast.success(`Option ${["A", "B", "C"][optionIndex]} approved and sent!`);
          setMessageOptions(null);
        }}
        onRejected={() => {
          setMessageOptions(null);
        }}
      />
      </div>
    </DashboardLayout>
  );
}

