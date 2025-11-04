"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import { Loader2, MessageSquare, CheckCircle2, RefreshCw, QrCode, AlertCircle, Phone, Building2 } from "lucide-react";
import { toast } from "sonner";

interface WhatsAppStatus {
  status: string;
  running: boolean;
  connected: boolean;
  has_qr: boolean;
}

interface WhatsAppInfo {
  phone: string;
  account_type: string;
  is_business: boolean;
}

export function WhatsAppUserConnect() {
  const [status, setStatus] = useState<WhatsAppStatus | null>(null);
  const [isChecking, setIsChecking] = useState(true);
  const [isRestarting, setIsRestarting] = useState(false);
  const [qrLogs, setQrLogs] = useState<string | null>(null);
  const [accountInfo, setAccountInfo] = useState<WhatsAppInfo | null>(null);

  const checkStatus = async () => {
    try {
      const result = await api.getUserWhatsAppStatus();
      setStatus(result);
      
      // Fetch account info if connected
      if (result.connected) {
        try {
          const info = await api.getUserWhatsAppInfo();
          setAccountInfo(info);
        } catch (error) {
          // Silently fail - account info is optional
          console.warn('Could not fetch account info:', error);
        }
      } else {
        setAccountInfo(null);
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to check WhatsApp status");
      setStatus({
        status: "error",
        running: false,
        connected: false,
        has_qr: false,
      });
      setAccountInfo(null);
    } finally {
      setIsChecking(false);
    }
  };

  const fetchQRCode = async () => {
    try {
      const result = await api.getUserWhatsAppQR();
      if (result.qr_available && result.qr_data) {
        setQrLogs(result.qr_data);
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
      await api.restartUserWhatsAppBridge();
      toast.success("User WhatsApp bridge restarted. Checking status...");
      // Reset QR logs to force refresh
      setQrLogs(null);
      // Check status multiple times to catch QR code generation
      setTimeout(() => checkStatus(), 1000);
      setTimeout(() => {
        checkStatus().then(() => {
          // Check again after status update
          setTimeout(() => {
            checkStatus().then(() => {
              // Try to fetch QR if available
              setTimeout(() => {
                fetchQRCode();
              }, 500);
            });
          }, 2000);
        });
      }, 3000);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to restart bridge");
    } finally {
      setIsRestarting(false);
    }
  };

  useEffect(() => {
    checkStatus();
    const interval = setInterval(() => {
      if (status?.has_qr && !qrLogs) {
        fetchQRCode();
      }
      if (status?.status === "connected" || status?.status === "pending") {
        checkStatus();
      }
    }, 5000);

    return () => clearInterval(interval);
  }, [status?.has_qr, qrLogs, status?.status]);

  // Auto-fetch QR code when status indicates it's available
  useEffect(() => {
    if (status?.has_qr && !qrLogs) {
      // Wait a bit more for QR code to be fully generated
      setTimeout(() => {
        fetchQRCode();
      }, 500);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status?.has_qr]);

  if (isChecking) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <MessageSquare className="h-5 w-5" />
            <span>User WhatsApp Status</span>
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
          <span>User WhatsApp Account</span>
        </div>
        {getStatusBadge()}
      </div>

      <div className="text-sm text-muted-foreground">
        Connect your personal WhatsApp account to receive messages in real-time, import conversations, and send approved responses.
      </div>

      {status?.connected && accountInfo && (
        <div className="flex items-center gap-4 p-3 bg-muted rounded-lg">
          <div className="flex items-center gap-2">
            <Phone className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm font-medium">{accountInfo.phone}</span>
          </div>
          <div className="flex items-center gap-2">
            {accountInfo.is_business ? (
              <>
                <Building2 className="h-4 w-4 text-blue-600" />
                <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200">
                  WhatsApp Business
                </Badge>
              </>
            ) : (
              <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200">
                WhatsApp Standard
              </Badge>
            )}
          </div>
        </div>
      )}

      {status?.connected ? (
        <div className="flex items-center gap-2 text-green-600">
          <CheckCircle2 className="h-5 w-5" />
          <span>Connected and ready</span>
        </div>
      ) : status?.has_qr && qrLogs ? (
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <QrCode className="h-5 w-5 text-yellow-600" />
            <span className="font-medium">Scan QR Code to Connect</span>
          </div>
          
          <div className="bg-white dark:bg-black p-4 rounded-lg border-2 border-dashed border-yellow-500/50">
            <img 
              src={qrLogs} 
              alt="WhatsApp QR Code" 
              className="w-64 h-64 mx-auto"
            />
          </div>

          <div className="bg-blue-50 dark:bg-blue-950 p-4 rounded-lg space-y-3">
            <p className="text-sm font-semibold text-blue-900 dark:text-blue-100">
              Comment connecter votre compte WhatsApp :
            </p>
            <ol className="text-sm space-y-2 text-blue-800 dark:text-blue-200">
              <li className="flex items-start gap-2">
                <span className="font-bold text-blue-600 dark:text-blue-400">1.</span>
                <span>Ouvrez WhatsApp sur votre téléphone</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="font-bold text-blue-600 dark:text-blue-400">2.</span>
                <span>Allez dans <strong>Paramètres</strong> → <strong>Appareils liés</strong></span>
              </li>
              <li className="flex items-start gap-2">
                <span className="font-bold text-blue-600 dark:text-blue-400">3.</span>
                <span>Appuyez sur <strong>"Lier un appareil"</strong></span>
              </li>
              <li className="flex items-start gap-2">
                <span className="font-bold text-blue-600 dark:text-blue-400">4.</span>
                <span>Scannez le QR code ci-dessus avec votre téléphone</span>
              </li>
            </ol>
          </div>
        </div>
      ) : status?.has_qr && !qrLogs ? (
        <div className="flex items-center gap-2 text-yellow-600">
          <Loader2 className="h-4 w-4 animate-spin" />
          <span>Chargement du QR code...</span>
        </div>
      ) : (
        <div className="flex items-center gap-2 text-muted-foreground">
          <AlertCircle className="h-5 w-5" />
          <span>Not connected - Click "Restart" to generate QR code</span>
        </div>
      )}

      <div className="flex gap-2">
        <Button
          onClick={handleRestart}
          disabled={isRestarting}
          variant="outline"
          size="sm"
        >
          {isRestarting ? (
            <>
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              Restarting...
            </>
          ) : (
            <>
              <RefreshCw className="h-4 w-4 mr-2" />
              Restart
            </>
          )}
        </Button>
        <Button onClick={checkStatus} variant="outline" size="sm">
          <RefreshCw className="h-4 w-4 mr-2" />
          Refresh Status
        </Button>
      </div>
    </div>
  );
}

