"use client";

import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { BillingDashboard } from "@/components/billing/BillingDashboard";
import { SubscriptionStatus } from "@/components/billing/SubscriptionStatus";

export default function BillingPage() {
  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold">Billing</h1>
          <p className="text-muted-foreground">
            Manage your subscription and billing information
          </p>
        </div>

        <SubscriptionStatus />
        <BillingDashboard />
      </div>
    </DashboardLayout>
  );
}


