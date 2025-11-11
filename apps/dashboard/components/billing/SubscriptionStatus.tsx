"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Loader2, ExternalLink } from "lucide-react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { formatPrice } from "@/lib/constants/pricing";
import { getEnv } from "@/lib/env";

interface Subscription {
  id: string;
  plan_id: string;
  status: "active" | "canceled" | "past_due" | "trialing";
  current_period_end: string;
  cancel_at_period_end: boolean;
  price: number;
  billing_period: "monthly" | "yearly";
}

export function SubscriptionStatus() {
  const router = useRouter();
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadSubscription();
  }, []);

  const loadSubscription = async () => {
    try {
      const apiUrl = getEnv().apiUrl;
      const token = localStorage.getItem("auth_token");
      
      const response = await fetch(`${apiUrl}/billing/subscription`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (response.ok) {
        const data = await response.json();
        setSubscription(data);
      } else if (response.status === 404) {
        setSubscription(null);
      }
    } catch (error) {
      console.error("Failed to load subscription:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleManageBilling = async () => {
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
      toast.error(error instanceof Error ? error.message : "Failed to open billing portal");
    }
  };

  if (isLoading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-8">
          <Loader2 className="h-6 w-6 animate-spin" />
        </CardContent>
      </Card>
    );
  }

  if (!subscription) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>No Active Subscription</CardTitle>
          <CardDescription>
            Subscribe to a plan to unlock all features
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button onClick={() => router.push("/pricing")}>
            View Plans
          </Button>
        </CardContent>
      </Card>
    );
  }

  const statusColors = {
    active: "bg-green-600",
    canceled: "bg-gray-600",
    past_due: "bg-red-600",
    trialing: "bg-blue-600",
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Current Subscription</CardTitle>
        <CardDescription>
          Your active subscription details
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium">Plan</p>
            <p className="text-2xl font-bold capitalize">{subscription.plan_id}</p>
          </div>
          <Badge className={statusColors[subscription.status]}>
            {subscription.status}
          </Badge>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <p className="text-sm text-muted-foreground">Price</p>
            <p className="text-lg font-semibold">
              {formatPrice(subscription.price)}/{subscription.billing_period === "monthly" ? "mo" : "yr"}
            </p>
          </div>
          <div>
            <p className="text-sm text-muted-foreground">
              {subscription.cancel_at_period_end ? "Cancels on" : "Renews on"}
            </p>
            <p className="text-lg font-semibold">
              {new Date(subscription.current_period_end).toLocaleDateString()}
            </p>
          </div>
        </div>

        {subscription.cancel_at_period_end && (
          <div className="rounded-md bg-yellow-50 dark:bg-yellow-900/20 p-3">
            <p className="text-sm text-yellow-800 dark:text-yellow-200">
              Your subscription will cancel at the end of the current billing period.
            </p>
          </div>
        )}

        <div className="flex gap-2">
          <Button onClick={handleManageBilling} variant="outline">
            <ExternalLink className="mr-2 h-4 w-4" />
            Manage Billing
          </Button>
          {!subscription.cancel_at_period_end && (
            <Button
              variant="outline"
              onClick={async () => {
                try {
                  const apiUrl = getEnv().apiUrl;
                  const token = localStorage.getItem("auth_token");
                  
                  const response = await fetch(`${apiUrl}/billing/cancel`, {
                    method: "POST",
                    headers: {
                      Authorization: `Bearer ${token}`,
                    },
                  });

                  if (!response.ok) {
                    throw new Error("Failed to cancel subscription");
                  }

                  toast.success("Subscription will cancel at period end");
                  loadSubscription();
                } catch (error) {
                  toast.error(error instanceof Error ? error.message : "Failed to cancel subscription");
                }
              }}
            >
              Cancel Subscription
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

