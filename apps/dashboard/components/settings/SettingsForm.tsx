"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { AISettings } from "./AISettings";
import { IntegrationsSettings } from "./IntegrationsSettings";
import { PolicyEditor } from "../policy/PolicyEditor";

export function SettingsForm() {
  const searchParams = useSearchParams();
  const tabParam = searchParams.get("tab");
  const [activeTab, setActiveTab] = useState<string>(tabParam || "integrations");

  useEffect(() => {
    if (tabParam && ["ai", "integrations", "policies"].includes(tabParam)) {
      setActiveTab(tabParam);
    }
  }, [tabParam]);

  return (
    <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
      <TabsList className="grid w-full grid-cols-3">
        <TabsTrigger value="integrations">Integrations</TabsTrigger>
        <TabsTrigger value="ai">AI Models</TabsTrigger>
        <TabsTrigger value="policies">Policies & Prompts</TabsTrigger>
      </TabsList>

      <TabsContent value="integrations">
        <IntegrationsSettings />
      </TabsContent>

      <TabsContent value="ai">
        <AISettings />
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

