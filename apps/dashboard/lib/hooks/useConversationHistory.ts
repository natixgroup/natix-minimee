import { useQuery } from "@tanstack/react-query";
import { api } from "../api";

export interface ChatMessage {
  id: number;
  content: string;
  sender: string;
  timestamp: string;
  source: string;
  conversation_id: string | null;
}

export function useConversationHistory(
  conversationId: string,
  userId: number = 1,
  enabled: boolean = true
) {
  return useQuery({
    queryKey: ["conversation", conversationId, userId],
    queryFn: () => api.getConversationMessages(conversationId, userId),
    enabled: enabled && !!conversationId,
  });
}

