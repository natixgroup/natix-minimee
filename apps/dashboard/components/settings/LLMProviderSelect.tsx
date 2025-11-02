"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useSettings, useCreateSetting } from "@/lib/hooks/useSettings";
import { api } from "@/lib/api";
import { Loader2, Check } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { cn } from "@/lib/utils";

interface ModelInfo {
  provider: string;
  model: string;
  parameters?: string;
  size?: string;
  context_length?: string;
  modified?: string;
  description?: string;
  available: boolean;
  error?: string;
  location_type?: "local" | "cloud";
  cost?: "free" | "paid";
  cost_info?: string;
}

export function LLMProviderSelect() {
  const { data: settings = [], isLoading: isLoadingSettings } = useSettings();
  const createSetting = useCreateSetting();
  
  const llmSetting = settings.find((s) => s.key === "llm_provider");
  const currentProvider = llmSetting?.value?.provider || "ollama";
  const currentModelFromSettings = llmSetting?.value?.model || null;

  // Get the actual active model from backend status
  const { data: modelStatus } = useQuery({
    queryKey: ["llm-status"],
    queryFn: () => api.getModelStatus(),
    enabled: !isLoadingSettings,
  });

  // Use model from status if available, otherwise fall back to settings
  const currentModel = modelStatus?.model || currentModelFromSettings;

  const { data: modelsData, isLoading: isLoadingModels } = useQuery({
    queryKey: ["models"],
    queryFn: () => api.getModels(),
  });

  const models: ModelInfo[] = modelsData?.models || [];

  const handleSwitchProvider = (provider: string, model?: string) => {
    createSetting.mutate({
      key: "llm_provider",
      value: { 
        provider,
        ...(model && { model })
      },
    });
  };

  const isActive = (provider: string, model: string) => {
    // Provider must match
    if (currentProvider !== provider) return false;
    
    // Get the model to compare (from status first, then settings)
    const modelToCompare = modelStatus?.model || currentModel;
    
    if (!modelToCompare) {
      // No model specified - this shouldn't happen, but if it does, return false
      return false;
    }
    
    // Normalize both model names for comparison
    const normalizeModelName = (name: string) => {
      if (!name) return "";
      return name.toLowerCase()
        .replace(/:latest$/, "") // Remove :latest tag
        .replace(/:/g, "") // Remove all colons
        .replace(/\s+/g, "") // Remove spaces
        .trim();
    };
    
    const normalizedCurrent = normalizeModelName(modelToCompare);
    const normalizedModel = normalizeModelName(model);
    
    // Exact normalized match
    if (normalizedCurrent === normalizedModel) return true;
    
    // Check if one contains the other (for partial matches like "llama3.2:1b" vs "llama3.2:1b")
    if (normalizedCurrent && normalizedModel) {
      if (normalizedCurrent.includes(normalizedModel) || 
          normalizedModel.includes(normalizedCurrent)) {
        return true;
      }
    }
    
    // For Ollama, also check direct string matching (case-insensitive)
    if (provider === "ollama") {
      const currentLower = modelToCompare.toLowerCase();
      const modelLower = model.toLowerCase();
      
      // Exact match
      if (currentLower === modelLower) return true;
      
      // Check if current model name starts with model name or vice versa
      // e.g., "llama3.2:1b" matches "llama3.2:1b" (same)
      // or "llama3.2:1b" contains "llama3.2"
      if (currentLower.startsWith(modelLower) || modelLower.startsWith(currentLower)) {
        return true;
      }
      
      // Check if they share a common prefix (e.g., both start with "llama3.2")
      const getBaseModel = (name: string) => {
        return name.split(":")[0].toLowerCase();
      };
      if (getBaseModel(modelToCompare) === getBaseModel(model)) {
        return true;
      }
    }
    
    return false;
  };

  const getProviderLabel = (provider: string) => {
    const labels: Record<string, string> = {
      ollama: "Ollama",
      openai: "OpenAI",
      vllm: "vLLM",
    };
    return labels[provider] || provider;
  };

  const getProviderColor = (provider: string) => {
    const colors: Record<string, string> = {
      ollama: "bg-blue-500",
      openai: "bg-green-500",
      vllm: "bg-purple-500",
    };
    return colors[provider] || "bg-gray-500";
  };

  // Group models by provider
  const groupedModels = models.reduce((acc, model) => {
    if (!acc[model.provider]) {
      acc[model.provider] = [];
    }
    acc[model.provider].push(model);
    return acc;
  }, {} as Record<string, ModelInfo[]>);

  const providerOrder = ["ollama", "openai", "vllm"];

  if (isLoadingSettings || isLoadingModels) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }


  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <h3 className="text-sm font-medium">Current Provider</h3>
        <div className="text-sm text-muted-foreground">
          {getProviderLabel(currentProvider)} {currentModel && `- ${currentModel}`}
        </div>
      </div>

      <div className="space-y-4">
        {providerOrder.map((provider) => {
          const providerModels = groupedModels[provider] || [];
          if (providerModels.length === 0) return null;

          return (
            <div key={provider} className="space-y-3">
              <div className="flex items-center gap-2">
                <div className={cn("h-3 w-3 rounded-full", getProviderColor(provider))} />
                <h3 className="text-sm font-semibold">{getProviderLabel(provider)}</h3>
              </div>
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {providerModels.map((model, index) => {
                  // Check if this model is active
                  let active = isActive(model.provider, model.model);
                  
                  // Fallback: if no model is specified from backend/settings but provider matches,
                  // mark the first model of that provider as active (likely default)
                  const hasNoModelFromBackend = !modelStatus?.model && !currentModelFromSettings;
                  if (!active && hasNoModelFromBackend && model.provider === currentProvider && index === 0) {
                    active = true;
                  }
                  
                  return (
                    <Card
                      key={`${model.provider}-${model.model}`}
                      className={cn(
                        "relative transition-all hover:shadow-md",
                        active
                          ? "ring-2 ring-primary border-primary"
                          : "border-muted"
                      )}
                    >
                      <div className="absolute top-2 right-2 flex gap-1 flex-wrap justify-end max-w-[60%]">
                        {active && (
                          <Badge variant="default" className="bg-primary">
                            <Check className="h-3 w-3 mr-1" />
                            Active
                          </Badge>
                        )}
                        {model.location_type && (
                          <Badge 
                            variant={model.location_type === "local" ? "secondary" : "outline"}
                            className={cn(
                              model.location_type === "local" 
                                ? "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200" 
                                : "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200"
                            )}
                          >
                            {model.location_type === "local" ? "Local" : "Cloud"}
                          </Badge>
                        )}
                        {model.cost && (
                          <Badge 
                            variant={model.cost === "free" ? "secondary" : "destructive"}
                            className={cn(
                              model.cost === "free"
                                ? "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200"
                                : "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200"
                            )}
                          >
                            {model.cost === "free" ? "Gratuit" : "Payant"}
                          </Badge>
                        )}
                      </div>
                      <CardHeader className="pb-3">
                        <CardTitle className="text-base pr-20">{model.model}</CardTitle>
                        {model.description && (
                          <p className="text-xs text-muted-foreground mt-1">
                            {model.description}
                          </p>
                        )}
                      </CardHeader>
                      <CardContent className="space-y-3">
                        <div className="space-y-2 text-sm">
                          {model.parameters && (
                            <div className="flex justify-between">
                              <span className="text-muted-foreground">Paramètres:</span>
                              <span className="font-medium">{model.parameters}</span>
                            </div>
                          )}
                          {model.size && (
                            <div className="flex justify-between">
                              <span className="text-muted-foreground">Taille:</span>
                              <span className="font-medium">{model.size}</span>
                            </div>
                          )}
                          {model.context_length && (
                            <div className="flex justify-between">
                              <span className="text-muted-foreground">Contexte:</span>
                              <span className="font-medium">{model.context_length}</span>
                            </div>
                          )}
                          {model.modified && (
                            <div className="flex justify-between">
                              <span className="text-muted-foreground">Modifié:</span>
                              <span className="font-medium text-xs">{model.modified}</span>
                            </div>
                          )}
                          {model.cost_info && model.cost === "paid" && (
                            <div className="flex justify-between items-center pt-1 border-t">
                              <span className="text-muted-foreground text-xs">Coût:</span>
                              <span className="font-medium text-xs text-orange-600 dark:text-orange-400">
                                {model.cost_info}
                              </span>
                            </div>
                          )}
                          {!model.available && model.error && (
                            <div className="text-xs text-destructive mt-2">
                              {model.error}
                            </div>
                          )}
                        </div>
                        <Button
                          onClick={() => handleSwitchProvider(model.provider, model.model)}
                          disabled={active || createSetting.isPending || !model.available}
                          className="w-full"
                          variant={active ? "outline" : "default"}
                        >
                          {createSetting.isPending ? (
                            <>
                              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                              Switching...
                            </>
                          ) : active ? (
                            "Currently Active"
                          ) : (
                            "Switch to this model"
                          )}
                        </Button>
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
