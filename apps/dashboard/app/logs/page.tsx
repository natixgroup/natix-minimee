"use client";

import { useState, useMemo } from "react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { useLogs } from "@/lib/hooks/useLogs";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Loader2, AlertCircle, Info, CheckCircle, AlertTriangle, Filter, X, ChevronDown, ChevronUp } from "lucide-react";
import { Log } from "@/lib/api";
import { 
  Tooltip, 
  TooltipContent, 
  TooltipProvider, 
  TooltipTrigger 
} from "@/components/ui/tooltip";

const TIME_FILTERS = [
  { label: "Last Hour", value: "last_hour" },
  { label: "Today", value: "today" },
  { label: "Yesterday", value: "yesterday" },
  { label: "Last 7 Days", value: "last_7_days" },
  { label: "Last 30 Days", value: "last_30_days" },
  { label: "All Time", value: "all" },
] as const;

type TimeFilter = typeof TIME_FILTERS[number]["value"];

const LOG_LEVELS = [
  { label: "All", value: "all" },
  { label: "ERROR", value: "ERROR" },
  { label: "WARNING", value: "WARNING" },
  { label: "INFO", value: "INFO" },
  { label: "DEBUG", value: "DEBUG" },
] as const;

const SERVICES = [
  { label: "All Services", value: "all" },
  { label: "API", value: "api" },
  { label: "Frontend", value: "frontend" },
  { label: "Minimee", value: "minimee" },
  { label: "Approval Flow", value: "approval_flow" },
  { label: "Ingestion", value: "ingestion" },
  { label: "Bridge Client", value: "bridge_client" },
] as const;

export default function LogsPage() {
  const [timeFilter, setTimeFilter] = useState<TimeFilter>("all");
  const [selectedLevel, setSelectedLevel] = useState<string>("all");
  const [selectedService, setSelectedService] = useState<string>("all");
  const [page, setPage] = useState(0);
  const [filtersExpanded, setFiltersExpanded] = useState(true);
  const limit = 50;

  // Calculate date range from time filter
  const dateRange = useMemo(() => {
    const now = new Date();
    let start_date: Date | null = null;
    let end_date: Date | null = null;

    switch (timeFilter) {
      case "last_hour":
        start_date = new Date(now.getTime() - 60 * 60 * 1000);
        break;
      case "today":
        const todayStart = new Date(now);
        todayStart.setHours(0, 0, 0, 0);
        start_date = todayStart;
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
        end_date = null;
        break;
    }

    return {
      start_date: start_date ? start_date.toISOString() : undefined,
      end_date: end_date ? end_date.toISOString() : undefined,
    };
  }, [timeFilter]);

  const { data, isLoading, isError } = useLogs({
    level: selectedLevel !== "all" ? selectedLevel : undefined,
    service: selectedService !== "all" ? selectedService : undefined,
    start_date: dateRange.start_date,
    end_date: dateRange.end_date,
    limit,
    offset: page * limit,
  });

  const logs: Log[] = data?.logs || [];
  const total = data?.total || 0;
  const totalPages = data?.total_pages || 0;

  const getLevelIcon = (level: string) => {
    switch (level) {
      case "ERROR":
        return <AlertCircle className="h-4 w-4 text-destructive" />;
      case "WARNING":
        return <AlertTriangle className="h-4 w-4 text-yellow-500" />;
      case "INFO":
        return <Info className="h-4 w-4 text-blue-500" />;
      case "DEBUG":
        return <Info className="h-4 w-4 text-muted-foreground" />;
      default:
        return <CheckCircle className="h-4 w-4 text-muted-foreground" />;
    }
  };

  const hasActiveFilters = timeFilter !== "all" || selectedLevel !== "all" || selectedService !== "all";

  const clearFilters = () => {
    setTimeFilter("all");
    setSelectedLevel("all");
    setSelectedService("all");
    setPage(0);
  };

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold">Logs</h1>
          <p className="text-muted-foreground">
            System and application logs with detailed metadata
          </p>
        </div>

        {/* Filters Card */}
        <Card>
          <CardContent className="pt-6">
            <div className="space-y-4">
              {/* Filter Header */}
              <div 
                className="flex items-center justify-between cursor-pointer"
                onClick={() => setFiltersExpanded(!filtersExpanded)}
              >
                <div className="flex items-center gap-2">
                  <Filter className="h-4 w-4" />
                  <span className="font-medium">Filters</span>
                  {hasActiveFilters && (
                    <Badge variant="secondary" className="ml-2">
                      Active
                    </Badge>
                  )}
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={(e) => {
                    e.stopPropagation();
                    setFiltersExpanded(!filtersExpanded);
                  }}
                >
                  {filtersExpanded ? (
                    <ChevronUp className="h-4 w-4" />
                  ) : (
                    <ChevronDown className="h-4 w-4" />
                  )}
                </Button>
              </div>

              {/* Filters Content */}
              <div
                className={`overflow-hidden transition-all duration-300 ${
                  filtersExpanded ? "max-h-[500px] opacity-100" : "max-h-0 opacity-0"
                }`}
                onClick={(e) => e.stopPropagation()}
              >
                <div className="space-y-4 pt-2">
                  {/* Time Filter */}
                  <div>
                    <label className="text-sm font-medium mb-2 block">Time Range</label>
                    <div className="flex flex-wrap gap-2">
                      {TIME_FILTERS.map((filter) => (
                        <Button
                          key={filter.value}
                          variant={timeFilter === filter.value ? "default" : "outline"}
                          size="sm"
                          onClick={() => {
                            setTimeFilter(filter.value);
                            setPage(0);
                          }}
                        >
                          {filter.label}
                        </Button>
                      ))}
                    </div>
                  </div>

                  {/* Level Filter */}
                  <div>
                    <label className="text-sm font-medium mb-2 block">Level</label>
                    <div className="flex flex-wrap gap-2">
                      {LOG_LEVELS.map((level) => (
                        <Button
                          key={level.value}
                          variant={selectedLevel === level.value ? "default" : "outline"}
                          size="sm"
                          onClick={() => {
                            setSelectedLevel(level.value);
                            setPage(0);
                          }}
                        >
                          {level.label}
                        </Button>
                      ))}
                    </div>
                  </div>

                  {/* Service Filter */}
                  <div>
                    <label className="text-sm font-medium mb-2 block">
                      Service
                      {hasActiveFilters && (
                        <Button
                          variant="ghost"
                          size="sm"
                          className="ml-2 h-6 px-2"
                          onClick={clearFilters}
                        >
                          <X className="h-3 w-3 mr-1" />
                          Clear All
                        </Button>
                      )}
                    </label>
                    <div className="flex flex-wrap gap-2">
                      {SERVICES.map((service) => (
                        <Button
                          key={service.value}
                          variant={selectedService === service.value ? "default" : "outline"}
                          size="sm"
                          onClick={() => {
                            setSelectedService(service.value);
                            setPage(0);
                          }}
                        >
                          {service.label}
                        </Button>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Total count */}
        <div className="text-sm text-muted-foreground">
          {total} total logs
        </div>

        {/* Logs Table */}
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : isError ? (
          <div className="flex items-center justify-center py-12 text-destructive">
            <AlertCircle className="h-5 w-5 mr-2" />
            Failed to load logs
          </div>
        ) : logs.length === 0 ? (
          <div className="text-center py-12 text-muted-foreground">
            No logs found
          </div>
        ) : (
          <>
            <div className="border rounded-lg overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-12">Level</TableHead>
                    <TableHead className="w-40">Timestamp</TableHead>
                    <TableHead>Service</TableHead>
                    <TableHead>Message</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {logs.map((log) => {
                    return (
                      <TableRow key={log.id} className="hover:bg-muted/50">
                        <TableCell>
                          {getLevelIcon(log.level)}
                        </TableCell>
                        <TableCell className="text-sm font-mono text-muted-foreground">
                          {new Date(log.timestamp).toLocaleString("fr-FR", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit" })}
                        </TableCell>
                        <TableCell>
                          {log.service && (
                            <Badge variant="secondary" className="text-xs">
                              {log.service}
                            </Badge>
                          )}
                        </TableCell>
                        <TableCell className="max-w-2xl relative">
                          <TooltipProvider>
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <div className="cursor-help truncate">
                                  {log.message}
                                </div>
                              </TooltipTrigger>
                              <TooltipContent 
                                  side="right" 
                                  className="max-w-lg p-4 bg-popover border shadow-lg"
                                >
                                  <div className="space-y-2 text-sm">
                                    <div className="font-semibold mb-2 border-b pb-2">
                                      {log.message}
                                    </div>
                                    
                                    {/* Basic info */}
                                    <div className="grid grid-cols-[100px_1fr] gap-2 text-xs">
                                      <span className="text-muted-foreground font-medium">Level:</span>
                                      <span className="font-medium">{log.level}</span>
                                      
                                      <span className="text-muted-foreground font-medium">Service:</span>
                                      <span>{log.service || "N/A"}</span>
                                      
                                      <span className="text-muted-foreground font-medium">Timestamp:</span>
                                      <span>{new Date(log.timestamp).toLocaleString("fr-FR", { 
                                        year: "numeric",
                                        month: "long", 
                                        day: "numeric",
                                        hour: "2-digit", 
                                        minute: "2-digit", 
                                        second: "2-digit" 
                                      })}</span>
                                      
                                      <span className="text-muted-foreground font-medium">ID:</span>
                                      <span className="font-mono text-xs">{log.id}</span>
                                    </div>
                                    
                                    {/* Metadata */}
                                    {log.metadata && Object.keys(log.metadata).length > 0 && (
                                      <>
                                        <div className="border-t pt-2 mt-2">
                                          <div className="text-xs font-semibold mb-2 text-muted-foreground">
                                            Metadata:
                                          </div>
                                          <div className="space-y-2 max-h-96 overflow-y-auto">
                                            {Object.entries(log.metadata).map(([key, value]) => {
                                              const stringValue = typeof value === "object" 
                                                ? JSON.stringify(value, null, 2)
                                                : String(value);
                                              const isLongText = stringValue.length > 200;
                                              const displayValue = isLongText && typeof value !== "object"
                                                ? stringValue.substring(0, 300) + "..."
                                                : stringValue;
                                              
                                              return (
                                                <div key={key} className="border-b pb-2 last:border-0">
                                                  <div className="text-muted-foreground font-medium text-xs mb-1">
                                                    {key}:
                                                  </div>
                                                  <div className="text-xs break-words">
                                                    {typeof value === "object" ? (
                                                      <pre className="whitespace-pre-wrap text-xs bg-muted p-2 rounded max-h-40 overflow-y-auto">
                                                        {displayValue}
                                                      </pre>
                                                    ) : (
                                                      <div className="whitespace-pre-wrap">
                                                        {displayValue}
                                                      </div>
                                                    )}
                                                  </div>
                                                </div>
                                              );
                                            })}
                                          </div>
                                        </div>
                                      </>
                                    )}
                                  </div>
                                </TooltipContent>
                            </Tooltip>
                          </TooltipProvider>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between">
                <Button
                  variant="outline"
                  onClick={() => setPage(Math.max(0, page - 1))}
                  disabled={page === 0}
                >
                  Previous
                </Button>
                <span className="text-sm text-muted-foreground">
                  Page {page + 1} of {totalPages}
                </span>
                <Button
                  variant="outline"
                  onClick={() => setPage(Math.min(totalPages - 1, page + 1))}
                  disabled={page >= totalPages - 1}
                >
                  Next
                </Button>
              </div>
            )}
          </>
        )}
      </div>
    </DashboardLayout>
  );
}
