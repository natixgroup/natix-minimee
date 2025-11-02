"use client";

import { useState, useEffect } from "react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Loader2, CheckCircle2, XCircle, TestTube } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";

interface TestResult {
  method: string;
  status: "success" | "error" | "pending";
  message?: string;
  formatUsed?: string;
  timestamp?: Date;
  error?: string;
}

const TEST_METHODS = [
  { id: "buttons", name: "Buttons Classiques", description: "Format actuel avec buttons array" },
  { id: "interactive", name: "Interactive Message", description: "Format interactive de Baileys" },
  { id: "template", name: "Template Message", description: "Format template si supporté" },
  { id: "poll", name: "Sondage (Poll)", description: "Format sondage WhatsApp" },
];

export default function TestsPage() {
  const [whatsappStatus, setWhatsappStatus] = useState<{
    connected: boolean;
    status: string;
  } | null>(null);
  const [userPhone, setUserPhone] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [testResults, setTestResults] = useState<TestResult[]>([]);
  const [testingMethod, setTestingMethod] = useState<string | null>(null);

  useEffect(() => {
    loadStatus();
  }, []);

  const loadStatus = async () => {
    try {
      const status = await api.getWhatsAppStatus();
      setWhatsappStatus({
        connected: status.connected,
        status: status.status,
      });
      
      // Récupérer le numéro de l'utilisateur connecté
      if (status.connected) {
        const phone = await api.getConnectedWhatsAppUser();
        setUserPhone(phone);
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to load WhatsApp status");
    } finally {
      setIsLoading(false);
    }
  };

  const handleTest = async (methodId: string) => {
    if (!whatsappStatus?.connected) {
      toast.error("WhatsApp n'est pas connecté");
      return;
    }

    if (!userPhone) {
      toast.error("Numéro WhatsApp de l'utilisateur non disponible");
      return;
    }

    setTestingMethod(methodId);
    const testResult: TestResult = {
      method: methodId,
      status: "pending",
      timestamp: new Date(),
    };

    setTestResults((prev) => [...prev, testResult]);

    try {
      const result = await api.testWhatsAppMessage(methodId, userPhone);
      
      setTestResults((prev) =>
        prev.map((r) =>
          r.method === methodId && r.timestamp === testResult.timestamp
            ? {
                ...r,
                status: "success" as const,
                message: result.message || "Message envoyé avec succès",
                formatUsed: result.formatUsed,
              }
            : r
        )
      );
      
      toast.success(`Test ${methodId} réussi !`);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "Erreur inconnue";
      
      setTestResults((prev) =>
        prev.map((r) =>
          r.method === methodId && r.timestamp === testResult.timestamp
            ? {
                ...r,
                status: "error" as const,
                error: errorMessage,
              }
            : r
        )
      );
      
      toast.error(`Test ${methodId} échoué: ${errorMessage}`);
    } finally {
      setTestingMethod(null);
    }
  };

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-2">
            <TestTube className="h-8 w-8" />
            Tests WhatsApp Multi-choix
          </h1>
          <p className="text-muted-foreground">
            Testez différents formats de messages multi-choix depuis Minimee vers votre WhatsApp
          </p>
        </div>

        {/* Status Card */}
        <Card>
          <CardHeader>
            <CardTitle>Statut WhatsApp</CardTitle>
            <CardDescription>État de la connexion WhatsApp</CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="flex items-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin" />
                <span>Chargement...</span>
              </div>
            ) : whatsappStatus ? (
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">Statut: {whatsappStatus.status}</p>
                  {userPhone && (
                    <p className="text-sm text-muted-foreground">Numéro: {userPhone}</p>
                  )}
                </div>
                <Badge variant={whatsappStatus.connected ? "default" : "destructive"}>
                  {whatsappStatus.connected ? "Connecté" : "Déconnecté"}
                </Badge>
              </div>
            ) : (
              <p className="text-muted-foreground">Impossible de charger le statut</p>
            )}
          </CardContent>
        </Card>

        {/* Test Methods */}
        <Card>
          <CardHeader>
            <CardTitle>Méthodes de Test</CardTitle>
            <CardDescription>
              Testez chaque format de message multi-choix. Les messages seront envoyés à votre numéro WhatsApp.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {TEST_METHODS.map((method) => (
              <div
                key={method.id}
                className="flex items-center justify-between p-4 border rounded-lg"
              >
                <div className="flex-1">
                  <h3 className="font-semibold">{method.name}</h3>
                  <p className="text-sm text-muted-foreground">{method.description}</p>
                </div>
                <Button
                  onClick={() => handleTest(method.id)}
                  disabled={!whatsappStatus?.connected || testingMethod === method.id}
                  variant="outline"
                >
                  {testingMethod === method.id ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      Test en cours...
                    </>
                  ) : (
                    "Tester"
                  )}
                </Button>
              </div>
            ))}
          </CardContent>
        </Card>

        {/* Test Results */}
        {testResults.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>Résultats des Tests</CardTitle>
              <CardDescription>Historique des tests effectués</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {testResults
                  .slice()
                  .reverse()
                  .map((result, index) => (
                    <div
                      key={index}
                      className="flex items-start justify-between p-3 border rounded-lg"
                    >
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <Badge variant="outline">{result.method}</Badge>
                          {result.status === "success" && (
                            <CheckCircle2 className="h-4 w-4 text-green-600" />
                          )}
                          {result.status === "error" && (
                            <XCircle className="h-4 w-4 text-red-600" />
                          )}
                          {result.status === "pending" && (
                            <Loader2 className="h-4 w-4 animate-spin text-blue-600" />
                          )}
                          <Badge
                            variant={result.status === "success" ? "default" : "destructive"}
                          >
                            {result.status === "success"
                              ? "Succès"
                              : result.status === "error"
                              ? "Erreur"
                              : "En cours"}
                          </Badge>
                        </div>
                        {result.message && (
                          <p className="text-sm text-muted-foreground">{result.message}</p>
                        )}
                        {result.formatUsed && (
                          <p className="text-xs text-muted-foreground mt-1">
                            Format: {result.formatUsed}
                          </p>
                        )}
                        {result.error && (
                          <p className="text-sm text-red-600 mt-1">{result.error}</p>
                        )}
                        {result.timestamp && (
                          <p className="text-xs text-muted-foreground mt-1">
                            {result.timestamp.toLocaleTimeString()}
                          </p>
                        )}
                      </div>
                    </div>
                  ))}
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </DashboardLayout>
  );
}

