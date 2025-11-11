import { useState, useCallback } from "react";
import { api } from "../api";
import { toast } from "sonner";

export function useChatStream() {
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const sendMessage = useCallback(
    async (
      content: string,
      userId: number,
      conversationId: string,
      onToken: (token: string) => void,
      onComplete: (response: string, actions: any[], debugInfo?: any) => void,
      includedSources?: string[]
    ) => {
      setIsStreaming(true);
      setError(null);

      try {
        await api.chatStream(
          content,
          userId,
          conversationId,
          includedSources,
          (token) => {
            onToken(token);
          },
          (response, actions, debugInfo) => {
            setIsStreaming(false);
            onComplete(response, actions, debugInfo);
          },
          (error) => {
            setIsStreaming(false);
            setError(error);
            toast.error(`Chat error: ${error.message}`);
          }
        );
      } catch (err) {
        setIsStreaming(false);
        const error = err instanceof Error ? err : new Error(String(err));
        setError(error);
        toast.error(`Failed to send message: ${error.message}`);
      }
    },
    []
  );

  return {
    sendMessage,
    isStreaming,
    error,
  };
}

