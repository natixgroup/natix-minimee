"use client";

import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useSettings, useCreateSetting } from "@/lib/hooks/useSettings";
import { Loader2 } from "lucide-react";

export function EmbeddingSettings() {
  const { data: settings = [] } = useSettings();
  const createSetting = useCreateSetting();

  const embeddingModel = settings.find((s) => s.key === "embedding_model");
  const currentModel = embeddingModel?.value?.model || "sentence-transformers/all-MiniLM-L6-v2";

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>Current Model</Label>
        <div className="text-sm text-muted-foreground">{currentModel}</div>
      </div>

      <div className="space-y-2">
        <Label htmlFor="model">Embedding Model</Label>
        <Input
          id="model"
          defaultValue={currentModel}
          placeholder="sentence-transformers/all-MiniLM-L6-v2"
        />
      </div>

      <Button disabled={createSetting.isPending}>
        {createSetting.isPending && (
          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        )}
        Save Settings
      </Button>
    </div>
  );
}

