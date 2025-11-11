"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { GmailConnect } from "../gmail/GmailConnect";
import { WhatsAppUserConnect } from "../whatsapp/WhatsAppUserConnect";
import { WhatsAppUpload } from "../upload/WhatsAppUpload";
import { ImportHistory } from "./ImportHistory";
import { OpenAIConfig } from "./OpenAIConfig";
import { Database, MessageSquare, KeyRound, History } from "lucide-react";

export function IntegrationsSettings() {
  return (
    <div className="space-y-8">
      {/* Sources de données */}
      <div className="space-y-4">
        <div className="flex items-center gap-3">
          <Database className="h-5 w-5 text-muted-foreground" />
          <div>
            <h2 className="text-xl font-semibold">Data Sources</h2>
            <p className="text-sm text-muted-foreground">
              Connect external services to import and index historical conversations
            </p>
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="flex items-center gap-2">
                  Gmail
                </CardTitle>
                <Badge variant="secondary">Data Source</Badge>
              </div>
              <CardDescription>
                Import emails and conversations from your Gmail account
              </CardDescription>
            </CardHeader>
            <CardContent>
              <GmailConnect />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="flex items-center gap-2">
                  WhatsApp Import
                </CardTitle>
                <Badge variant="secondary">Data Source</Badge>
              </div>
              <CardDescription>
                Upload WhatsApp conversation exports (.txt files) to import historical conversations
              </CardDescription>
            </CardHeader>
            <CardContent>
              <WhatsAppUpload />
            </CardContent>
          </Card>
        </div>

        {/* Import History */}
        <ImportHistory />
      </div>

      {/* Canaux de communication */}
      <div className="space-y-4">
        <div className="flex items-center gap-3">
          <MessageSquare className="h-5 w-5 text-muted-foreground" />
          <div>
            <h2 className="text-xl font-semibold">Communication Channels</h2>
            <p className="text-sm text-muted-foreground">
              Connect services to receive messages in real-time and communicate with Minimee
            </p>
          </div>
        </div>

        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="flex items-center gap-2">
                <MessageSquare className="h-5 w-5" />
                User WhatsApp Account
              </CardTitle>
              <div className="flex gap-2">
                <Badge variant="secondary">Communication</Badge>
                <Badge variant="outline">Data Source</Badge>
              </div>
            </div>
            <CardDescription>
              Your personal WhatsApp account for receiving messages, importing conversations, and sending approved responses.
              All agents use this single WhatsApp account with routing via [Agent Name] prefix.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <WhatsAppUserConnect />
          </CardContent>
        </Card>
      </div>

      {/* API Keys & Credentials */}
      <div className="space-y-4">
        <div className="flex items-center gap-3">
          <KeyRound className="h-5 w-5 text-muted-foreground" />
          <div>
            <h2 className="text-xl font-semibold">API Keys & Credentials</h2>
            <p className="text-sm text-muted-foreground">
              Configure API keys for external services and AI providers
            </p>
          </div>
        </div>

        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="flex items-center gap-2">
                OpenAI
              </CardTitle>
              <Badge variant="secondary">LLM Provider</Badge>
            </div>
            <CardDescription>
              Configure your OpenAI API key to use GPT models. The key will be validated before being saved.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <OpenAIConfig />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

