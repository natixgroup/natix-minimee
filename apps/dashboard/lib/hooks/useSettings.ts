import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, type Setting } from "../api";
import { toast } from "sonner";

export function useSettings(userId?: number) {
  return useQuery({
    queryKey: ["settings", userId],
    queryFn: () => api.getSettings(userId),
  });
}

export function useCreateSetting() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: Parameters<typeof api.createSetting>[0]) =>
      api.createSetting(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings"] });
      toast.success("Setting saved successfully");
    },
    onError: (error: Error) => {
      toast.error(error.message);
    },
  });
}

