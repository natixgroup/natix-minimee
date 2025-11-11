"use client";

import { useEffect, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Loader2, CheckCircle2, XCircle } from "lucide-react";
import { api } from "@/lib/api";

export default function GmailCallbackPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [message, setMessage] = useState<string>("Processing Gmail OAuth...");

  useEffect(() => {
    const code = searchParams.get("code");
    const state = searchParams.get("state");
    const error = searchParams.get("error");

    if (error) {
      setStatus("error");
      setMessage("OAuth authorization was denied or failed.");
      setTimeout(() => router.push("/settings?tab=integrations"), 3000);
      return;
    }

    if (!code || !state) {
      setStatus("error");
      setMessage("Missing OAuth code or state parameter.");
      setTimeout(() => router.push("/settings?tab=integrations"), 3000);
      return;
    }

    // Call backend callback endpoint
    const handleCallback = async () => {
      try {
        const result = await api.handleGmailCallback(code, state);
        setStatus("success");
        setMessage("Gmail successfully connected!");
        setTimeout(() => router.push("/settings?tab=integrations"), 2000);
      } catch (err) {
        setStatus("error");
        setMessage(
          err instanceof Error ? err.message : "Failed to complete Gmail OAuth"
        );
        setTimeout(() => router.push("/settings?tab=integrations"), 3000);
      }
    };

    handleCallback();
  }, [searchParams, router]);

  return (
    <div className="flex items-center justify-center min-h-screen p-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Gmail OAuth</CardTitle>
          <CardDescription>Completing Gmail connection...</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col items-center justify-center space-y-4 py-8">
          {status === "loading" && (
            <>
              <Loader2 className="h-8 w-8 animate-spin text-primary" />
              <p className="text-sm text-muted-foreground">{message}</p>
            </>
          )}
          {status === "success" && (
            <>
              <CheckCircle2 className="h-8 w-8 text-green-500" />
              <p className="text-sm text-green-600">{message}</p>
              <p className="text-xs text-muted-foreground">
                Redirecting to settings...
              </p>
            </>
          )}
          {status === "error" && (
            <>
              <XCircle className="h-8 w-8 text-destructive" />
              <p className="text-sm text-destructive">{message}</p>
              <p className="text-xs text-muted-foreground">
                Redirecting to settings...
              </p>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

