"use client";

import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useState, useMemo, useEffect, useRef } from "react";
import { toast } from "sonner";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { useLogs } from "@/lib/hooks/useLogs";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";                                                          
import { Loader2, AlertCircle, Info, CheckCircle, AlertTriangle, Filter, X, ChevronDown, ChevronUp, Trash2 } from "lucide-react";                                       
import { Log } from "@/lib/api";
import { api } from "@/lib/api";
// Simple Tooltip component for logs
function LogTooltip({ log, children }: { log: Log; children: React.ReactNode }) {                                                                               
  const [show, setShow] = useState(false);
  const [position, setPosition] = useState<{ top: number; left: number } | null>(null);                                                                         
  const triggerRef = useRef<HTMLDivElement>(null);
  
  useEffect(() => {
    if (!show || !triggerRef.current) return;
    
    const trigger = triggerRef.current;
    const rect = trigger.getBoundingClientRect();
    const tooltipWidth = 500;
    const tooltipHeight = 300; // Estimation
    
    // Positionner à droite, centré verticalement
    let left = rect.right + 8;
    let top = rect.top + rect.height / 2 - tooltipHeight / 2;
    
    // Ajuster si dépasse la viewport
    if (left + tooltipWidth > window.innerWidth - 8) {
      // Mettre à gauche si pas de place à droite
      left = rect.left - tooltipWidth - 8;
    }
    if (top < 8) top = 8;
    if (top + tooltipHeight > window.innerHeight - 8) {
      top = window.innerHeight - tooltipHeight - 8;
    }
    
    setPosition({ top, left });
  }, [show]);
  
  return (
    <>
      <div
        ref={triggerRef}
        className="inline-block w-full"
        onMouseEnter={() => setShow(true)}
        onMouseLeave={() => setShow(false)}
      >
        {children}
      </div>
      {show && position && (
        <div 
          className="fixed z-[9999] w-[500px] max-w-[80vw] p-4 bg-popover text-popover-foreground text-sm rounded-md border shadow-lg"                          
          style={{ top: `${position.top}px`, left: `${position.left}px` }}
          onMouseEnter={() => setShow(true)}
          onMouseLeave={() => setShow(false)}
        >          <div className="space-y-2 text-sm">
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
                    {(() => {
                      // First, check if options exist and render them prominently
                      const options = log.metadata?.options;
                      const hasOptions = Array.isArray(options) && options.length > 0;
                      
                      // Get all entries
                      const entries = Object.entries(log.metadata || {});
                      
                      // Separate options from other entries
                      const otherEntries = entries.filter(([key]) => key !== "options");
                      
                      return (
                        <>
                          {hasOptions && (
                            <div className="border-b pb-3 mb-3 last:border-0">
                              <div className="text-muted-foreground font-medium text-xs mb-2">
                                Options générées ({options.length}):
                              </div>
                              <div className="space-y-2">
                                {options.map((option, idx) => (
                                  <div key={idx} className="bg-primary/10 border border-primary/20 p-2 rounded text-xs">
                                    <span className="font-medium text-primary">Option {idx + 1}:</span>
                                    <div className="mt-1 whitespace-pre-wrap text-foreground">
                                      {typeof option === "string" ? option : JSON.stringify(option, null, 2)}
                                    </div>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                          {otherEntries.map(([key, value]) => {
                      // Special handling for options
                      if (key === "options" && Array.isArray(value)) {
                        return (
                          <div key={key} className="border-b pb-2 last:border-0">
                            <div className="text-muted-foreground font-medium text-xs mb-2">
                              {key} ({value.length} options):
                            </div>
                            <div className="space-y-2">
                              {value.map((option, idx) => (
                                <div key={idx} className="bg-muted p-2 rounded text-xs">
                                  <span className="font-medium text-muted-foreground">Option {idx + 1}:</span>
                                  <div className="mt-1 whitespace-pre-wrap">{option}</div>
                                </div>
                              ))}
                            </div>
                          </div>
                        );
                      }
                      
                      // Special handling for option_1, option_2, option_3
                      if (key.startsWith("option_") && typeof value === "string") {
                        const optionNum = key.replace("option_", "");
                        return (
                          <div key={key} className="border-b pb-2 last:border-0">
                            <div className="text-muted-foreground font-medium text-xs mb-1">
                              Option {optionNum}:
                            </div>
                            <div className="bg-muted p-2 rounded text-xs whitespace-pre-wrap">
                              {value}
                            </div>
                          </div>
                        );
                      }
                      
                      // Special handling for request_body (POST request details)
                      if (key === "request_body" && typeof value === "object") {
                        return (
                          <div key={key} className="border-b pb-2 last:border-0">
                            <div className="text-muted-foreground font-medium text-xs mb-2">
                              Request Body:
                            </div>
                            <div className="bg-muted p-2 rounded text-xs">
                              <pre className="whitespace-pre-wrap max-h-40 overflow-y-auto">
                                {JSON.stringify(value, null, 2)}
                              </pre>
                            </div>
                          </div>
                        );
                      }
                      
                      // Special handling for content (truncate if too long)
                      if (key === "content" && typeof value === "string" && value.length > 200) {
                        return (
                          <div key={key} className="border-b pb-2 last:border-0">
                            <div className="text-muted-foreground font-medium text-xs mb-1">
                              {key}:
                            </div>
                            <div className="text-xs break-words whitespace-pre-wrap">
                              {value.substring(0, 300)}...
                              <span className="text-muted-foreground"> ({value.length} chars)</span>
                            </div>
                          </div>
                        );
                      }
                      
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
                        </>
                      );
                    })()}
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </>
  );
}

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
  { label: "ERROR", value: "ERROR" },
  { label: "WARNING", value: "WARNING" },
  { label: "INFO", value: "INFO" },
  { label: "DEBUG", value: "DEBUG" },
] as const;

const SERVICES = [
  { label: "API", value: "api" },
  { label: "Frontend", value: "frontend" },
  { label: "Minimee", value: "minimee" },
  { label: "Approval Flow", value: "approval_flow" },
  { label: "Ingestion", value: "ingestion" },
  { label: "Bridge Client", value: "bridge_client" },
] as const;

export default function LogsPage() {
  const [timeFilter, setTimeFilter] = useState<TimeFilter>("all");
  const [selectedLevels, setSelectedLevels] = useState<Set<string>>(new Set());
  const [selectedServices, setSelectedServices] = useState<Set<string>>(new Set());
  const [page, setPage] = useState(0);
  const [filtersExpanded, setFiltersExpanded] = useState(true);
  const [showPurgeConfirm, setShowPurgeConfirm] = useState(false);
  const [isPurging, setIsPurging] = useState(false);
  // Hide frontend HTTP requests by default
  const [hideFrontendRequests, setHideFrontendRequests] = useState(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem("logs-hide-frontend");
      return saved !== null ? saved === "true" : true; // Default to true
    }
    return true;
  });
  const limit = 50;

  // Save hideFrontendRequests preference to localStorage
  useEffect(() => {
    if (typeof window !== "undefined") {
      localStorage.setItem("logs-hide-frontend", String(hideFrontendRequests));
    }
  }, [hideFrontendRequests]);

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

  // Toggle level selection
  const toggleLevel = (level: string) => {
    setSelectedLevels(prev => {
      const newSet = new Set(prev);
      if (newSet.has(level)) {
        newSet.delete(level);
      } else {
        newSet.add(level);
      }
      return newSet;
    });
    setPage(0);
  };

  // Toggle service selection
  const toggleService = (service: string) => {
    setSelectedServices(prev => {
      const newSet = new Set(prev);
      if (newSet.has(service)) {
        newSet.delete(service);
      } else {
        newSet.add(service);
      }
      return newSet;
    });
    setPage(0);
  };

  // Select all levels
  const selectAllLevels = () => {
    setSelectedLevels(new Set(LOG_LEVELS.map(l => l.value)));
    setPage(0);
  };

  // Deselect all levels
  const deselectAllLevels = () => {
    setSelectedLevels(new Set());
    setPage(0);
  };

  // Select all services
  const selectAllServices = () => {
    setSelectedServices(new Set(SERVICES.map(s => s.value)));
    setPage(0);
  };

  // Deselect all services
  const deselectAllServices = () => {
    setSelectedServices(new Set());
    setPage(0);
  };

  // Prepare API params - convert sets to comma-separated strings
  const levelParam = selectedLevels.size > 0 ? Array.from(selectedLevels).join(",") : undefined;
  const serviceParam = selectedServices.size > 0 ? Array.from(selectedServices).join(",") : undefined;

  const { data, isLoading, isError, refetch } = useLogs({
    level: levelParam,
    service: serviceParam,
    start_date: dateRange.start_date,
    end_date: dateRange.end_date,
    limit,
    offset: page * limit,
  });

  const allLogs: Log[] = data?.logs || [];
  // Filter out frontend requests if option is enabled
  const logs = hideFrontendRequests
    ? allLogs.filter(log => log.service !== "frontend")
    : allLogs;
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

  const hasActiveFilters = timeFilter !== "all" || selectedLevels.size > 0 || selectedServices.size > 0;                                                        

  const clearFilters = () => {
    setTimeFilter("all");
    setSelectedLevels(new Set());
    setSelectedServices(new Set());
    setPage(0);
  };

  

  // Handler for purging logs
  const handlePurge = async () => {
    setIsPurging(true);
    try {
      const result = await api.deleteLogs({
        level: levelParam,
        service: serviceParam,
        start_date: dateRange.start_date,
        end_date: dateRange.end_date,
      });
      toast.success(result.message || `${result.deleted} log(s) supprimé(s)`);
      setShowPurgeConfirm(false);
      setPage(0);
      // Refetch logs
      await refetch();
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Erreur lors de la suppression"
      );
    } finally {
      setIsPurging(false);
    }
  };

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div className="flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold">Logs</h1>
              <p className="text-muted-foreground">
                System and application logs with detailed metadata
              </p>
            </div>
          </div>
          <div className="flex items-center gap-4 flex-wrap">
            <div className="flex items-center gap-2">
              <Label htmlFor="hide-frontend-toggle" className="text-sm cursor-pointer whitespace-nowrap">
                Cacher les requêtes HTTP du frontend
              </Label>
              <Switch
                id="hide-frontend-toggle"
                checked={hideFrontendRequests}
                onCheckedChange={setHideFrontendRequests}
              />
            </div>
            <Button
              variant="destructive"
              size="sm"
              onClick={() => setShowPurgeConfirm(true)}
              disabled={isPurging || total === 0}
              className="flex items-center gap-2 whitespace-nowrap"
            >
              <Trash2 className="h-4 w-4" />
              Purger les logs filtrés
            </Button>
          </div>
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
                    <div className="flex items-center justify-between mb-2">
                      <label className="text-sm font-medium">Level</label>
                      <div className="flex gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-6 px-2 text-xs"
                          onClick={selectAllLevels}
                        >
                          All
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-6 px-2 text-xs"
                          onClick={deselectAllLevels}
                        >
                          None
                        </Button>
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {LOG_LEVELS.map((level) => (
                        <Button
                          key={level.value}
                          variant={selectedLevels.has(level.value) ? "default" : "outline"}                                                                       
                          size="sm"
                          onClick={() => toggleLevel(level.value)}
                        >
                          {level.label}
                        </Button>
                      ))}
                    </div>
                  </div>

                  {/* Service Filter */}
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <label className="text-sm font-medium">Service</label>
                      <div className="flex gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-6 px-2 text-xs"
                          onClick={selectAllServices}
                        >
                          All
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-6 px-2 text-xs"
                          onClick={deselectAllServices}
                        >
                          None
                        </Button>
                        {hasActiveFilters && (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-6 px-2 text-xs"
                            onClick={clearFilters}
                          >
                            <X className="h-3 w-3 mr-1" />
                            Clear All
                          </Button>
                        )}
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {SERVICES.map((service) => (
                        <Button
                          key={service.value}
                          variant={selectedServices.has(service.value) ? "default" : "outline"}                                                                   
                          size="sm"
                          onClick={() => toggleService(service.value)}
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
                        <TableCell className="max-w-2xl">
                          <LogTooltip log={log}>
                            <div className="cursor-help truncate">
                              {log.message}
                            </div>
                          </LogTooltip>
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
          {/* Purge confirmation dialog */}
      <Dialog open={showPurgeConfirm} onOpenChange={setShowPurgeConfirm}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Confirmer la suppression</DialogTitle>
            <DialogDescription>
              Vous êtes sur le point de supprimer <strong>{total} log(s)</strong> correspondant aux filtres actuels.
              <br />
              <br />
              Cette action est <strong className="text-destructive">irréversible</strong>.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="flex gap-2 mt-4">
            <Button
              variant="outline"
              onClick={() => setShowPurgeConfirm(false)}
              disabled={isPurging}
            >
              Annuler
            </Button>
            <Button
              variant="destructive"
              onClick={handlePurge}
              disabled={isPurging}
              className="flex items-center gap-2"
            >
              {isPurging ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Suppression...
                </>
              ) : (
                <>
                  <Trash2 className="h-4 w-4" />
                  Supprimer {total} log(s)
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
</DashboardLayout>
  );
}
