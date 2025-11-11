"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { Loader2, Mail, CheckCircle2, AlertCircle } from "lucide-react";
import { toast } from "sonner";
import {
  Alert,
  AlertDescription,
} from "@/components/ui/alert";

export function GmailConnect() {
  const [isConnecting, setIsConnecting] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [isChecking, setIsChecking] = useState(true);
  const [hasCredentials, setHasCredentials] = useState<boolean | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Check Gmail connection status on mount
    const checkStatus = async () => {
      try {
        const status = await api.checkGmailStatus(1); // TODO: Get userId from auth
        setIsConnected(status.connected || status.has_token || false);
        setHasCredentials(status.has_client_credentials ?? true); // Default to true if not returned
        if (status.error && !status.has_client_credentials) {
          setError(status.error);
        } else {
          setError(null);
        }
      } catch (error) {
        setIsConnected(false);
        setHasCredentials(false);
        setError("Failed to check Gmail status");
      } finally {
        setIsChecking(false);
      }
    };

    checkStatus();
  }, []);

  const handleConnect = async () => {
    if (!hasCredentials) {
      toast.error("Gmail integration is not configured. Please contact your administrator.");
      return;
    }

    setIsConnecting(true);
    try {
      const result = await api.startGmailOAuth(1); // TODO: Get userId from auth
      window.location.href = result.authorization_url;
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "Failed to connect Gmail";
      toast.error(errorMessage);
      if (errorMessage.includes("credentials not configured")) {
        setHasCredentials(false);
        setError(errorMessage);
      }
      setIsConnecting(false);
    }
  };

  const handleFetch = async () => {
    if (!isConnected) {
      toast.error("Please connect your Gmail account first");
      return;
    }

    try {
      const result = await api.fetchGmailThreadsAsync(30, true, 1);
      const jobId = result.job_id;
      
      // Store in localStorage for global component
      localStorage.setItem("activeIngestionJobId", jobId.toString());
      
      // Dispatch custom event for same-tab communication
      window.dispatchEvent(new CustomEvent("ingestionJobStart", { detail: { jobId } }));
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "Failed to start Gmail import";
      toast.error(errorMessage);
      console.error("Gmail fetch error:", error);
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
          <span>Gmail Connection</span>
        </div>
        <Badge variant={isConnected ? "default" : "secondary"} className={isConnected ? "bg-green-600" : ""}>
          {isConnected ? "Connected" : "Not Connected"}
        </Badge>
      </div>

      {hasCredentials === false && (
        <Alert className="bg-yellow-50 dark:bg-yellow-950 border-yellow-200 dark:border-yellow-800">
          <AlertCircle className="h-4 w-4 text-yellow-600" />
          <AlertDescription className="text-yellow-800 dark:text-yellow-200">
            Gmail integration is not configured. Please contact your administrator to enable Gmail integration.
          </AlertDescription>
        </Alert>
      )}

      {isConnected && (
        <Alert className="bg-green-50 dark:bg-green-950 border-green-200 dark:border-green-800">
          <CheckCircle2 className="h-4 w-4 text-green-600" />
          <AlertDescription className="text-green-800 dark:text-green-200">
            Your Gmail account is connected. You can import emails and conversations.
          </AlertDescription>
        </Alert>
      )}

      <div className="space-y-2">
        <Button
          onClick={handleConnect}
          disabled={isConnecting || isConnected || hasCredentials === false}
          className="w-full bg-white hover:bg-gray-50 text-gray-900 border border-gray-300 shadow-sm"
          size="lg"
        >
          {isConnecting ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Connecting...
            </>
          ) : (
            <>
              <svg className="mr-2 h-4 w-4" viewBox="0 0 24 24">
                <path
                  fill="currentColor"
                  d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                />
                <path
                  fill="currentColor"
                  d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                />
                <path
                  fill="currentColor"
                  d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                />
                <path
                  fill="currentColor"
                  d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                />
              </svg>
              Se connecter avec Google
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
            Importer les emails récents (30 derniers jours)
          </Button>
        )}
      </div>

      <p className="text-sm text-muted-foreground">
        Connectez votre compte Gmail pour importer vos conversations. Seuls les emails auxquels vous avez répondu seront importés.
      </p>
    </div>
  );
}

