import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, type Policy } from "../api";
import { toast } from "sonner";

export function usePolicies(userId?: number) {
  return useQuery({
    queryKey: ["policies", userId],
    queryFn: () => api.getPolicies(userId),
  });
}

export function useCreatePolicy() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: Parameters<typeof api.createPolicy>[0]) =>
      api.createPolicy(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["policies"] });
      toast.success("Policy created successfully");
    },
    onError: (error: Error) => {
      toast.error(error.message);
    },
  });
}

export function useUpdatePolicy() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: number;
      data: Partial<Policy>;
    }) => api.updatePolicy(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["policies"] });
      toast.success("Policy updated successfully");
    },
    onError: (error: Error) => {
      toast.error(error.message);
    },
  });
}

