"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Check, X } from "lucide-react";
import type { PricingPlan } from "@/lib/constants/pricing";

interface PlanComparisonProps {
  plans: PricingPlan[];
  isYearly: boolean;
}

export function PlanComparison({ plans, isYearly }: PlanComparisonProps) {
  // Extract all unique features across all plans
  const allFeatures = new Set<string>();
  plans.forEach((plan) => {
    plan.features.forEach((feature) => allFeatures.add(feature));
  });

  const featureList = Array.from(allFeatures);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Plan Comparison</CardTitle>
        <CardDescription>
          Compare features across all plans
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Feature</TableHead>
                {plans.map((plan) => (
                  <TableHead key={plan.id} className="text-center">
                    {plan.name}
                  </TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {featureList.map((feature) => (
                <TableRow key={feature}>
                  <TableCell className="font-medium">{feature}</TableCell>
                  {plans.map((plan) => (
                    <TableCell key={plan.id} className="text-center">
                      {plan.features.includes(feature) ? (
                        <Check className="h-5 w-5 text-green-600 mx-auto" />
                      ) : (
                        <X className="h-5 w-5 text-muted-foreground mx-auto" />
                      )}
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  );
}


