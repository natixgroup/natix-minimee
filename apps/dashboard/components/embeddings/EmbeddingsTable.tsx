"use client";

import { useState, useMemo, useEffect } from "react";
import { useEmbeddings } from "@/lib/hooks/useEmbeddings";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { ChevronLeft, ChevronRight, Eye, ChevronDown, ChevronUp, Filter, X } from "lucide-react";

const TRUNCATE_LENGTH = 150;

const TIME_FILTERS = [
  { label: "Last Hour", value: "last_hour" },
  { label: "Today", value: "today" },
  { label: "Yesterday", value: "yesterday" },
  { label: "Last 7 Days", value: "last_7_days" },
  { label: "Last 30 Days", value: "last_30_days" },
  { label: "All Time", value: "all" },
] as const;

type TimeFilter = typeof TIME_FILTERS[number]["value"];

const SOURCES = ["dashboard", "whatsapp", "gmail"] as const;

// Simple Tooltip component
function Tooltip({ children, content }: { children: React.ReactNode; content: string }) {
  const [show, setShow] = useState(false);
  
  if (content.length <= TRUNCATE_LENGTH) {
    return <>{children}</>;
  }

  return (
    <div
      className="relative inline-block w-full"
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
    >
      {children}
      {show && (
        <div className="absolute z-50 bottom-full left-0 mb-2 w-80 max-w-[80vw] p-3 bg-popover text-popover-foreground text-sm rounded-md border shadow-lg whitespace-pre-wrap break-words">
          {content}
        </div>
      )}
    </div>
  );
}

export function EmbeddingsTable() {
  const [messageTimeFilter, setMessageTimeFilter] = useState<TimeFilter>("all");
  const [embeddingTimeFilter, setEmbeddingTimeFilter] = useState<TimeFilter>("all");
  const [selectedSources, setSelectedSources] = useState<Set<string>>(new Set());
  const [search, setSearch] = useState<string>("");
  const [page, setPage] = useState(1);
  const [limit] = useState(50);
  const [selectedEmbedding, setSelectedEmbedding] = useState<number | null>(null);
  const [searchDebounce, setSearchDebounce] = useState<NodeJS.Timeout | null>(null);
  const [realTime, setRealTime] = useState<boolean>(false);
  const [filtersExpanded, setFiltersExpanded] = useState<boolean>(false);

  // Load filters expanded state from localStorage
  useEffect(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem("embeddings-filters-expanded");
      if (saved !== null) {
        setFiltersExpanded(saved === "true");
      }
    }
  }, []);

  // Save filters expanded state to localStorage
  useEffect(() => {
    if (typeof window !== "undefined") {
      localStorage.setItem("embeddings-filters-expanded", String(filtersExpanded));
    }
  }, [filtersExpanded]);

  // Calculate message date range from time filter
  const messageDateRange = useMemo(() => {
    const now = new Date();
    let start_date: Date | null = null;
    let end_date: Date | null = null;

    switch (messageTimeFilter) {
      case "last_hour":
        start_date = new Date(now.getTime() - 60 * 60 * 1000);
        break;
      case "today":
        start_date = new Date(now.setHours(0, 0, 0, 0));
        break;
      case "yesterday":
        const yesterday = new Date(now);
        yesterday.setDate(yesterday.getDate() - 1);
        start_date = new Date(yesterday.setHours(0, 0, 0, 0));
        end_date = new Date(yesterday.setHours(23, 59, 59, 999));
        break;
      case "last_7_days":
        start_date = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
        break;
      case "last_30_days":
        start_date = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
        break;
      case "all":
        start_date = null;
        break;
    }

    return {
      start_date: start_date?.toISOString(),
      end_date: end_date?.toISOString(),
    };
  }, [messageTimeFilter]);

  // Calculate embedding date range from time filter
  const embeddingDateRange = useMemo(() => {
    const now = new Date();
    let start_date: Date | null = null;
    let end_date: Date | null = null;

    switch (embeddingTimeFilter) {
      case "last_hour":
        start_date = new Date(now.getTime() - 60 * 60 * 1000);
        break;
      case "today":
        start_date = new Date(now.setHours(0, 0, 0, 0));
        break;
      case "yesterday":
        const yesterday = new Date(now);
        yesterday.setDate(yesterday.getDate() - 1);
        start_date = new Date(yesterday.setHours(0, 0, 0, 0));
        end_date = new Date(yesterday.setHours(23, 59, 59, 999));
        break;
      case "last_7_days":
        start_date = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
        break;
      case "last_30_days":
        start_date = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
        break;
      case "all":
        start_date = null;
        break;
    }

    return {
      start_date: start_date?.toISOString(),
      end_date: end_date?.toISOString(),
    };
  }, [embeddingTimeFilter]);

  // Determine source filter value (first selected source or undefined)
  const sourceFilter = useMemo(() => {
    if (selectedSources.size === 0) return undefined;
    return Array.from(selectedSources)[0];
  }, [selectedSources]);

  const { embeddings, total, totalPages, isLoading, error } = useEmbeddings({
    source: sourceFilter,
    search: search || undefined,
    message_start_date: messageDateRange.start_date,
    message_end_date: messageDateRange.end_date,
    embedding_start_date: embeddingDateRange.start_date,
    embedding_end_date: embeddingDateRange.end_date,
    page,
    limit,
    realTime,
  });

  const handleSearchChange = (value: string) => {
    // Debounce search
    if (searchDebounce) {
      clearTimeout(searchDebounce);
    }
    const timeout = setTimeout(() => {
      setSearch(value);
      setPage(1); // Reset to first page on search
    }, 500);
    setSearchDebounce(timeout);
  };

  const toggleSource = (source: string) => {
    const newSet = new Set(selectedSources);
    if (newSet.has(source)) {
      newSet.delete(source);
    } else {
      newSet.add(source);
    }
    setSelectedSources(newSet);
    setPage(1);
  };

  const truncateText = (text: string, maxLength: number = TRUNCATE_LENGTH) => {
    if (text.length <= maxLength) return text;
    return text.substring(0, maxLength) + "...";
  };

  const selectedEmbeddingData = embeddings.find((e) => e.id === selectedEmbedding);

  if (isLoading && embeddings.length === 0) {
    return <div className="text-muted-foreground">Loading embeddings...</div>;
  }

  if (error) {
    return <div className="text-destructive">Error loading embeddings: {error.message}</div>;
  }

  return (
    <>
      {/* Filters Card */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Filter className="h-5 w-5" />
            Filters
            <Button
              variant="ghost"
              size="sm"
              className="ml-auto h-8 w-8 p-0"
              onClick={() => setFiltersExpanded(!filtersExpanded)}
            >
              {filtersExpanded ? (
                <ChevronUp className="h-4 w-4" />
              ) : (
                <ChevronDown className="h-4 w-4" />
              )}
            </Button>
          </CardTitle>
        </CardHeader>
        <div
          className={`overflow-hidden transition-all duration-300 ease-in-out ${
            filtersExpanded ? "max-h-[2000px] opacity-100" : "max-h-0 opacity-0"
          }`}
        >
          <CardContent className="space-y-4">
            {/* Message Date Filter */}
            <div>
              <label className="text-sm font-medium mb-2 block">Message Date</label>
              <div className="flex flex-wrap gap-2">
                {TIME_FILTERS.map((filter) => (
                  <Button
                    key={filter.value}
                    variant={messageTimeFilter === filter.value ? "default" : "outline"}
                    size="sm"
                    onClick={() => {
                      setMessageTimeFilter(filter.value);
                      setPage(1);
                    }}
                  >
                    {filter.label}
                  </Button>
                ))}
              </div>
            </div>

            {/* Embedding Date Filter */}
            <div>
              <label className="text-sm font-medium mb-2 block">Embedding Date</label>
              <div className="flex flex-wrap gap-2">
                {TIME_FILTERS.map((filter) => (
                  <Button
                    key={filter.value}
                    variant={embeddingTimeFilter === filter.value ? "default" : "outline"}
                    size="sm"
                    onClick={() => {
                      setEmbeddingTimeFilter(filter.value);
                      setPage(1);
                    }}
                  >
                    {filter.label}
                  </Button>
                ))}
              </div>
            </div>

            {/* Source Filter */}
            <div>
              <label className="text-sm font-medium mb-2 block">
                Source
                {selectedSources.size > 0 && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="ml-2 h-6 px-2"
                    onClick={() => {
                      setSelectedSources(new Set());
                      setPage(1);
                    }}
                  >
                    <X className="h-3 w-3 mr-1" />
                    Clear
                  </Button>
                )}
              </label>
              <div className="flex flex-wrap gap-2">
                {SOURCES.map((source) => (
                  <Button
                    key={source}
                    variant={selectedSources.has(source) ? "default" : "outline"}
                    size="sm"
                    onClick={() => toggleSource(source)}
                  >
                    {source.charAt(0).toUpperCase() + source.slice(1)}
                  </Button>
                ))}
              </div>
            </div>

            {/* Search and Real-time Toggle */}
            <div className="flex gap-4 items-center">
              <div className="flex-1">
                <label className="text-sm font-medium mb-2 block">Search</label>
                <Input
                  placeholder="Search in text content..."
                  onChange={(e) => handleSearchChange(e.target.value)}
                />
              </div>
              <div>
                <label className="text-sm font-medium mb-2 block">Options</label>
                <div className="flex items-center gap-2">
                  <Switch
                    id="realtime-embeddings"
                    checked={realTime}
                    onCheckedChange={setRealTime}
                  />
                  <Label htmlFor="realtime-embeddings" className="cursor-pointer">
                    Temps réel
                  </Label>
                </div>
              </div>
            </div>
          </CardContent>
        </div>
      </Card>

      {/* Embeddings Table */}
      <Card>
        <CardHeader>
          <CardTitle>Embeddings ({total} total)</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="rounded-md border max-h-[600px] overflow-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[80px]">ID</TableHead>
                  <TableHead>Text</TableHead>
                  <TableHead className="w-[120px]">Source</TableHead>
                  <TableHead className="w-[120px]">Date</TableHead>
                  <TableHead className="w-[100px]">Message</TableHead>
                  <TableHead className="w-[80px]">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {embeddings.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center text-muted-foreground">
                      No embeddings found
                    </TableCell>
                  </TableRow>
                ) : (
                  embeddings.map((embedding) => (
                    <TableRow key={embedding.id}>
                      <TableCell className="text-sm font-mono">
                        {embedding.id}
                      </TableCell>
                      <TableCell className="max-w-md">
                        <Tooltip content={embedding.text}>
                          <div className="text-sm">
                            {truncateText(embedding.text, TRUNCATE_LENGTH)}
                          </div>
                        </Tooltip>
                      </TableCell>
                      <TableCell>
                        {embedding.source ? (
                          <Badge variant="secondary">{embedding.source}</Badge>
                        ) : (
                          <span className="text-muted-foreground">-</span>
                        )}
                      </TableCell>
                      <TableCell className="text-sm">
                        {new Date(embedding.created_at).toLocaleDateString()}
                      </TableCell>
                      <TableCell>
                        {embedding.message_id ? (
                          <Badge variant="outline">#{embedding.message_id}</Badge>
                        ) : (
                          <span className="text-muted-foreground">Chunk</span>
                        )}
                      </TableCell>
                      <TableCell>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setSelectedEmbedding(embedding.id)}
                        >
                          <Eye className="h-4 w-4" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="mt-4 flex items-center justify-between">
              <div className="text-sm text-muted-foreground">
                Page {page} of {totalPages} ({total} total)
              </div>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage(Math.max(1, page - 1))}
                  disabled={page === 1}
                >
                  <ChevronLeft className="h-4 w-4" />
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage(Math.min(totalPages, page + 1))}
                  disabled={page === totalPages}
                >
                  Next
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Detail Dialog */}
      <Dialog open={selectedEmbedding !== null} onOpenChange={(open) => !open && setSelectedEmbedding(null)}>
        <DialogContent className="max-w-3xl max-h-[80vh] overflow-auto">
          <DialogHeader>
            <DialogTitle>Embedding #{selectedEmbedding}</DialogTitle>
            <DialogDescription>Full embedding details</DialogDescription>
          </DialogHeader>
          {selectedEmbeddingData && (
            <div className="space-y-4">
              <div>
                <h3 className="font-semibold mb-2">Text Content</h3>
                <div className="p-3 bg-muted rounded-md text-sm whitespace-pre-wrap">
                  {selectedEmbeddingData.text}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <h3 className="font-semibold mb-2">Source</h3>
                  <p className="text-sm">
                    {selectedEmbeddingData.source || <span className="text-muted-foreground">Not specified</span>}
                  </p>
                </div>
                <div>
                  <h3 className="font-semibold mb-2">Created At</h3>
                  <p className="text-sm">
                    {new Date(selectedEmbeddingData.created_at).toLocaleString()}
                  </p>
                </div>
                {selectedEmbeddingData.message_id && (
                  <div>
                    <h3 className="font-semibold mb-2">Message ID</h3>
                    <p className="text-sm">#{selectedEmbeddingData.message_id}</p>
                  </div>
                )}
              </div>

              {selectedEmbeddingData.message && (
                <div>
                  <h3 className="font-semibold mb-2">Associated Message</h3>
                  <div className="p-3 bg-muted rounded-md text-sm space-y-2">
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <p className="text-xs text-muted-foreground mb-1">From (Sender):</p>
                        <p className="font-medium">{selectedEmbeddingData.message.sender}</p>
                      </div>
                      <div>
                        <p className="text-xs text-muted-foreground mb-1">To:</p>
                        {selectedEmbeddingData.message.recipient ? (
                          <p className="font-medium">{selectedEmbeddingData.message.recipient}</p>
                        ) : selectedEmbeddingData.message.recipients && selectedEmbeddingData.message.recipients.length > 0 ? (
                          <div>
                            <p className="font-medium text-xs mb-1">Group ({selectedEmbeddingData.message.recipients.length} participants):</p>
                            <div className="flex flex-wrap gap-1">
                              {selectedEmbeddingData.message.recipients.map((r, idx) => (
                                <span key={idx} className="text-xs bg-background px-1.5 py-0.5 rounded">{r}</span>
                              ))}
                            </div>
                          </div>
                        ) : (
                          <p className="text-muted-foreground text-xs">Unknown</p>
                        )}
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-2 pt-2 border-t">
                      <div>
                        <p className="text-xs text-muted-foreground mb-1">Source:</p>
                        <p>{selectedEmbeddingData.message.source}</p>
                      </div>
                      <div>
                        <p className="text-xs text-muted-foreground mb-1">Timestamp:</p>
                        <p>{new Date(selectedEmbeddingData.message.timestamp).toLocaleString()}</p>
                      </div>
                    </div>
                    {selectedEmbeddingData.message.conversation_id && (
                      <div className="pt-2 border-t">
                        <p className="text-xs text-muted-foreground mb-1">Conversation ID:</p>
                        <p className="text-xs font-mono">{selectedEmbeddingData.message.conversation_id}</p>
                      </div>
                    )}
                    <div className="mt-2 pt-2 border-t">
                      <p className="text-xs text-muted-foreground mb-1">Content:</p>
                      <p className="mt-1 whitespace-pre-wrap">{selectedEmbeddingData.message.content}</p>
                    </div>
                  </div>
                </div>
              )}

              {selectedEmbeddingData.metadata && (
                <div>
                  <h3 className="font-semibold mb-2">Metadata</h3>
                  <pre className="p-3 bg-muted rounded-md text-xs overflow-auto">
                    {JSON.stringify(selectedEmbeddingData.metadata, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
