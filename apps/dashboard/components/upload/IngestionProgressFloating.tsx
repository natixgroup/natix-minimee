"use client";

import { useState, useEffect, useRef } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import {
  ChevronDown,
  ChevronUp,
  X,
  Loader2,
  CheckCircle2,
  AlertCircle,
  Code,
  StopCircle,
} from "lucide-react";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { ScrollArea } from "@/components/ui/scroll-area";
import { getEnv } from "@/lib/env";

interface ProgressData {
  step?: string;
  message?: string;
  current?: number;
  total?: number;
  percent?: number;
  embeddings_created?: number;
  eta_seconds?: number;
  type?: string;
  data?: any;
}

interface IngestionProgressFloatingProps {
  jobId: number;
  fileName: string;
  onClose: () => void;
  onProgressUpdate?: (progress: any) => void;
}

export function IngestionProgressFloating({
  jobId,
  fileName,
  onClose,
  onProgressUpdate,
}: IngestionProgressFloatingProps) {
  const [progress, setProgress] = useState<ProgressData | null>(null);
  const [status, setStatus] = useState<"running" | "completed" | "failed" | "cancelled">(
    "running"
  );
  const [isCancelling, setIsCancelling] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const [llmLogs, setLlmLogs] = useState<any[]>([]);
  const [showLlmLogs, setShowLlmLogs] = useState(false);
  const [importLogs, setImportLogs] = useState<any[]>([]);
  const [showImportLogs, setShowImportLogs] = useState(true); // Show by default for Gmail/WhatsApp
  const logsEndRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const isMountedRef = useRef(true);

  useEffect(() => {
    isMountedRef.current = true;
    
    // Load job_id from localStorage on mount
    const savedJobId = localStorage.getItem("activeIngestionJobId");
    if (savedJobId && parseInt(savedJobId) === jobId) {
      // Job is already in progress, connect to WebSocket
      connectWebSocket(parseInt(savedJobId));
    } else {
      // New job, connect immediately
      connectWebSocket(jobId);
      localStorage.setItem("activeIngestionJobId", jobId.toString());
    }

    return () => {
      isMountedRef.current = false;
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
      if (wsRef.current) {
        try {
          wsRef.current.onerror = null;
          wsRef.current.onclose = null;
          wsRef.current.close();
        } catch {
          // Ignore errors during cleanup
        }
        wsRef.current = null;
      }
    };
  }, [jobId]);

  const connectWebSocket = (jobId: number) => {
    if (!isMountedRef.current) return;

    // Use API URL instead of window.location.host to connect to backend
    const apiUrl = getEnv().apiUrl;
    const wsUrl = apiUrl.replace(/^http/, "ws") + `/ingest/ws/${jobId}`;

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        if (!isMountedRef.current) {
          ws.close();
          return;
        }
        reconnectAttemptsRef.current = 0; // Reset on successful connection
        console.log(`[ImportLogs] WebSocket connected for job ${jobId}`);
      };
      
      ws.onerror = (error) => {
        console.error(`[ImportLogs] WebSocket error for job ${jobId}:`, error);
      };

      ws.onmessage = (event) => {
        if (!isMountedRef.current) return;

        // Handle pong (keepalive)
        if (event.data === "pong") {
          return;
        }

        try {
          const data = JSON.parse(event.data);
          
          // Handle ping (keepalive)
          if (data.type === "ping") {
            ws.send("pong");
            return;
          }
          
          if (data.type === "ingestion_progress") {
            const progressData = data.data;
            setProgress(progressData);
            
            // Notify parent component of progress update
            if (onProgressUpdate) {
              onProgressUpdate(progressData);
            }

            // Add import logs for Gmail/WhatsApp
            // Debug: log to console to see what we receive
            if (progressData.thread_log || progressData.message_log || progressData.indexing_log) {
              console.log("[ImportLogs] Received log:", {
                thread_log: progressData.thread_log,
                message_log: progressData.message_log,
                indexing_log: progressData.indexing_log
              });
              
              const logEntry = {
                timestamp: new Date().toISOString(),
                type: progressData.thread_log ? "thread" : progressData.message_log ? "message" : "indexing",
                data: progressData.thread_log || progressData.message_log || progressData.indexing_log
              };
              setImportLogs((prev) => [...prev, logEntry].slice(-100)); // Keep last 100 logs
              
              // Auto-scroll to bottom
              setTimeout(() => {
                logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
              }, 100);
            } else {
              // Debug: log when we receive progress but no logs
              console.log("[ImportLogs] Progress received but no logs:", {
                step: progressData.step,
                message: progressData.message,
                has_thread_log: !!progressData.thread_log,
                has_message_log: !!progressData.message_log,
                has_indexing_log: !!progressData.indexing_log,
                keys: Object.keys(progressData)
              });
            }

            // Update status based on step
            if (progressData.step === "complete") {
              setStatus("completed");
              localStorage.removeItem("activeIngestionJobId");
              // Dispatch event for global component
              window.dispatchEvent(new CustomEvent("ingestionJobComplete"));
            } else if (progressData.step === "failed") {
              setStatus("failed");
              localStorage.removeItem("activeIngestionJobId");
              // Dispatch event for global component
              window.dispatchEvent(new CustomEvent("ingestionJobComplete"));
            } else if (progressData.step === "cancelled") {
              setStatus("cancelled");
              localStorage.removeItem("activeIngestionJobId");
              // Dispatch event for global component
              window.dispatchEvent(new CustomEvent("ingestionJobComplete"));
            } else {
              setStatus("running");
            }
          } else if (data.type === "llm_log" || data.data?.type === "llm_call") {
            // Add LLM log
            const logEntry = data.data || data;
            setLlmLogs((prev) => [...prev, logEntry].slice(-50)); // Keep last 50 logs
          }
        } catch (error) {
          // Only log parsing errors for malformed JSON (not for expected non-JSON messages)
          if (typeof event.data === "string" && event.data.trim().startsWith("{")) {
            // Silently ignore - likely malformed JSON
          }
        }
      };

      ws.onerror = () => {
        // Don't log errors - they're expected when backend is unavailable
        // The onclose handler will handle reconnection
      };

      ws.onclose = () => {
        if (!isMountedRef.current) return;

        // Attempt to reconnect if job is still running with exponential backoff
        setStatus((currentStatus) => {
          if (currentStatus === "running" && isMountedRef.current) {
            const delay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 30000); // Max 30s
            reconnectAttemptsRef.current += 1;
            
            reconnectTimeoutRef.current = setTimeout(() => {
              if (isMountedRef.current) {
                connectWebSocket(jobId);
              }
            }, delay);
          }
          return currentStatus;
        });
      };
    } catch (error) {
      // Don't log connection errors - they're expected when backend is unavailable
      
      // Retry with exponential backoff
      if (isMountedRef.current) {
        const delay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 30000);
        reconnectAttemptsRef.current += 1;
        
        reconnectTimeoutRef.current = setTimeout(() => {
          if (isMountedRef.current) {
            connectWebSocket(jobId);
          }
        }, delay);
      }
    }
  };

  const formatTime = (seconds?: number) => {
    if (!seconds) return "";
    if (seconds < 60) return `${Math.round(seconds)}s`;
    const minutes = Math.floor(seconds / 60);
    const secs = Math.round(seconds % 60);
    return `${minutes}m ${secs}s`;
  };

  const handleCancel = async () => {
    if (isCancelling) return;
    
    setIsCancelling(true);
    try {
      await api.cancelIngestionJob(jobId);
      toast.success("Import cancelled");
      setStatus("cancelled");
      localStorage.removeItem("activeIngestionJobId");
      window.dispatchEvent(new CustomEvent("ingestionJobComplete"));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to cancel import");
      setIsCancelling(false);
    }
  };

  const getStepLabel = (step?: string) => {
    const labels: Record<string, string> = {
      parsing: "Parsing",
      saving_messages: "Sauvegarde messages",
      chunking: "Création blocs",
      topic_generation: "Génération topics",
      embedding: "Vectorisation",
      fetching: "Récupération Gmail",
      indexing: "Indexation",
      complete: "Terminé",
      failed: "Échec",
      cancelled: "Annulé",
    };
    return labels[step || ""] || step || "En cours";
  };

  return (
    <Card className="fixed bottom-4 right-4 w-96 z-50 shadow-lg">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-medium">{fileName}</CardTitle>
          <div className="flex items-center gap-2">
            {status === "running" && (
              <Button
                variant="ghost"
                size="sm"
                onClick={handleCancel}
                disabled={isCancelling}
                className="text-red-500 hover:text-red-600 hover:bg-red-50"
              >
                <StopCircle className="h-4 w-4" />
              </Button>
            )}
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setIsExpanded(!isExpanded)}
            >
              {isExpanded ? (
                <ChevronUp className="h-4 w-4" />
              ) : (
                <ChevronDown className="h-4 w-4" />
              )}
            </Button>
            <Button variant="ghost" size="sm" onClick={onClose}>
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-3">
        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs">
            <span className="text-muted-foreground">
              {getStepLabel(progress?.step)}
            </span>
            {status === "running" && (
              <Loader2 className="h-3 w-3 animate-spin text-primary" />
            )}
            {status === "completed" && (
              <CheckCircle2 className="h-3 w-3 text-green-500" />
            )}
            {status === "failed" && (
              <AlertCircle className="h-3 w-3 text-red-500" />
            )}
          </div>

          {progress && (
            <>
              <Progress
                value={progress.percent || 0}
                className="h-2"
              />
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>
                  {progress.current || 0}/{progress.total || 0}
                </span>
                {progress.eta_seconds && (
                  <span>ETA: {formatTime(progress.eta_seconds)}</span>
                )}
              </div>
              {progress.message && (
                <p className="text-xs text-muted-foreground">
                  {progress.message}
                </p>
              )}
            </>
          )}

          {status === "completed" && (
            <Badge variant="outline" className="w-full justify-center">
              Import terminé avec succès
            </Badge>
          )}

            {status === "failed" && (
              <Badge variant="destructive" className="w-full justify-center">
                Échec de l'import
              </Badge>
            )}

            {status === "cancelled" && (
              <Badge variant="outline" className="w-full justify-center border-orange-500 text-orange-600">
                Import annulé
              </Badge>
            )}
        </div>

        {isExpanded && (
          <div className="space-y-2 pt-2 border-t">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium">Import Logs</span>
              <div className="flex gap-1">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowImportLogs(!showImportLogs)}
                >
                  <Code className="h-3 w-3" />
                </Button>
              </div>
            </div>

            {showImportLogs && (
              <ScrollArea className="h-64 w-full rounded border bg-black p-2">
                <div className="space-y-1 font-mono text-xs">
                  {importLogs.length === 0 ? (
                    <p className="text-green-400">
                      Waiting for import logs...
                    </p>
                  ) : (
                    importLogs.map((log, idx) => {
                      const data = log.data;
                      if (log.type === "thread") {
                        return (
                          <div key={idx} className="text-green-400">
                            <span className="text-green-500">[THREAD]</span>{" "}
                            <span className="font-semibold">{data.subject}</span>
                            <div className="text-green-300 pl-4 text-[10px]">
                              From: {data.participants?.join(", ") || "Unknown"}
                            </div>
                            <div className="text-green-300 pl-4 text-[10px]">
                              {data.message_count} messages | {new Date(data.last_date).toLocaleString()}
                            </div>
                          </div>
                        );
                      } else if (log.type === "message") {
                        return (
                          <div key={idx} className="text-green-400">
                            <span className="text-green-500">[EMAIL]</span>{" "}
                            <span className="text-green-300">{data.from}</span>
                            <div className="text-green-300 pl-4 text-[10px]">
                              {data.subject}
                            </div>
                            <div className="text-green-400 pl-4 text-[10px] italic">
                              {data.body_preview}
                            </div>
                          </div>
                        );
                      } else if (log.type === "indexing") {
                        return (
                          <div key={idx} className="text-green-400">
                            <span className="text-green-500">[INDEX]</span>{" "}
                            <span className="font-semibold">{data.subject}</span>
                            {data.status === "completed" ? (
                              <div className="text-green-300 pl-4 text-[10px]">
                                ✓ {data.chunks} chunks, {data.embeddings} embeddings
                              </div>
                            ) : data.status === "failed" ? (
                              <div className="text-red-400 pl-4 text-[10px]">
                                ✗ Error: {data.error}
                              </div>
                            ) : (
                              <div className="text-green-300 pl-4 text-[10px]">
                                Indexing...
                              </div>
                            )}
                          </div>
                        );
                      }
                      return null;
                    })
                  )}
                  <div ref={logsEndRef} />
                </div>
              </ScrollArea>
            )}

            {showLlmLogs && llmLogs.length > 0 && (
              <div className="mt-2">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-medium">Logs LLM</span>
                </div>
                <ScrollArea className="h-48 w-full rounded border p-2">
                  <div className="space-y-2">
                    {llmLogs.map((log, idx) => (
                      <div
                        key={idx}
                        className="text-xs bg-muted p-2 rounded font-mono"
                      >
                        <div className="font-semibold">
                          {log.type === "llm_call" ? "Request" : "Error"}
                        </div>
                        {log.request && (
                          <div className="mt-1 text-muted-foreground">
                            {log.request.substring(0, 100)}...
                          </div>
                        )}
                        {log.response && (
                          <div className="mt-1 text-green-600">
                            {log.response.substring(0, 100)}...
                          </div>
                        )}
                        {log.error && (
                          <div className="mt-1 text-red-600">{log.error}</div>
                        )}
                        {log.duration_ms && (
                          <div className="mt-1 text-xs text-muted-foreground">
                            {log.duration_ms}ms
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </ScrollArea>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

