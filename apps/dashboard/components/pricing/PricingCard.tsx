"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Check } from "lucide-react";
import { formatPrice, type PricingPlan } from "@/lib/constants/pricing";
import { useAuth } from "@/lib/hooks/useAuth";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { getEnv } from "@/lib/env";

export { PRICING_PLANS } from "@/lib/constants/pricing";

interface PricingCardProps {
  plan: PricingPlan;
  isYearly: boolean;
}

export function PricingCard({ plan, isYearly }: PricingCardProps) {
  const { isAuthenticated } = useAuth();
  const router = useRouter();
  const price = isYearly ? plan.price.yearly : plan.price.monthly;
  const displayPrice = price === 0 ? "Custom" : formatPrice(isYearly ? price / 12 : price);
  const period = isYearly ? "month" : "month";

  const handleSubscribe = async () => {
    if (!isAuthenticated) {
      toast.error("Please sign in to subscribe");
      router.push("/auth/login");
      return;
    }

    if (plan.id === "enterprise") {
      toast.info("Please contact us for enterprise pricing");
      return;
    }

    try {
      const apiUrl = getEnv().apiUrl;
      const token = localStorage.getItem("auth_token");
      
      const response = await fetch(`${apiUrl}/billing/create-checkout-session`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          plan_id: plan.id,
          billing_period: isYearly ? "yearly" : "monthly",
        }),
      });

      if (!response.ok) {
        throw new Error("Failed to create checkout session");
      }

      const { session_url } = await response.json();
      window.location.href = session_url;
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to start checkout");
    }
  };

  return (
    <Card className={`relative ${plan.popular ? "border-primary shadow-lg" : ""}`}>
      {plan.popular && (
        <div className="absolute -top-3 left-1/2 -translate-x-1/2">
          <Badge className="bg-primary">Most Popular</Badge>
        </div>
      )}
      <CardHeader>
        <CardTitle className="text-2xl">{plan.name}</CardTitle>
        <CardDescription>{plan.description}</CardDescription>
        <div className="mt-4">
          <div className="flex items-baseline gap-2">
            <span className="text-4xl font-bold">
              {price === 0 ? "Custom" : displayPrice}
            </span>
            {price > 0 && (
              <span className="text-muted-foreground">/{period}</span>
            )}
          </div>
          {isYearly && price > 0 && (
            <p className="text-sm text-muted-foreground mt-1">
              Billed annually ({formatPrice(price)}/year)
            </p>
          )}
        </div>
      </CardHeader>
      <CardContent>
        <ul className="space-y-3 mb-6">
          {plan.features.map((feature, index) => (
            <li key={index} className="flex items-start gap-2">
              <Check className="h-5 w-5 text-green-600 flex-shrink-0 mt-0.5" />
              <span className="text-sm">{feature}</span>
            </li>
          ))}
        </ul>
        <Button
          className="w-full"
          variant={plan.popular ? "default" : "outline"}
          onClick={handleSubscribe}
        >
          {plan.id === "enterprise" ? "Contact Sales" : "Get Started"}
        </Button>
      </CardContent>
    </Card>
  );
}

