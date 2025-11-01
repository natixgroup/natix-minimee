import { useQuery } from "@tanstack/react-query";
import { api } from "../api";

export function useLogs(params?: {
  level?: string;
  service?: string;
  start_date?: string;
  end_date?: string;
  limit?: number;
  offset?: number;
}) {
  return useQuery({
    queryKey: ["logs", params],
    queryFn: () => api.getLogs(params),
    refetchInterval: 30000, // Refresh every 30 seconds
  });
}

