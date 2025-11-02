"use client";

import { useState } from "react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { useLogs } from "@/lib/hooks/useLogs";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Loader2, AlertCircle, Info, CheckCircle, AlertTriangle } from "lucide-react";
import { Log } from "@/lib/api";

import { 
  Tooltip, 
  TooltipContent, 
  TooltipProvider, 
  TooltipTrigger 
} from "@/components/ui/tooltip";

export default function LogsPage() {
  const [level, setLevel] = useState<string>("");
  const [service, setService] = useState<string>("");
  const [page, setPage] = useState(0);
  const limit = 50;

  const { data, isLoading, isError } = useLogs({
    level: level || undefined,
    service: service || undefined,
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

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold">Logs</h1>
          <p className="text-muted-foreground">
            System and application logs with detailed metadata
          </p>
        </div>

        {/* Filters */}
        <div className="flex gap-4 items-center">
          <Select value={level} onValueChange={setLevel}>
            <SelectTrigger className="w-40">
              <SelectValue placeholder="All Levels" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="">All Levels</SelectItem>
              <SelectItem value="ERROR">ERROR</SelectItem>
              <SelectItem value="WARNING">WARNING</SelectItem>
              <SelectItem value="INFO">INFO</SelectItem>
              <SelectItem value="DEBUG">DEBUG</SelectItem>
            </SelectContent>
          </Select>

          <Select value={service} onValueChange={setService}>
            <SelectTrigger className="w-48">
              <SelectValue placeholder="All Services" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="">All Services</SelectItem>
              <SelectItem value="api">API</SelectItem>
              <SelectItem value="frontend">Frontend</SelectItem>
              <SelectItem value="minimee">Minimee</SelectItem>
              <SelectItem value="approval_flow">Approval Flow</SelectItem>
              <SelectItem value="ingestion">Ingestion</SelectItem>
              <SelectItem value="bridge_client">Bridge Client</SelectItem>
            </SelectContent>
          </Select>

          <div className="ml-auto text-sm text-muted-foreground">
            {total} total logs
          </div>
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
                    const hasDetails = log.metadata && Object.keys(log.metadata).length > 0;
                    
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
                              {hasDetails && (
                                <TooltipContent 
                                  side="right" 
                                  className="max-w-lg p-4 bg-popover border shadow-lg"
                                >
                                  <div className="space-y-2 text-sm">
                                    <div className="font-semibold mb-2 border-b pb-2">
                                      {log.message}
                                    </div>
                                    <div className="space-y-1 max-h-96 overflow-y-auto">
                                      {log.metadata && Object.entries(log.metadata).map(([key, value]) => (
                                        <div key={key} className="grid grid-cols-[120px_1fr] gap-2">
                                          <span className="text-muted-foreground font-medium text-xs">
                                            {key}:
                                          </span>
                                          <span className="text-xs break-words">
                                            {typeof value === "object" ? (
                                              <pre className="whitespace-pre-wrap text-xs bg-muted p-2 rounded">
                                                {JSON.stringify(value, null, 2)}
                                              </pre>
                                            ) : (
                                              String(value)
                                            )}
                                          </span>
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                </TooltipContent>
                              )}
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
