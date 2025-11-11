"use client";

import { useState } from "react";
import { PricingCard } from "@/components/pricing/PricingCard";
import { PlanComparison } from "@/components/pricing/PlanComparison";
import { PRICING_PLANS } from "@/components/pricing/PricingCard";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";

export default function PricingPage() {
  const [isYearly, setIsYearly] = useState(false);

  return (
    <div className="container mx-auto py-12 px-4">
      <div className="text-center space-y-4 mb-12">
        <h1 className="text-4xl font-bold">Pricing</h1>
        <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
          Choose the perfect plan for your needs. All plans include a 14-day free trial.
        </p>
      </div>

      <div className="flex justify-center items-center gap-4 mb-8">
        <Label htmlFor="billing-toggle" className={!isYearly ? "font-semibold" : ""}>
          Monthly
        </Label>
        <Switch
          id="billing-toggle"
          checked={isYearly}
          onCheckedChange={setIsYearly}
        />
        <Label htmlFor="billing-toggle" className={isYearly ? "font-semibold" : ""}>
          Yearly
        </Label>
        {isYearly && (
          <span className="text-sm text-green-600 font-medium">
            Save up to 17%
          </span>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-12">
        {PRICING_PLANS.map((plan) => (
          <PricingCard key={plan.id} plan={plan} isYearly={isYearly} />
        ))}
      </div>

      <PlanComparison plans={PRICING_PLANS} isYearly={isYearly} />
    </div>
  );
}


