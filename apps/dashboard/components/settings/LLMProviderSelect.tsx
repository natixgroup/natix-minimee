"use client";

import { useState } from "react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { useSettings, useCreateSetting } from "@/lib/hooks/useSettings";
import { Loader2 } from "lucide-react";

export function LLMProviderSelect() {
  const { data: settings = [], isLoading } = useSettings();
  const createSetting = useCreateSetting();
  const [provider, setProvider] = useState<string>("");

  const llmSetting = settings.find((s) => s.key === "llm_provider");
  const currentProvider = llmSetting?.value?.provider || "ollama";

  const handleSave = () => {
    createSetting.mutate({
      key: "llm_provider",
      value: { provider },
    });
    setProvider("");
  };

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>Current Provider</Label>
        <div className="text-sm text-muted-foreground">
          {currentProvider.toUpperCase()}
        </div>
      </div>

      <div className="space-y-2">
        <Label htmlFor="provider">Select Provider</Label>
        <Select value={provider} onValueChange={setProvider}>
          <SelectTrigger>
            <SelectValue placeholder="Choose LLM provider" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="ollama">Ollama (Local)</SelectItem>
            <SelectItem value="vllm">vLLM (70B)</SelectItem>
            <SelectItem value="openai">OpenAI (GPT-4o)</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <Button
        onClick={handleSave}
        disabled={!provider || createSetting.isPending}
      >
        {createSetting.isPending && (
          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        )}
        Save Provider
      </Button>
    </div>
  );
}

