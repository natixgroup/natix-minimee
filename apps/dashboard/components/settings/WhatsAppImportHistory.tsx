"use client";

import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { useQuery } from "@tanstack/react-query";
import { Loader2, MessageSquare, Layers, Sparkles, Tag, ChevronRight } from "lucide-react";
import { WhatsAppImportHistoryModal } from "./WhatsAppImportHistoryModal";

interface ImportHistoryItem {
  conversation_id: string;
  messages_count: number;
  embeddings_count: number;
  chunks_count: number;
  summaries_count: number;
  first_import: string;
  last_import: string;
}

export function WhatsAppImportHistory() {
  const [showModal, setShowModal] = useState(false);

  const { data: historyData, isLoading } = useQuery({
    queryKey: ["whatsapp-import-history", { limit: 3 }],
    queryFn: () => api.getWhatsAppImportHistory({ limit: 3 }),
  });

  const historyItems: ImportHistoryItem[] = historyData?.items || [];

  const formatDate = (dateString: string) => {
    try {
      const date = new Date(dateString);
      return new Intl.DateTimeFormat("fr-FR", {
        day: "numeric",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      }).format(date);
    } catch {
      return dateString;
    }
  };

  const truncateConversationId = (id: string) => {
    if (id.length > 30) {
      return id.substring(0, 15) + "..." + id.substring(id.length - 10);
    }
    return id;
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-4">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (historyItems.length === 0) {
    return (
      <div className="text-sm text-muted-foreground">
        Aucun historique d'importation disponible
      </div>
    );
  }

  return (
    <>
      <div className="space-y-3">
        {historyItems.map((item) => (
          <Card key={item.conversation_id} className="hover:shadow-md transition-shadow">
            <CardContent className="pt-4">
              <div className="space-y-3">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="text-xs text-muted-foreground mb-1">
                      {formatDate(item.last_import)}
                    </div>
                    <div className="text-sm font-mono text-xs">
                      {truncateConversationId(item.conversation_id)}
                    </div>
                  </div>
                </div>
                
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                  <div className="flex items-center gap-2">
                    <MessageSquare className="h-4 w-4 text-muted-foreground" />
                    <div>
                      <div className="font-medium">{item.messages_count}</div>
                      <div className="text-xs text-muted-foreground">Messages</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Sparkles className="h-4 w-4 text-muted-foreground" />
                    <div>
                      <div className="font-medium">{item.embeddings_count}</div>
                      <div className="text-xs text-muted-foreground">Embeddings</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Layers className="h-4 w-4 text-muted-foreground" />
                    <div>
                      <div className="font-medium">{item.chunks_count}</div>
                      <div className="text-xs text-muted-foreground">Chunks</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Tag className="h-4 w-4 text-muted-foreground" />
                    <div>
                      <div className="font-medium">{item.summaries_count}</div>
                      <div className="text-xs text-muted-foreground">Summaries</div>
                    </div>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}

        {historyData && historyData.total > 3 && (
          <Button
            variant="outline"
            className="w-full"
            onClick={() => setShowModal(true)}
          >
            Voir tout l'historique ({historyData.total} importations)
            <ChevronRight className="ml-2 h-4 w-4" />
          </Button>
        )}
      </div>

      <WhatsAppImportHistoryModal
        open={showModal}
        onOpenChange={setShowModal}
      />
    </>
  );
}

