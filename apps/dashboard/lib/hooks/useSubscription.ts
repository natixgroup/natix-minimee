import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { getEnv } from "../env";

interface Subscription {
  id: string;
  plan_id: string;
  status: "active" | "canceled" | "past_due" | "trialing";
  current_period_end: string;
  cancel_at_period_end: boolean;
  price: number;
  billing_period: "monthly" | "yearly";
}

async function fetchSubscription(): Promise<Subscription | null> {
  const apiUrl = getEnv().apiUrl;
  const token = localStorage.getItem("auth_token");
  
  const response = await fetch(`${apiUrl}/billing/subscription`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (response.status === 404) {
    return null;
  }

  if (!response.ok) {
    throw new Error("Failed to fetch subscription");
  }

  return response.json();
}

export function useSubscription() {
  return useQuery({
    queryKey: ["subscription"],
    queryFn: fetchSubscription,
    retry: false,
  });
}

export function useCancelSubscription() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async () => {
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

      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["subscription"] });
      toast.success("Subscription will cancel at period end");
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Failed to cancel subscription");
    },
  });
}

