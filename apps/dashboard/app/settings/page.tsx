"use client";

import { Suspense } from "react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { SettingsForm } from "@/components/settings/SettingsForm";

function SettingsFormWrapper() {
  return <SettingsForm />;
}

export default function SettingsPage() {
  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold">Settings</h1>
          <p className="text-muted-foreground">
            Configure Minimee and integrations
          </p>
        </div>

        <Suspense fallback={<div>Loading...</div>}>
          <SettingsFormWrapper />
        </Suspense>
      </div>
    </DashboardLayout>
  );
}

