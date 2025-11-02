"use client";

import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api } from "@/lib/api";
import { useQuery } from "@tanstack/react-query";
import { Loader2, ChevronLeft, ChevronRight, MessageSquare, Layers, Sparkles, Tag } from "lucide-react";

interface ImportHistoryItem {
  conversation_id: string;
  messages_count: number;
  embeddings_count: number;
  chunks_count: number;
  summaries_count: number;
  first_import: string;
  last_import: string;
}

interface WhatsAppImportHistoryModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function WhatsAppImportHistoryModal({
  open,
  onOpenChange,
}: WhatsAppImportHistoryModalProps) {
  const [page, setPage] = useState(0);
  const limit = 10;

  const { data: historyData, isLoading } = useQuery({
    queryKey: ["whatsapp-import-history-all", page],
    queryFn: () => api.getWhatsAppImportHistory({ limit, offset: page * limit }),
    enabled: open,
  });

  const historyItems: ImportHistoryItem[] = historyData?.items || [];
  const total = historyData?.total || 0;
  const hasMore = historyData?.has_more || false;
  const totalPages = Math.ceil(total / limit);

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
    if (id.length > 40) {
      return id.substring(0, 20) + "..." + id.substring(id.length - 15);
    }
    return id;
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-5xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Historique des importations WhatsApp</DialogTitle>
          <DialogDescription>
            Vue détaillée de toutes les importations avec statistiques complètes
          </DialogDescription>
        </DialogHeader>

        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : historyItems.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">
            Aucun historique d'importation disponible
          </div>
        ) : (
          <>
            <div className="border rounded-lg overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Date</TableHead>
                    <TableHead>Conversation ID</TableHead>
                    <TableHead className="text-right">
                      <MessageSquare className="h-4 w-4 inline mr-1" />
                      Messages
                    </TableHead>
                    <TableHead className="text-right">
                      <Sparkles className="h-4 w-4 inline mr-1" />
                      Embeddings
                    </TableHead>
                    <TableHead className="text-right">
                      <Layers className="h-4 w-4 inline mr-1" />
                      Chunks
                    </TableHead>
                    <TableHead className="text-right">
                      <Tag className="h-4 w-4 inline mr-1" />
                      Summaries
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {historyItems.map((item) => (
                    <TableRow key={item.conversation_id}>
                      <TableCell className="text-sm">
                        {formatDate(item.last_import)}
                      </TableCell>
                      <TableCell>
                        <code className="text-xs font-mono">
                          {truncateConversationId(item.conversation_id)}
                        </code>
                      </TableCell>
                      <TableCell className="text-right font-medium">
                        {item.messages_count}
                      </TableCell>
                      <TableCell className="text-right font-medium">
                        {item.embeddings_count}
                      </TableCell>
                      <TableCell className="text-right font-medium">
                        {item.chunks_count}
                      </TableCell>
                      <TableCell className="text-right font-medium">
                        {item.summaries_count}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>

            {/* Pagination */}
            <div className="flex items-center justify-between pt-4">
              <div className="text-sm text-muted-foreground">
                Affichage de {page * limit + 1} à {Math.min((page + 1) * limit, total)} sur {total} importations
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                  disabled={page === 0}
                >
                  <ChevronLeft className="h-4 w-4" />
                  Précédent
                </Button>
                <div className="text-sm text-muted-foreground">
                  Page {page + 1} / {totalPages || 1}
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((p) => p + 1)}
                  disabled={!hasMore || page >= totalPages - 1}
                >
                  Suivant
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

