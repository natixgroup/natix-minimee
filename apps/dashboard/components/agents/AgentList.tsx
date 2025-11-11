"use client";

import { useAgents, useDeleteAgent } from "@/lib/hooks/useAgents";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Edit, Trash2, Crown } from "lucide-react";
import { useState } from "react";
import { AgentDialog } from "./AgentDialog";
import { type Agent, api } from "@/lib/api";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

export function AgentList() {
  const userId = 1; // TODO: Get from auth context
  const { data: agents = [], isLoading } = useAgents(userId);
  const deleteAgent = useDeleteAgent();
  const [editingAgent, setEditingAgent] = useState<Agent | null>(null);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const queryClient = useQueryClient();

  const handleSetLeader = async (agentId: number) => {
    try {
      await api.setMinimeeLeader(agentId, userId);
      queryClient.invalidateQueries({ queryKey: ["agents"] });
      toast.success("Leader agent updated successfully");
    } catch (error) {
      toast.error(`Failed to set leader: ${error instanceof Error ? error.message : "Unknown error"}`);
    }
  };

  if (isLoading) {
    return <div className="text-muted-foreground">Loading agents...</div>;
  }

  if (agents.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>No Agents</CardTitle>
          <CardDescription>
            Create your first agent to get started with Minimee
          </CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Agents help Minimee understand your communication style and handle
            different types of conversations on your behalf.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <>
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Role</TableHead>
              <TableHead>Leader</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Created</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {agents.map((agent) => (
              <TableRow key={agent.id}>
                <TableCell className="font-medium">{agent.name}</TableCell>
                <TableCell>{agent.role}</TableCell>
                <TableCell>
                  {agent.is_minimee_leader ? (
                    <Badge variant="default" className="bg-yellow-600">
                      <Crown className="h-3 w-3 mr-1" />
                      Leader
                    </Badge>
                  ) : (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleSetLeader(agent.id)}
                      className="text-xs"
                    >
                      Set as Leader
                    </Button>
                  )}
                </TableCell>
                <TableCell>
                  <Badge 
                    variant={agent.enabled ? "default" : "secondary"}
                    className={agent.enabled ? "bg-green-600" : ""}
                  >
                    {agent.enabled ? "Enabled" : "Disabled"}
                  </Badge>
                </TableCell>
                <TableCell>
                  {new Date(agent.created_at).toLocaleDateString()}
                </TableCell>
                <TableCell className="text-right">
                  <div className="flex justify-end gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        setEditingAgent(agent);
                        setIsDialogOpen(true);
                      }}
                    >
                      <Edit className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        if (
                          confirm(
                            `Are you sure you want to delete ${agent.name}?`
                          )
                        ) {
                          deleteAgent.mutate(agent.id);
                        }
                      }}
                    >
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <AgentDialog
        open={isDialogOpen}
        onOpenChange={(open) => {
          setIsDialogOpen(open);
          if (!open) setEditingAgent(null);
        }}
        agent={editingAgent}
      />
    </>
  );
}

