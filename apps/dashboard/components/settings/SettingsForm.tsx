"use client";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { AISettings } from "./AISettings";
import { IntegrationsSettings } from "./IntegrationsSettings";
import { PolicyEditor } from "../policy/PolicyEditor";

export function SettingsForm() {
  return (
    <Tabs defaultValue="ai" className="space-y-4">
      <TabsList className="grid w-full grid-cols-3">
        <TabsTrigger value="ai">AI Models</TabsTrigger>
        <TabsTrigger value="integrations">Integrations</TabsTrigger>
        <TabsTrigger value="policies">Policies & Prompts</TabsTrigger>
      </TabsList>

      <TabsContent value="ai">
        <AISettings />
      </TabsContent>

      <TabsContent value="integrations">
        <IntegrationsSettings />
      </TabsContent>

      <TabsContent value="policies">
        <Card>
          <CardHeader>
            <CardTitle>Policies & Prompts</CardTitle>
            <CardDescription>
              Configure rules, policies, and prompts that govern agent behavior and responses
            </CardDescription>
          </CardHeader>
          <CardContent>
            <PolicyEditor />
          </CardContent>
        </Card>
      </TabsContent>
    </Tabs>
  );
}

