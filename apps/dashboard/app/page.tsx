"use client";

import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Bot, MessageSquare, Clock, CheckCircle } from "lucide-react";
import { useAgents } from "@/lib/hooks/useAgents";

export default function OverviewPage() {
  const { data: agents = [], isLoading } = useAgents();

  const stats = [
    {
      title: "Total Agents",
      value: agents.length,
      icon: Bot,
      description: `${agents.filter((a) => a.enabled).length} active`,
    },
    {
      title: "Messages Today",
      value: "0",
      icon: MessageSquare,
      description: "No messages yet",
    },
    {
      title: "Pending Approvals",
      value: "0",
      icon: Clock,
      description: "All clear",
    },
    {
      title: "System Status",
      value: "Healthy",
      icon: CheckCircle,
      description: "All systems operational",
    },
  ];

  if (isLoading) {
    return (
      <DashboardLayout>
        <div className="space-y-6">
          <div>
            <h1 className="text-3xl font-bold">Overview</h1>
            <p className="text-muted-foreground">Loading...</p>
          </div>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold">Overview</h1>
          <p className="text-muted-foreground">
            Welcome to your Minimee dashboard
          </p>
        </div>

        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {stats.map((stat) => {
            const Icon = stat.icon;
            return (
              <Card key={stat.title}>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">
                    {stat.title}
                  </CardTitle>
                  <Icon className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">{stat.value}</div>
                  <p className="text-xs text-muted-foreground">
                    {stat.description}
                  </p>
                </CardContent>
              </Card>
            );
          })}
        </div>

        {agents.length === 0 && (
          <Card>
            <CardHeader>
              <CardTitle>Get Started</CardTitle>
              <CardDescription>
                Create your first agent to start using Minimee
              </CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                Agents help Minimee understand your communication style and
                handle different types of conversations.
              </p>
            </CardContent>
          </Card>
        )}
      </div>
    </DashboardLayout>
  );
}
