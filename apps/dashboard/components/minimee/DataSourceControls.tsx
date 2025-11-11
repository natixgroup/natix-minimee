"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
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

interface DataSourceControlsProps {
  includedSources: string[] | null; // null = all sources included, [] = no sources, [source1, ...] = only these sources
  onSourcesChange: (sources: string[] | null) => void;
  userId?: number;
}

export function DataSourceControls({ includedSources, onSourcesChange, userId = 1 }: DataSourceControlsProps) {
  const [stats, setStats] = useState<DataSourceStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        setIsLoading(true);
        setError(null);
        const result = await api.getEmbeddingsStatsBySource(userId);
        setStats(result.stats);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load statistics");
      } finally {
        setIsLoading(false);
      }
    };

    fetchStats();
  }, [userId]);

  const handleSourceToggle = (source: string, enabled: boolean) => {
    // All available sources
    const allSources = ["whatsapp", "gmail"];
    
    if (enabled) {
      // Enabling a source
      if (includedSources === null) {
        // All sources are already included, no change needed
        return;
      }
      // Add source if not already included
      if (!includedSources.includes(source)) {
        const newSources = [...includedSources, source];
        // If we've added all sources back, reset to null (all included)
        if (newSources.length === allSources.length) {
          onSourcesChange(null);
        } else {
          onSourcesChange(newSources);
        }
      }
    } else {
      // Disabling a source
      if (includedSources === null) {
        // All sources are currently included, so we need to exclude this one
        // Create a list with all sources except the one being disabled
        const excludedSources = allSources.filter(s => s !== source);
        onSourcesChange(excludedSources);
      } else {
        // Remove source from the list
        const newSources = includedSources.filter(s => s !== source);
        // If no sources left, set to empty array (no sources)
        onSourcesChange(newSources.length === 0 ? [] : newSources);
      }
    }
  };

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return "N/A";
    try {
      const date = new Date(dateStr);
      return date.toLocaleString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
      });
    } catch {
      return dateStr;
    }
  };

  const formatDateRange = (oldest: string | null, newest: string | null) => {
    if (!oldest || !newest) return "N/A";
    const oldestDate = formatDate(oldest);
    const newestDate = formatDate(newest);
    if (oldestDate === newestDate) return oldestDate;
    return `${oldestDate} → ${newestDate}`;
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Data Sources</CardTitle>
        <CardDescription>
          Select which data sources to include in the RAG context. By default, all sources are included.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : error ? (
          <div className="text-sm text-destructive">{error}</div>
        ) : (
          <>
            {/* WhatsApp Control */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <Switch
                    id="whatsapp-source"
                    checked={includedSources === null || includedSources.includes("whatsapp")}
                    onCheckedChange={(checked) => handleSourceToggle("whatsapp", checked)}
                  />
                  <Label htmlFor="whatsapp-source" className="font-semibold text-base cursor-pointer">
                    WhatsApp
                  </Label>
                </div>
                {stats?.whatsapp && stats.whatsapp.messages_count > 0 && (
                  <div className="text-sm text-muted-foreground">
                    {stats.whatsapp.interlocutors_count} interlocutor{stats.whatsapp.interlocutors_count !== 1 ? "s" : ""} • {stats.whatsapp.messages_count} message{stats.whatsapp.messages_count !== 1 ? "s" : ""}
                  </div>
                )}
              </div>
              {stats?.whatsapp && stats.whatsapp.messages_count > 0 ? (
                <div className="pl-8 space-y-1 text-sm">
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Date range:</span>
                    <span className="font-medium">{formatDateRange(stats.whatsapp.oldest_date, stats.whatsapp.newest_date)}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Conversations:</span>
                    <span className="font-medium">{stats.whatsapp.conversations_count}</span>
                  </div>
                </div>
              ) : (
                <div className="pl-8 text-sm text-muted-foreground">No WhatsApp data imported yet</div>
              )}
            </div>

            {/* Gmail Control */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <Switch
                    id="gmail-source"
                    checked={includedSources === null || includedSources.includes("gmail")}
                    onCheckedChange={(checked) => handleSourceToggle("gmail", checked)}
                  />
                  <Label htmlFor="gmail-source" className="font-semibold text-base cursor-pointer">
                    Gmail
                  </Label>
                </div>
                {stats?.gmail && stats.gmail.messages_count > 0 && (
                  <div className="text-sm text-muted-foreground">
                    {stats.gmail.threads_count} thread{stats.gmail.threads_count !== 1 ? "s" : ""} • {stats.gmail.messages_count} message{stats.gmail.messages_count !== 1 ? "s" : ""}
                  </div>
                )}
              </div>
              {stats?.gmail && stats.gmail.messages_count > 0 ? (
                <div className="pl-8 space-y-1 text-sm">
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Date range:</span>
                    <span className="font-medium">{formatDateRange(stats.gmail.oldest_date, stats.gmail.newest_date)}</span>
                  </div>
                </div>
              ) : (
                <div className="pl-8 text-sm text-muted-foreground">No Gmail data imported yet</div>
              )}
            </div>

            {(!stats?.gmail || stats.gmail.messages_count === 0) && 
             (!stats?.whatsapp || stats.whatsapp.messages_count === 0) && (
              <div className="text-center py-4 text-sm text-muted-foreground">
                No data sources have been imported yet
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}

