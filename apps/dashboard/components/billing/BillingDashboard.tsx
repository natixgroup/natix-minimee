"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useRouter } from "next/navigation";
import { getEnv } from "@/lib/env";

export function BillingDashboard() {
  const router = useRouter();

  return (
    <div className="grid gap-6 md:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>Payment Method</CardTitle>
          <CardDescription>
            Manage your payment methods
          </CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground mb-4">
            Update your payment method in the billing portal
          </p>
          <Button
            variant="outline"
            onClick={async () => {
              try {
                const apiUrl = getEnv().apiUrl;
                const token = localStorage.getItem("auth_token");
                
                const response = await fetch(`${apiUrl}/billing/portal-session`, {
                  method: "POST",
                  headers: {
                    Authorization: `Bearer ${token}`,
                  },
                });

                if (!response.ok) {
                  throw new Error("Failed to create portal session");
                }

                const { url } = await response.json();
                window.location.href = url;
              } catch (error) {
                console.error("Failed to open billing portal:", error);
              }
            }}
          >
            Manage Payment Methods
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Billing History</CardTitle>
          <CardDescription>
            View your past invoices
          </CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground mb-4">
            Access your billing history and download invoices
          </p>
          <Button
            variant="outline"
            onClick={async () => {
              try {
                const apiUrl = getEnv().apiUrl;
                const token = localStorage.getItem("auth_token");
                
                const response = await fetch(`${apiUrl}/billing/portal-session`, {
                  method: "POST",
                  headers: {
                    Authorization: `Bearer ${token}`,
                  },
                });

                if (!response.ok) {
                  throw new Error("Failed to create portal session");
                }

                const { url } = await response.json();
                window.location.href = url;
              } catch (error) {
                console.error("Failed to open billing portal:", error);
              }
            }}
          >
            View Billing History
          </Button>
        </CardContent>
      </Card>

      <Card className="md:col-span-2">
        <CardHeader>
          <CardTitle>Change Plan</CardTitle>
          <CardDescription>
            Upgrade or downgrade your subscription
          </CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground mb-4">
            Compare plans and choose the one that fits your needs
          </p>
          <Button onClick={() => router.push("/pricing")}>
            View Plans
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}

