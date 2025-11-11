"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import { Loader2 } from "lucide-react";

interface DataSourceStats {
  gmail?: {
    threads_count: number;
    messages_count: number;
    oldest_date: string | null;
    newest_date: string | null;
    last_import_date: string | null;
    last_import_type: "bulk" | null;
  };
  whatsapp?: {
    conversations_count: number;
    interlocutors_count: number;
    messages_count: number;
    oldest_date: string | null;
    newest_date: string | null;
    last_import_date: string | null;
    last_import_type: "bulk" | null;
  };
}

export function DataSourceStats() {
  const [stats, setStats] = useState<DataSourceStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        setIsLoading(true);
        setError(null);
        const result = await api.getEmbeddingsStatsBySource(1);
        setStats(result.stats);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load statistics");
      } finally {
        setIsLoading(false);
      }
    };

    fetchStats();
  }, []);

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Data Sources Statistics</CardTitle>
          <CardDescription>Loading statistics...</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Data Sources Statistics</CardTitle>
          <CardDescription className="text-destructive">{error}</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return "N/A";
    try {
      const date = new Date(dateStr);
      return date.toLocaleString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit"
      });
    } catch {
      return dateStr;
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Data Sources Statistics</CardTitle>
        <CardDescription>Overview of imported data by source</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Gmail Stats */}
        {stats?.gmail && (
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <h3 className="font-semibold text-lg">Gmail</h3>
              {stats.gmail.threads_count > 0 && (
                <span className="text-sm text-muted-foreground">
                  {stats.gmail.threads_count} thread{stats.gmail.threads_count !== 1 ? "s" : ""} • {stats.gmail.messages_count} message{stats.gmail.messages_count !== 1 ? "s" : ""}
                </span>
              )}
            </div>
            {stats.gmail.messages_count > 0 ? (
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <div className="text-muted-foreground">Date range</div>
                  <div className="font-medium">
                    {formatDate(stats.gmail.oldest_date)} → {formatDate(stats.gmail.newest_date)}
                  </div>
                </div>
                <div>
                  <div className="text-muted-foreground">Last import</div>
                  <div className="font-medium">
                    {formatDate(stats.gmail.last_import_date)}
                    {stats.gmail.last_import_type && (
                      <span className="ml-2 text-xs text-muted-foreground">
                        ({stats.gmail.last_import_type})
                      </span>
                    )}
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-sm text-muted-foreground">No Gmail data imported yet</div>
            )}
          </div>
        )}

        {/* WhatsApp Stats */}
        {stats?.whatsapp && (
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <h3 className="font-semibold text-lg">WhatsApp</h3>
              {stats.whatsapp.interlocutors_count > 0 && (
                <span className="text-sm text-muted-foreground">
                  {stats.whatsapp.interlocutors_count} interlocutor{stats.whatsapp.interlocutors_count !== 1 ? "s" : ""} • {stats.whatsapp.messages_count} message{stats.whatsapp.messages_count !== 1 ? "s" : ""}
                </span>
              )}
            </div>
            {stats.whatsapp.messages_count > 0 ? (
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <div className="text-muted-foreground">Date range</div>
                  <div className="font-medium">
                    {formatDate(stats.whatsapp.oldest_date)} → {formatDate(stats.whatsapp.newest_date)}
                  </div>
                </div>
                <div>
                  <div className="text-muted-foreground">Last import</div>
                  <div className="font-medium">
                    {formatDate(stats.whatsapp.last_import_date)}
                    {stats.whatsapp.last_import_type && (
                      <span className="ml-2 text-xs text-muted-foreground">
                        ({stats.whatsapp.last_import_type})
                      </span>
                    )}
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-sm text-muted-foreground">No WhatsApp data imported yet</div>
            )}
          </div>
        )}

        {(!stats?.gmail || stats.gmail.messages_count === 0) && 
         (!stats?.whatsapp || stats.whatsapp.messages_count === 0) && (
          <div className="text-center py-8 text-muted-foreground">
            No data sources have been imported yet
          </div>
        )}
      </CardContent>
    </Card>
  );
}

