"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import { Loader2, MessageSquare, CheckCircle2, RefreshCw, QrCode, AlertCircle } from "lucide-react";
import { toast } from "sonner";

interface WhatsAppStatus {
  status: string;
  running: boolean;
  connected: boolean;
  has_qr: boolean;
}

export function WhatsAppConnect() {
  const [status, setStatus] = useState<WhatsAppStatus | null>(null);
  const [isChecking, setIsChecking] = useState(true);
  const [isRestarting, setIsRestarting] = useState(false);
  const [isStarting, setIsStarting] = useState(false);
  const [qrLogs, setQrLogs] = useState<string | null>(null);
  const [showQR, setShowQR] = useState(false);

  const checkStatus = async () => {
    try {
      const result = await api.getWhatsAppStatus();
      setStatus(result);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to check WhatsApp status");
      setStatus({
        status: "error",
        running: false,
        connected: false,
        has_qr: false,
      });
    } finally {
      setIsChecking(false);
    }
  };

  const fetchQRCode = async () => {
    try {
      const result = await api.getWhatsAppQR();
      if (result.qr_available && result.qr_data) {
        // Use QR image data directly
        setQrLogs(result.qr_data);
        setShowQR(true);
      } else {
        toast.info("QR code not available. Try restarting the bridge.");
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to get QR code");
    }
  };

  const handleRestart = async () => {
    setIsRestarting(true);
    try {
      await api.restartWhatsAppBridge();
      toast.success("WhatsApp bridge restarted. Checking status...");
      setTimeout(() => {
        checkStatus();
        setTimeout(() => fetchQRCode(), 2000);
      }, 1000);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to restart bridge");
    } finally {
      setIsRestarting(false);
    }
  };

  const handleStart = async () => {
    setIsStarting(true);
    try {
      await api.startWhatsAppBridge();
      toast.success("WhatsApp bridge started. Checking status...");
      setTimeout(() => {
        checkStatus();
        setTimeout(() => fetchQRCode(), 2000);
      }, 1000);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to start bridge");
    } finally {
      setIsStarting(false);
    }
  };

  useEffect(() => {
    checkStatus();
    const interval = setInterval(() => {
      if (!showQR && status?.has_qr) {
        fetchQRCode();
      }
      if (status?.status === "connected" || status?.status === "pending") {
        checkStatus();
      }
    }, 5000); // Check every 5 seconds

    return () => clearInterval(interval);
  }, [status?.has_qr, showQR, status?.status]);

  if (isChecking) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <MessageSquare className="h-5 w-5" />
            <span>WhatsApp Status</span>
          </div>
          <Loader2 className="h-4 w-4 animate-spin" />
        </div>
      </div>
    );
  }

  const getStatusBadge = () => {
    if (!status) return null;
    
    if (status.connected) {
      return <Badge variant="default" className="bg-green-600">Connected</Badge>;
    } else if (status.has_qr) {
      return <Badge variant="secondary" className="bg-yellow-600">QR Code Ready</Badge>;
    } else if (status.running) {
      return <Badge variant="secondary">Running</Badge>;
    } else {
      return <Badge variant="secondary">Not Running</Badge>;
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <MessageSquare className="h-5 w-5" />
          <span>WhatsApp Bridge Status</span>
        </div>
        {getStatusBadge()}
      </div>

      {status && status.connected && (
        <div className="flex items-center gap-2 p-3 bg-green-50 dark:bg-green-950 rounded-lg">
          <CheckCircle2 className="h-5 w-5 text-green-600" />
          <span className="text-sm text-green-800 dark:text-green-200">
            WhatsApp is connected and ready to receive messages
          </span>
        </div>
      )}

      {status && status.has_qr && !showQR && (
        <div className="flex items-center gap-2 p-3 bg-yellow-50 dark:bg-yellow-950 rounded-lg">
          <QrCode className="h-5 w-5 text-yellow-600" />
          <span className="text-sm text-yellow-800 dark:text-yellow-200">
            QR code available. Click below to view it.
          </span>
        </div>
      )}

      {!status?.running && (
        <div className="flex items-center gap-2 p-3 bg-red-50 dark:bg-red-950 rounded-lg">
          <AlertCircle className="h-5 w-5 text-red-600" />
          <span className="text-sm text-red-800 dark:text-red-200">
            Bridge is not running. Start it to connect WhatsApp.
          </span>
        </div>
      )}

      <div className="space-y-2">
        {!status?.running ? (
          <Button
            onClick={handleStart}
            disabled={isStarting}
            className="w-full"
            variant="default"
          >
            {isStarting ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Starting...
              </>
            ) : (
              <>
                <MessageSquare className="mr-2 h-4 w-4" />
                Start WhatsApp Bridge
              </>
            )}
          </Button>
        ) : (
          <>
            {status.has_qr && !showQR && (
              <Button
                onClick={fetchQRCode}
                className="w-full"
                variant="default"
              >
                <QrCode className="mr-2 h-4 w-4" />
                Show QR Code
              </Button>
            )}
            <Button
              onClick={handleRestart}
              disabled={isRestarting || status.connected}
              className="w-full"
              variant="outline"
            >
              {isRestarting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Restarting...
                </>
              ) : (
                <>
                  <RefreshCw className="mr-2 h-4 w-4" />
                  Restart Bridge (New QR Code)
                </>
              )}
            </Button>
            <Button
              onClick={checkStatus}
              variant="ghost"
              className="w-full"
            >
              <RefreshCw className="mr-2 h-4 w-4" />
              Refresh Status
            </Button>
          </>
        )}
      </div>

      {showQR && qrLogs && (
        <Card className="mt-4">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <QrCode className="h-5 w-5" />
              QR Code for WhatsApp Connection
            </CardTitle>
            <CardDescription>
              Scan this QR code with WhatsApp to connect
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {qrLogs && qrLogs.startsWith('data:image') ? (
                <div className="bg-white dark:bg-black p-4 rounded-lg border flex justify-center">
                  <img src={qrLogs} alt="WhatsApp QR Code" className="max-w-xs" />
                </div>
              ) : (
                <div className="bg-white dark:bg-black p-4 rounded-lg border">
                  <pre className="text-xs font-mono whitespace-pre-wrap overflow-auto max-h-96">
                    {qrLogs}
                  </pre>
                </div>
              )}
              <div className="bg-blue-50 dark:bg-blue-950 p-3 rounded-lg">
                <p className="text-sm font-semibold mb-2">Instructions:</p>
                <ol className="text-sm space-y-1 list-decimal list-inside">
                  <li>Open WhatsApp on your phone</li>
                  <li>Go to Settings → Linked Devices</li>
                  <li>Tap "Link a Device"</li>
                  <li>Point your camera at the QR code above</li>
                </ol>
              </div>
              <Button
                onClick={() => setShowQR(false)}
                variant="outline"
                className="w-full"
              >
                Hide QR Code
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      <p className="text-sm text-muted-foreground">
        Connect your WhatsApp account to receive and process messages in real-time.
        The bridge uses Baileys to maintain a persistent connection with WhatsApp Web.
      </p>
    </div>
  );
}

