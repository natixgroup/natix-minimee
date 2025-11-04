"use client";

import { useState, useEffect } from "react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Loader2, CheckCircle2, XCircle, TestTube, MessageSquare, Bot, Phone, Building2 } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";

interface TestResult {
  method: string;
  sender: "user" | "minimee";
  destination: "user" | "group";
  status: "success" | "error" | "pending";
  message?: string;
  formatUsed?: string;
  timestamp?: Date;
  error?: string;
}

interface WhatsAppAccountInfo {
  phone: string;
  account_type: string;
  is_business: boolean;
  connected: boolean;
  status: string;
}

const TEST_METHODS = [
  { id: "buttons", name: "Buttons Classiques", description: "Format actuel avec buttons array" },
  { id: "interactive", name: "Interactive Message", description: "Format interactive de Baileys" },
  { id: "template", name: "Template Message", description: "Format template si supporté" },
  { id: "poll", name: "Sondage (Poll)", description: "Format sondage WhatsApp" },
];

export default function TestsPage() {
  const [userAccount, setUserAccount] = useState<WhatsAppAccountInfo | null>(null);
  const [minimeeAccount, setMinimeeAccount] = useState<WhatsAppAccountInfo | null>(null);
  const [sender, setSender] = useState<"user" | "minimee">("minimee");
  const [destination, setDestination] = useState<"user" | "group">("user");
  const [isLoading, setIsLoading] = useState(true);
  const [testResults, setTestResults] = useState<TestResult[]>([]);
  const [testingMethod, setTestingMethod] = useState<string | null>(null);

  useEffect(() => {
    loadAccountsStatus();
  }, []);

  const loadAccountsStatus = async () => {
    try {
      // Load User account status
      const userStatus = await api.getUserWhatsAppStatus();
      if (userStatus.connected) {
        try {
          const userInfo = await api.getUserWhatsAppInfo();
          setUserAccount({
            phone: userInfo.phone,
            account_type: userInfo.account_type,
            is_business: userInfo.is_business,
            connected: userStatus.connected,
            status: userStatus.status,
          });
        } catch (error) {
          // Account connected but info not available yet
          setUserAccount({
            phone: "N/A",
            account_type: "standard",
            is_business: false,
            connected: userStatus.connected,
            status: userStatus.status,
          });
        }
      } else {
        setUserAccount(null);
      }

      // Load Minimee account status
      const minimeeStatus = await api.getMinimeeWhatsAppStatus();
      if (minimeeStatus.connected) {
        try {
          const minimeeInfo = await api.getMinimeeWhatsAppInfo();
          setMinimeeAccount({
            phone: minimeeInfo.phone,
            account_type: minimeeInfo.account_type,
            is_business: minimeeInfo.is_business,
            connected: minimeeStatus.connected,
            status: minimeeStatus.status,
          });
        } catch (error) {
          // Account connected but info not available yet
          setMinimeeAccount({
            phone: "N/A",
            account_type: "standard",
            is_business: false,
            connected: minimeeStatus.connected,
            status: minimeeStatus.status,
          });
        }
      } else {
        setMinimeeAccount(null);
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to load WhatsApp accounts status");
    } finally {
      setIsLoading(false);
    }
  };

  const handleTest = async (methodId: string) => {
    // Check sender account
    if (sender === "user" && (!userAccount?.connected || !userAccount.phone || userAccount.phone === "N/A")) {
      toast.error("Le compte User WhatsApp n'est pas connecté ou le numéro n'est pas disponible");
      return;
    }

    if (sender === "minimee" && (!minimeeAccount?.connected || !minimeeAccount.phone || minimeeAccount.phone === "N/A")) {
      toast.error("Le compte Minimee WhatsApp n'est pas connecté ou le numéro n'est pas disponible");
      return;
    }

    // Check destination
    if (destination === "user" && (!userAccount?.connected || !userAccount.phone || userAccount.phone === "N/A")) {
      toast.error("Le compte User WhatsApp (destinataire) n'est pas connecté ou le numéro n'est pas disponible");
      return;
    }

    setTestingMethod(methodId);
    const testResult: TestResult = {
      method: methodId,
      sender,
      destination,
      status: "pending",
      timestamp: new Date(),
    };

    setTestResults((prev) => [...prev, testResult]);

    try {
      const result = await api.testWhatsAppMessage(
        methodId,
        sender,
        destination,
        destination === "user" ? userAccount!.phone : undefined
      );
      
      setTestResults((prev) =>
        prev.map((r) =>
          r.method === methodId && r.sender === sender && r.destination === destination && r.timestamp === testResult.timestamp
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
          r.method === methodId && r.sender === sender && r.destination === destination && r.timestamp === testResult.timestamp
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
            Testez différents formats de messages multi-choix. Les messages sont envoyés depuis le compte <strong>Minimee</strong> vers votre choix.
          </p>
        </div>

        {/* WhatsApp Accounts Status */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* User Account Card */}
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <MessageSquare className="h-5 w-5" />
                <CardTitle>Compte User (Data Source)</CardTitle>
              </div>
              <CardDescription>
                Compte utilisé pour recevoir les messages et envoyer les réponses approuvées
              </CardDescription>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <div className="flex items-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span>Chargement...</span>
                </div>
              ) : userAccount ? (
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Phone className="h-4 w-4 text-muted-foreground" />
                      <span className="font-medium">{userAccount.phone}</span>
                    </div>
                    <Badge variant={userAccount.connected ? "default" : "destructive"}>
                      {userAccount.connected ? "Connecté" : "Déconnecté"}
                    </Badge>
                  </div>
                  <div className="flex items-center gap-2">
                    {userAccount.is_business ? (
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
                  <p className="text-xs text-muted-foreground">
                    Statut: {userAccount.status}
                  </p>
                </div>
              ) : (
                <p className="text-muted-foreground">Compte non connecté</p>
              )}
            </CardContent>
          </Card>

          {/* Minimee Account Card */}
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <Bot className="h-5 w-5" />
                <CardTitle>Compte Minimee (Identity)</CardTitle>
              </div>
              <CardDescription>
                Identité Minimee - utilisé pour le chat direct et l'envoi de messages de test
              </CardDescription>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <div className="flex items-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span>Chargement...</span>
                </div>
              ) : minimeeAccount ? (
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Phone className="h-4 w-4 text-muted-foreground" />
                      <span className="font-medium">{minimeeAccount.phone}</span>
                    </div>
                    <Badge variant={minimeeAccount.connected ? "default" : "destructive"}>
                      {minimeeAccount.connected ? "Connecté" : "Déconnecté"}
                    </Badge>
                  </div>
                  <div className="flex items-center gap-2">
                    {minimeeAccount.is_business ? (
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
                  <p className="text-xs text-muted-foreground">
                    Statut: {minimeeAccount.status}
                  </p>
                </div>
              ) : (
                <p className="text-muted-foreground">Compte non connecté</p>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Sender Selection */}
        <Card>
          <CardHeader>
            <CardTitle>Expéditeur du message de test</CardTitle>
            <CardDescription>
              Choisissez depuis quel compte WhatsApp envoyer les messages de test
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <button
                onClick={() => setSender("user")}
                className={`p-4 border-2 rounded-lg transition-all ${
                  sender === "user"
                    ? "border-blue-500 bg-blue-50"
                    : "border-gray-200 hover:border-gray-300"
                }`}
              >
                <div className="flex items-center gap-3">
                  <div
                    className={`w-4 h-4 rounded-full border-2 flex items-center justify-center ${
                      sender === "user"
                        ? "border-blue-500 bg-blue-500"
                        : "border-gray-400"
                    }`}
                  >
                    {sender === "user" && (
                      <div className="w-2 h-2 rounded-full bg-white" />
                    )}
                  </div>
                  <div className="flex-1 text-left">
                    <div className="font-semibold">Compte User</div>
                    <div className="text-sm text-muted-foreground">
                      {userAccount?.phone || "N/A"} - Data Source
                    </div>
                  </div>
                </div>
              </button>

              <button
                onClick={() => setSender("minimee")}
                className={`p-4 border-2 rounded-lg transition-all ${
                  sender === "minimee"
                    ? "border-blue-500 bg-blue-50"
                    : "border-gray-200 hover:border-gray-300"
                }`}
              >
                <div className="flex items-center gap-3">
                  <div
                    className={`w-4 h-4 rounded-full border-2 flex items-center justify-center ${
                      sender === "minimee"
                        ? "border-blue-500 bg-blue-500"
                        : "border-gray-400"
                    }`}
                  >
                    {sender === "minimee" && (
                      <div className="w-2 h-2 rounded-full bg-white" />
                    )}
                  </div>
                  <div className="flex-1 text-left">
                    <div className="font-semibold">Compte Minimee</div>
                    <div className="text-sm text-muted-foreground">
                      {minimeeAccount?.phone || "N/A"} - Identity
                    </div>
                  </div>
                </div>
              </button>
            </div>
          </CardContent>
        </Card>

        {/* Destination Selection */}
        <Card>
          <CardHeader>
            <CardTitle>Destination du message de test</CardTitle>
            <CardDescription>
              Choisissez où envoyer les messages de test
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <button
                onClick={() => setDestination("user")}
                className={`p-4 border-2 rounded-lg transition-all ${
                  destination === "user"
                    ? "border-blue-500 bg-blue-50"
                    : "border-gray-200 hover:border-gray-300"
                }`}
              >
                <div className="flex items-center gap-3">
                  <div
                    className={`w-4 h-4 rounded-full border-2 flex items-center justify-center ${
                      destination === "user"
                        ? "border-blue-500 bg-blue-500"
                        : "border-gray-400"
                    }`}
                  >
                    {destination === "user" && (
                      <div className="w-2 h-2 rounded-full bg-white" />
                    )}
                  </div>
                  <div className="flex-1 text-left">
                    <div className="font-semibold">User WhatsApp</div>
                    <div className="text-sm text-muted-foreground">
                      Envoyer au numéro {userAccount?.phone || "N/A"}
                    </div>
                  </div>
                </div>
              </button>

              <button
                onClick={() => setDestination("group")}
                className={`p-4 border-2 rounded-lg transition-all ${
                  destination === "group"
                    ? "border-blue-500 bg-blue-50"
                    : "border-gray-200 hover:border-gray-300"
                }`}
              >
                <div className="flex items-center gap-3">
                  <div
                    className={`w-4 h-4 rounded-full border-2 flex items-center justify-center ${
                      destination === "group"
                        ? "border-blue-500 bg-blue-500"
                        : "border-gray-400"
                    }`}
                  >
                    {destination === "group" && (
                      <div className="w-2 h-2 rounded-full bg-white" />
                    )}
                  </div>
                  <div className="flex-1 text-left">
                    <div className="font-semibold">Groupe Minimee TEAM</div>
                    <div className="text-sm text-muted-foreground">
                      Envoyer au groupe (User + Minimee)
                    </div>
                  </div>
                </div>
              </button>
            </div>
          </CardContent>
        </Card>

        {/* Info Alert */}
        {((sender === "user" && userAccount?.connected) || (sender === "minimee" && minimeeAccount?.connected)) && (
          <Card className="bg-blue-50 border-blue-200">
            <CardContent className="pt-6">
              <div className="flex items-start gap-3">
                <TestTube className="h-5 w-5 text-blue-600 mt-0.5" />
                <div>
                  <p className="font-medium text-blue-900 mb-1">
                    Configuration du test
                  </p>
                  <p className="text-sm text-blue-700">
                    Les messages de test sont envoyés depuis le compte <strong>
                      {sender === "user" ? `User (${userAccount?.phone || "N/A"})` : `Minimee (${minimeeAccount?.phone || "N/A"})`}
                    </strong> vers{" "}
                    {destination === "user" ? (
                      <>
                        le compte <strong>User ({userAccount?.phone || "N/A"})</strong>
                      </>
                    ) : (
                      <>le groupe <strong>Minimee TEAM</strong></>
                    )}.
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Test Methods */}
        <Card>
          <CardHeader>
            <CardTitle>Méthodes de Test</CardTitle>
            <CardDescription>
              Testez chaque format de message multi-choix. Les messages seront envoyés depuis le compte{" "}
              {sender === "user" ? "User" : "Minimee"} vers{" "}
              {destination === "user" ? "le compte User" : "le groupe Minimee TEAM"}.
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
                  disabled={
                    (sender === "user" && (!userAccount?.connected || userAccount.phone === "N/A")) ||
                    (sender === "minimee" && (!minimeeAccount?.connected || minimeeAccount.phone === "N/A")) ||
                    (destination === "user" && (!userAccount?.connected || userAccount.phone === "N/A")) ||
                    testingMethod === method.id
                  }
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
                          <Badge variant="secondary">
                            Depuis: {result.sender === "user" ? "User" : "Minimee"}
                          </Badge>
                          <Badge variant="secondary">
                            Vers: {result.destination === "user" ? "User" : "Groupe"}
                          </Badge>
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
