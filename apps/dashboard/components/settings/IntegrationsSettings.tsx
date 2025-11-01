"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { GmailConnect } from "../gmail/GmailConnect";
import { WhatsAppConnect } from "../whatsapp/WhatsAppConnect";
import { WhatsAppUpload } from "../upload/WhatsAppUpload";
import { Database, MessageSquare } from "lucide-react";

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
                WhatsApp Bridge
              </CardTitle>
              <div className="flex gap-2">
                <Badge variant="secondary">Communication</Badge>
                <Badge variant="outline">Real-time</Badge>
              </div>
            </div>
            <CardDescription>
              Connect WhatsApp to receive messages in real-time and let Minimee respond automatically. 
              Messages are also indexed as a data source for context.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <WhatsAppConnect />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

