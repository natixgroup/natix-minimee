import { useState, useEffect, useRef, useCallback } from "react";
import { api, ActionLog } from "../api";

export function useActionLogs(filters?: {
  action_type?: string;
  request_id?: string;
  message_id?: number;
  realTime?: boolean;
}) {
  const [logs, setLogs] = useState<ActionLog[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);

  const loadLogs = useCallback(async () => {
    try {
      setIsLoading(true);
      const fetchedLogs = await api.getActionLogs({
        action_type: filters?.action_type,
        request_id: filters?.request_id,
        message_id: filters?.message_id,
        limit: 50,
      });
      setLogs(fetchedLogs);
      setIsLoading(false);
    } catch (err) {
      setError(err as Error);
      setIsLoading(false);
    }
  }, [filters?.action_type, filters?.request_id, filters?.message_id]);

  useEffect(() => {
    // Load initial logs
    loadLogs();

    // If realTime is enabled, poll every 2 seconds
    if (filters?.realTime) {
      pollingIntervalRef.current = setInterval(() => {
        loadLogs();
      }, 2000);

      return () => {
        if (pollingIntervalRef.current) {
          clearInterval(pollingIntervalRef.current);
        }
      };
    }

    // If realTime is disabled (default), do nothing after initial load
    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
      }
    };
  }, [filters?.realTime, loadLogs]);

  return { logs, isLoading, error, refetch: loadLogs };
}

