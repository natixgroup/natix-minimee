"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { Loader2, Mail, CheckCircle2 } from "lucide-react";
import { toast } from "sonner";

export function GmailConnect() {
  const [isConnecting, setIsConnecting] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [isChecking, setIsChecking] = useState(true);

  useEffect(() => {
    // Check Gmail connection status on mount
    const checkStatus = async () => {
      try {
        const status = await api.checkGmailStatus(1); // TODO: Get userId from auth
        setIsConnected(status.connected || status.has_token);
      } catch (error) {
        setIsConnected(false);
      } finally {
        setIsChecking(false);
      }
    };

    checkStatus();
  }, []);

  const handleConnect = async () => {
    setIsConnecting(true);
    try {
      const result = await api.startGmailOAuth(1); // TODO: Get userId from auth
      window.location.href = result.authorization_url;
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to connect Gmail");
      setIsConnecting(false);
    }
  };

  const handleFetch = async () => {
    try {
      await api.fetchGmailThreads(30, true, 1);
      toast.success("Gmail threads fetched and indexed successfully");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to fetch threads");
    }
  };

  if (isChecking) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Mail className="h-5 w-5" />
            <span>Gmail Status</span>
          </div>
          <Loader2 className="h-4 w-4 animate-spin" />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Mail className="h-5 w-5" />
          <span>Gmail Status</span>
        </div>
        <Badge variant={isConnected ? "default" : "secondary"}>
          {isConnected ? "Connected" : "Not Connected"}
        </Badge>
      </div>

      <div className="space-y-2">
        <Button
          onClick={handleConnect}
          disabled={isConnecting || isConnected}
          className="w-full"
        >
          {isConnecting ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Connecting...
            </>
          ) : (
            <>
              <Mail className="mr-2 h-4 w-4" />
              Connect Gmail
            </>
          )}
        </Button>

        {isConnected && (
          <Button
            onClick={handleFetch}
            variant="outline"
            className="w-full"
          >
            <CheckCircle2 className="mr-2 h-4 w-4" />
            Fetch Recent Emails (30 days)
          </Button>
        )}
      </div>

      <p className="text-sm text-muted-foreground">
        Connect your Gmail account to import conversations. Only emails you
        have replied to will be imported.
      </p>
    </div>
  );
}

