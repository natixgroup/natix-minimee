"use client";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Cpu, Database } from "lucide-react";

interface DebugInfo {
  llm_provider: string;
  llm_model: string;
  rag_context: string;
  rag_details: {
    results_count: number;
    top_similarity: number;
    avg_similarity: number;
    results: Array<{
      content: string;
      sender: string;
      timestamp: string;
      source: string;
      similarity: number;
      summary?: string;
      tags?: string;
    }>;
  };
}

interface DebugModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  debugInfo: DebugInfo | null;
}

export function DebugModal({ open, onOpenChange, debugInfo }: DebugModalProps) {
  if (!debugInfo) return null;

  const formatDate = (dateString: string) => {
    try {
      return new Date(dateString).toLocaleString("fr-FR");
    } catch {
      return dateString;
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl max-h-[90vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Database className="h-5 w-5" />
            Informations de Debug
          </DialogTitle>
          <DialogDescription>
            Détails du LLM utilisé et du contexte RAG récupéré pour cette réponse
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto pr-4">
          <div className="space-y-6">
            {/* LLM Info */}
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <Cpu className="h-4 w-4 text-muted-foreground" />
                <h3 className="font-semibold">Modèle LLM utilisé</h3>
              </div>
              <div className="space-y-2 pl-6">
                <div className="flex items-center gap-2">
                  <span className="text-sm text-muted-foreground">Provider:</span>
                  <Badge variant="outline">{debugInfo.llm_provider}</Badge>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-sm text-muted-foreground">Modèle:</span>
                  <Badge>{debugInfo.llm_model}</Badge>
                </div>
              </div>
            </div>

            {/* RAG Stats */}
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <Database className="h-4 w-4 text-muted-foreground" />
                <h3 className="font-semibold">Contexte RAG récupéré</h3>
              </div>
              <div className="space-y-2 pl-6">
                <div className="flex items-center gap-4 text-sm">
                  <div>
                    <span className="text-muted-foreground">Résultats trouvés:</span>{" "}
                    <Badge variant="secondary">{debugInfo.rag_details.results_count}</Badge>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Similarité max:</span>{" "}
                    <Badge variant="secondary">
                      {(debugInfo.rag_details.top_similarity * 100).toFixed(1)}%
                    </Badge>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Similarité moy:</span>{" "}
                    <Badge variant="secondary">
                      {(debugInfo.rag_details.avg_similarity * 100).toFixed(1)}%
                    </Badge>
                  </div>
                </div>
              </div>
            </div>

            {/* RAG Results */}
            {debugInfo.rag_details.results.length > 0 && (
              <div className="space-y-3">
                <h3 className="font-semibold">Messages similaires récupérés</h3>
                <div className="space-y-3">
                  {debugInfo.rag_details.results.map((result, index) => (
                    <div
                      key={index}
                      className="border rounded-lg p-4 space-y-2 bg-muted/50"
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <Badge variant="outline" className="text-xs">
                            {result.source}
                          </Badge>
                          <span className="text-sm font-medium">{result.sender}</span>
                          <span className="text-xs text-muted-foreground">
                            {formatDate(result.timestamp)}
                          </span>
                        </div>
                        <Badge variant="secondary">
                          {(result.similarity * 100).toFixed(1)}% similar
                        </Badge>
                      </div>
                      <p className="text-sm whitespace-pre-wrap">{result.content}</p>
                      {result.summary && (
                        <div className="text-xs text-muted-foreground pt-2 border-t">
                          <span className="font-medium">Résumé:</span> {result.summary}
                        </div>
                      )}
                      {result.tags && (
                        <div className="flex flex-wrap gap-1 pt-2">
                          {result.tags.split(",").map((tag, i) => (
                            <Badge key={i} variant="outline" className="text-xs">
                              {tag.trim()}
                            </Badge>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Full Context */}
            <div className="space-y-3">
              <h3 className="font-semibold">Contexte complet envoyé au LLM</h3>
              <div className="border rounded-lg p-4 bg-muted/50">
                <pre className="text-xs whitespace-pre-wrap font-mono">
                  {debugInfo.rag_context || "Aucun contexte RAG"}
                </pre>
              </div>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

