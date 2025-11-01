"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { LLMProviderSelect } from "./LLMProviderSelect";
import { EmbeddingSettings } from "./EmbeddingSettings";

export function AISettings() {
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>LLM Provider</CardTitle>
          <CardDescription>
            Configure which Large Language Model provider to use for generating responses
          </CardDescription>
        </CardHeader>
        <CardContent>
          <LLMProviderSelect />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Embedding Model</CardTitle>
          <CardDescription>
            Configure the embedding model for semantic search and RAG (Retrieval-Augmented Generation)
          </CardDescription>
        </CardHeader>
        <CardContent>
          <EmbeddingSettings />
        </CardContent>
      </Card>
    </div>
  );
}

