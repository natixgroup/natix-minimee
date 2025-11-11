"use client";

import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { AgentList } from "@/components/agents/AgentList";
import { Button } from "@/components/ui/button";
import { Plus, Crown, AlertCircle } from "lucide-react";
import { useState } from "react";
import { AgentDialog } from "@/components/agents/AgentDialog";
import { api, type Agent } from "@/lib/api";
import { useQuery } from "@tanstack/react-query";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useAuth } from "@/lib/hooks/useAuth";

export default function AgentsPage() {
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingAgent, setEditingAgent] = useState<Agent | null>(null);
  const { user } = useAuth();
  const userId = user?.id;

  const { data: leaderAgent, isLoading: isLoadingLeader, error: leaderError } = useQuery<Agent | null>({
    queryKey: ["minimee-leader", userId],
    queryFn: () => api.getMinimeeLeader(userId),
    retry: false, // Don't retry on 404 (no leader set)
  });

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold">Agents</h1>
            <p className="text-muted-foreground">
              Manage your AI agents and their personalities
            </p>
          </div>
          <Button onClick={() => setIsDialogOpen(true)}>
            <Plus className="mr-2 h-4 w-4" />
            Create Agent
          </Button>
        </div>

        {/* Minimee Leader Section */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Crown className="h-5 w-5 text-yellow-600" />
              Minimee Leader Agent
            </CardTitle>
            <CardDescription>
              The leader agent handles WhatsApp messages when no specific agent is specified via [Agent Name] prefix
            </CardDescription>
          </CardHeader>
          <CardContent>
            {isLoadingLeader ? (
              <div className="text-muted-foreground">Loading leader agent...</div>
            ) : leaderAgent ? (
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Badge variant="default" className="bg-yellow-600">
                    <Crown className="h-3 w-3 mr-1" />
                    Leader
                  </Badge>
                  <div>
                    <div className="font-semibold">{leaderAgent.name}</div>
                    <div className="text-sm text-muted-foreground">{leaderAgent.role}</div>
                    {leaderAgent.whatsapp_display_name && (
                      <div className="text-xs text-muted-foreground mt-1">
                        WhatsApp: [{leaderAgent.whatsapp_display_name}]
                      </div>
                    )}
                  </div>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setEditingAgent(leaderAgent);
                    setIsDialogOpen(true);
                  }}
                >
                  Edit Leader
                </Button>
              </div>
            ) : (
              <div className="flex items-center gap-2 text-amber-600">
                <AlertCircle className="h-4 w-4" />
                <span className="text-sm">
                  No leader agent set. Please set a leader agent from the list below.
                </span>
              </div>
            )}
          </CardContent>
        </Card>

        <AgentList />

        <AgentDialog
          open={isDialogOpen}
          onOpenChange={(open) => {
            setIsDialogOpen(open);
            if (!open) setEditingAgent(null);
          }}
          agent={editingAgent}
        />
      </div>
    </DashboardLayout>
  );
}

