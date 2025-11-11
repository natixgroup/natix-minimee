"use client";

import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { EmbeddingsTable } from "@/components/embeddings/EmbeddingsTable";
import { DataSourceStats } from "@/components/embeddings/DataSourceStats";

export default function EmbeddingsPage() {
  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold">Embeddings</h1>
          <p className="text-muted-foreground">
            Browse and search embeddings with their text content for debugging
          </p>
        </div>

        <DataSourceStats />

        <EmbeddingsTable />
      </div>
    </DashboardLayout>
  );
}

