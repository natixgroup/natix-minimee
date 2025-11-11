"use client";

import { useState, useEffect, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { Loader2, Mail, CheckCircle2, AlertCircle, StopCircle, LogOut } from "lucide-react";
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
  const [activeJob, setActiveJob] = useState<{
    id: number;
    status: string;
    progress: any;
    created_at: string;
  } | null>(null);
  const [isCancelling, setIsCancelling] = useState(false);
  const [isDisconnecting, setIsDisconnecting] = useState(false);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  // Check for active Gmail import job
  const checkActiveJob = async () => {
    try {
      const savedJobId = localStorage.getItem("activeIngestionJobId");
      if (savedJobId) {
        const jobId = parseInt(savedJobId);
        if (!isNaN(jobId)) {
          const job = await api.getIngestionJob(jobId);
          // Only show if it's a Gmail job and still running
          if (job.progress?.source === "gmail" && job.status === "running") {
            setActiveJob({
              id: job.id,
              status: job.status,
              progress: job.progress,
              created_at: job.created_at,
            });
            return;
          }
        }
      }
      setActiveJob(null);
    } catch (error) {
      // Job might not exist anymore
      setActiveJob(null);
      localStorage.removeItem("activeIngestionJobId");
    }
  };

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
    checkActiveJob();

    // Poll for active job updates every 2 seconds
    intervalRef.current = setInterval(checkActiveJob, 2000);

    // Listen for job completion
    const handleJobComplete = () => {
      setActiveJob(null);
    };

    window.addEventListener("ingestionJobComplete", handleJobComplete);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
      window.removeEventListener("ingestionJobComplete", handleJobComplete);
    };
  }, []);

  const handleConnect = async () => {
    if (!hasCredentials) {
      toast.error("Gmail integration is not configured. Please contact your administrator.");
      return;
    }

    setIsConnecting(true);
    try {
      // Always force consent to ensure we get a refresh_token
      const result = await api.startGmailOAuth(1, true); // TODO: Get userId from auth, force_consent=true
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
      
      // Update active job state
      checkActiveJob();
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "Failed to start Gmail import";
      toast.error(errorMessage);
      console.error("Gmail fetch error:", error);
    }
  };

  const handleCancel = async () => {
    if (!activeJob || isCancelling) return;

    setIsCancelling(true);
    try {
      await api.cancelIngestionJob(activeJob.id);
      toast.success("Import cancelled");
      setActiveJob(null);
      localStorage.removeItem("activeIngestionJobId");
      window.dispatchEvent(new CustomEvent("ingestionJobComplete"));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to cancel import");
    } finally {
      setIsCancelling(false);
    }
  };

  const handleDisconnect = async () => {
    if (isDisconnecting) return;

    setIsDisconnecting(true);
    try {
      await api.disconnectGmail(1); // TODO: Get userId from auth
      toast.success("Gmail disconnected");
      setIsConnected(false);
      setActiveJob(null);
      localStorage.removeItem("activeIngestionJobId");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to disconnect Gmail");
    } finally {
      setIsDisconnecting(false);
    }
  };

  const formatElapsedTime = (createdAt: string) => {
    const now = new Date();
    const created = new Date(createdAt);
    const diff = Math.floor((now.getTime() - created.getTime()) / 1000); // seconds

    if (diff < 60) {
      return `${diff}s`;
    } else if (diff < 3600) {
      const minutes = Math.floor(diff / 60);
      return `${minutes}m`;
    } else {
      const hours = Math.floor(diff / 3600);
      const minutes = Math.floor((diff % 3600) / 60);
      return `${hours}h ${minutes}m`;
    }
  };

  const getStepLabel = (step?: string) => {
    const labels: Record<string, string> = {
      fetching: "Fetching Gmail",
      indexing: "Indexing",
      complete: "Complete",
      failed: "Failed",
      cancelled: "Cancelled",
    };
    return labels[step || ""] || step || "In progress";
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
        <div className="flex items-center gap-2">
          <Button
            onClick={handleConnect}
            disabled={isConnecting || isConnected || hasCredentials === false}
            className="flex-1 bg-white hover:bg-gray-50 text-gray-900 border border-gray-300 shadow-sm"
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
                Sign in with Google
              </>
            )}
          </Button>
          {isConnected && (
            <Button
              onClick={handleDisconnect}
              variant="ghost"
              size="sm"
              disabled={isDisconnecting}
              className="h-10 w-10 p-0 text-red-500 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-950"
              title="Disconnect Gmail"
            >
              {isDisconnecting ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <LogOut className="h-4 w-4" />
              )}
            </Button>
          )}
        </div>

        {isConnected && (
          <>
            {activeJob ? (
              <div className="space-y-2">
                <Button
                  onClick={handleCancel}
                  variant="destructive"
                  className="w-full"
                  disabled={isCancelling}
                >
                  {isCancelling ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Cancelling...
                    </>
                  ) : (
                    <>
                      <StopCircle className="mr-2 h-4 w-4" />
                      Stop import
                    </>
                  )}
                </Button>
                <div className="text-xs text-muted-foreground space-y-1">
                  <div className="flex items-center justify-between">
                    <span>Status:</span>
                    <span className="font-medium">{getStepLabel(activeJob.progress?.step)}</span>
                  </div>
                  {activeJob.progress?.current !== undefined && activeJob.progress?.total !== undefined && (
                    <div className="flex items-center justify-between">
                      <span>Progress:</span>
                      <span className="font-medium">
                        {activeJob.progress.current}/{activeJob.progress.total}
                      </span>
                    </div>
                  )}
                  <div className="flex items-center justify-between">
                    <span>Duration:</span>
                    <span className="font-medium">{formatElapsedTime(activeJob.created_at)}</span>
                  </div>
                </div>
              </div>
            ) : (
              <Button
                onClick={handleFetch}
                variant="outline"
                className="w-full"
              >
                <CheckCircle2 className="mr-2 h-4 w-4" />
                Import recent emails (last 30 days)
              </Button>
            )}
          </>
        )}
      </div>

      <p className="text-sm text-muted-foreground">
        Connect your Gmail account to import your conversations. Only emails you have replied to will be imported.
      </p>
    </div>
  );
}

