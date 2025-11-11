/**
 * Pricing plans configuration
 */

export interface PricingPlan {
  id: string;
  name: string;
  description: string;
  price: {
    monthly: number;
    yearly: number;
  };
  features: string[];
  popular?: boolean;
  stripePriceId?: {
    monthly: string;
    yearly: string;
  };
}

export const PRICING_PLANS: PricingPlan[] = [
  {
    id: "free",
    name: "Free",
    description: "Perfect for trying out Minimee",
    price: {
      monthly: 0,
      yearly: 0,
    },
    features: [
      "1 agent",
      "100 messages/month",
      "Basic integrations",
      "Community support",
    ],
  },
  {
    id: "starter",
    name: "Starter",
    description: "For individuals getting started",
    price: {
      monthly: 29,
      yearly: 290, // 2 months free
    },
    features: [
      "5 agents",
      "1,000 messages/month",
      "All integrations",
      "Email support",
      "Priority processing",
    ],
    popular: true,
  },
  {
    id: "pro",
    name: "Pro",
    description: "For power users and small teams",
    price: {
      monthly: 99,
      yearly: 990, // 2 months free
    },
    features: [
      "Unlimited agents",
      "Unlimited messages",
      "All integrations",
      "Priority support",
      "Advanced analytics",
      "Custom integrations",
    ],
  },
  {
    id: "enterprise",
    name: "Enterprise",
    description: "For large organizations",
    price: {
      monthly: 0, // Custom pricing
      yearly: 0,
    },
    features: [
      "Everything in Pro",
      "Dedicated support",
      "SLA guarantee",
      "Custom deployment",
      "Team management",
      "Advanced security",
    ],
  },
];

export function formatPrice(price: number, currency: string = "USD"): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
  }).format(price);
}

export function getYearlyDiscount(monthlyPrice: number): number {
  return Math.round(((monthlyPrice * 12 - monthlyPrice * 10) / (monthlyPrice * 12)) * 100);
}


