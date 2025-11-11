"use client";

import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Trash2, AlertTriangle, CheckCircle2, XCircle, Clock, MessageSquare, Sparkles } from "lucide-react";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

interface IngestionJob {
  id: number;
  source: string | null;
  status: string;
  conversation_id: string | null;
  created_at: string;
  updated_at: string;
  error: string | null;
  progress: Record<string, any> | null;
  stats: Record<string, any>;
}

export function ImportHistory() {
  const [activeTab, setActiveTab] = useState<string>("whatsapp");
  const [deleteJobId, setDeleteJobId] = useState<number | null>(null);
  const [deleteAllSource, setDeleteAllSource] = useState<string | null>(null);
  const queryClient = useQueryClient();

  // Fetch jobs for each source
  const { data: whatsappJobs, isLoading: isLoadingWhatsApp } = useQuery({
    queryKey: ["ingestion-jobs", "whatsapp"],
    queryFn: () => api.getIngestionJobs("whatsapp", 1, 1000, 0),
  });

  const { data: gmailJobs, isLoading: isLoadingGmail } = useQuery({
    queryKey: ["ingestion-jobs", "gmail"],
    queryFn: () => api.getIngestionJobs("gmail", 1, 1000, 0),
  });

  const formatDate = (dateString: string) => {
    try {
      const date = new Date(dateString);
      return date.toLocaleString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit"
      });
    } catch {
      return dateString;
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "completed":
        return <Badge variant="default" className="bg-green-500"><CheckCircle2 className="h-3 w-3 mr-1" />Completed</Badge>;
      case "failed":
        return <Badge variant="destructive"><XCircle className="h-3 w-3 mr-1" />Failed</Badge>;
      case "cancelled":
        return <Badge variant="secondary"><XCircle className="h-3 w-3 mr-1" />Cancelled</Badge>;
      case "running":
        return <Badge variant="secondary" className="bg-blue-500"><Clock className="h-3 w-3 mr-1 animate-spin" />Running</Badge>;
      default:
        return <Badge variant="outline">{status}</Badge>;
    }
  };

  const handleDeleteJob = async (jobId: number) => {
    try {
      const result = await api.deleteIngestionJob(jobId, 1);
      toast.success(result.message);
      setDeleteJobId(null);
      // Invalidate queries to refresh
      queryClient.invalidateQueries({ queryKey: ["ingestion-jobs"] });
      queryClient.invalidateQueries({ queryKey: ["whatsapp-import-history"] });
      queryClient.invalidateQueries({ queryKey: ["embeddings"] });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to delete job");
    }
  };

  const handleDeleteAll = async (source: string) => {
    try {
      const result = await api.deleteAllIngestionJobs(source, 1);
      toast.success(result.message);
      setDeleteAllSource(null);
      // Invalidate queries to refresh
      queryClient.invalidateQueries({ queryKey: ["ingestion-jobs"] });
      queryClient.invalidateQueries({ queryKey: ["whatsapp-import-history"] });
      queryClient.invalidateQueries({ queryKey: ["embeddings"] });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to delete all jobs");
    }
  };

  const whatsappItems: IngestionJob[] = whatsappJobs?.items || [];
  const gmailItems: IngestionJob[] = gmailJobs?.items || [];

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle>Import History</CardTitle>
          <CardDescription>View and manage import history by source</CardDescription>
        </CardHeader>
        <CardContent>
          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList className="grid w-full grid-cols-2">
              <TabsTrigger value="whatsapp">
                WhatsApp ({whatsappItems.length})
              </TabsTrigger>
              <TabsTrigger value="gmail">
                Gmail ({gmailItems.length})
              </TabsTrigger>
            </TabsList>

            <TabsContent value="whatsapp" className="space-y-4 mt-4">
              <div className="flex items-center justify-between">
                <div className="text-sm text-muted-foreground">
                  {whatsappItems.length} import{whatsappItems.length !== 1 ? "s" : ""}
                </div>
                {whatsappItems.length > 0 && (
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={() => setDeleteAllSource("whatsapp")}
                  >
                    <Trash2 className="h-4 w-4 mr-2" />
                    Delete All
                  </Button>
                )}
              </div>

              {isLoadingWhatsApp ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                </div>
              ) : whatsappItems.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  No WhatsApp imports yet
                </div>
              ) : (
                <div className="border rounded-lg overflow-hidden">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Date</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Conversation ID</TableHead>
                        <TableHead className="text-right">
                          <MessageSquare className="h-4 w-4 inline mr-1" />
                          Messages
                        </TableHead>
                        <TableHead className="text-right">
                          <Sparkles className="h-4 w-4 inline mr-1" />
                          Embeddings
                        </TableHead>
                        <TableHead className="text-right">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {whatsappItems.map((job) => (
                        <TableRow key={job.id}>
                          <TableCell className="text-sm">
                            {formatDate(job.created_at)}
                          </TableCell>
                          <TableCell>
                            {getStatusBadge(job.status)}
                          </TableCell>
                          <TableCell>
                            <code className="text-xs font-mono">
                              {job.conversation_id ? (
                                job.conversation_id.length > 30
                                  ? job.conversation_id.substring(0, 15) + "..." + job.conversation_id.substring(job.conversation_id.length - 10)
                                  : job.conversation_id
                              ) : "-"}
                            </code>
                          </TableCell>
                          <TableCell className="text-right font-medium">
                            {job.stats?.messages_count || job.progress?.stats?.messages_created || 0}
                          </TableCell>
                          <TableCell className="text-right font-medium">
                            {job.stats?.embeddings_count || job.progress?.stats?.embeddings_created || 0}
                          </TableCell>
                          <TableCell className="text-right">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => setDeleteJobId(job.id)}
                              className="text-red-500 hover:text-red-600 hover:bg-red-50"
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </TabsContent>

            <TabsContent value="gmail" className="space-y-4 mt-4">
              <div className="flex items-center justify-between">
                <div className="text-sm text-muted-foreground">
                  {gmailItems.length} import{gmailItems.length !== 1 ? "s" : ""}
                </div>
                {gmailItems.length > 0 && (
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={() => setDeleteAllSource("gmail")}
                  >
                    <Trash2 className="h-4 w-4 mr-2" />
                    Delete All
                  </Button>
                )}
              </div>

              {isLoadingGmail ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                </div>
              ) : gmailItems.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  No Gmail imports yet
                </div>
              ) : (
                <div className="border rounded-lg overflow-hidden">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Date</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Days</TableHead>
                        <TableHead className="text-right">
                          <MessageSquare className="h-4 w-4 inline mr-1" />
                          Threads
                        </TableHead>
                        <TableHead className="text-right">
                          <Sparkles className="h-4 w-4 inline mr-1" />
                          Embeddings
                        </TableHead>
                        <TableHead className="text-right">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {gmailItems.map((job) => (
                        <TableRow key={job.id}>
                          <TableCell className="text-sm">
                            {formatDate(job.created_at)}
                          </TableCell>
                          <TableCell>
                            {getStatusBadge(job.status)}
                          </TableCell>
                          <TableCell>
                            {job.progress?.days || 30} days
                          </TableCell>
                          <TableCell className="text-right font-medium">
                            {job.stats?.threads_count || job.progress?.stats?.thread_count || 0}
                          </TableCell>
                          <TableCell className="text-right font-medium">
                            {job.stats?.embeddings_count || job.progress?.stats?.embeddings_created || 0}
                          </TableCell>
                          <TableCell className="text-right">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => setDeleteJobId(job.id)}
                              className="text-red-500 hover:text-red-600 hover:bg-red-50"
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>

      {/* Delete job confirmation */}
      <Dialog open={deleteJobId !== null} onOpenChange={(open) => !open && setDeleteJobId(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Import</DialogTitle>
            <DialogDescription>
              This will permanently delete this import and all associated data (messages, embeddings, contacts).
              This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteJobId(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => deleteJobId && handleDeleteJob(deleteJobId)}
            >
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete all confirmation */}
      <Dialog open={deleteAllSource !== null} onOpenChange={(open) => !open && setDeleteAllSource(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete All {deleteAllSource === "whatsapp" ? "WhatsApp" : "Gmail"} Imports</DialogTitle>
            <DialogDescription>
              This will permanently delete ALL {deleteAllSource === "whatsapp" ? "WhatsApp" : "Gmail"} imports and all associated data (messages, embeddings, contacts, threads).
              This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteAllSource(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => deleteAllSource && handleDeleteAll(deleteAllSource)}
            >
              Delete All
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

