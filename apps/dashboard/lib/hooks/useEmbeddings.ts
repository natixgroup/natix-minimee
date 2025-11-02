import { useState, useEffect, useMemo, useRef } from "react";
import { api, EmbeddingsListResponse } from "../api";

export function useEmbeddings(params?: {
  source?: string;
  search?: string;
  message_start_date?: string;
  message_end_date?: string;
  embedding_start_date?: string;
  embedding_end_date?: string;
  page?: number;
  limit?: number;
  realTime?: boolean;
}) {
  const [data, setData] = useState<EmbeddingsListResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Memoize params to avoid unnecessary re-renders
  const paramsKey = useMemo(
    () => JSON.stringify({
      source: params?.source || "",
      search: params?.search || "",
      message_start_date: params?.message_start_date || "",
      message_end_date: params?.message_end_date || "",
      embedding_start_date: params?.embedding_start_date || "",
      embedding_end_date: params?.embedding_end_date || "",
      page: params?.page || 1,
      limit: params?.limit || 50
    }),
    [params?.source, params?.search, params?.message_start_date, params?.message_end_date, params?.embedding_start_date, params?.embedding_end_date, params?.page, params?.limit]
  );

  const fetchEmbeddings = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const result = await api.getEmbeddings({
        source: params?.source,
        search: params?.search,
        message_start_date: params?.message_start_date,
        message_end_date: params?.message_end_date,
        embedding_start_date: params?.embedding_start_date,
        embedding_end_date: params?.embedding_end_date,
        page: params?.page,
        limit: params?.limit,
      });
      setData(result);
    } catch (err) {
      setError(err as Error);
      setData(null);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    // Load initial data
    fetchEmbeddings();

    // If realTime is enabled, poll every 2 seconds
    if (params?.realTime) {
      pollingIntervalRef.current = setInterval(() => {
        fetchEmbeddings();
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
  }, [paramsKey, params?.realTime]);

  return {
    embeddings: data?.embeddings || [],
    total: data?.total || 0,
    page: data?.page || 1,
    limit: data?.limit || 50,
    totalPages: data?.total_pages || 0,
    isLoading,
    error,
    refetch: fetchEmbeddings,
  };
}

