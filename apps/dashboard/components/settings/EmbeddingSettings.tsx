"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useSettings, useCreateSetting } from "@/lib/hooks/useSettings";
import { api } from "@/lib/api";
import { Loader2, Check } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { cn } from "@/lib/utils";

interface EmbeddingModelInfo {
  model: string;
  dimensions: number;
  description: string;
  size?: string;
  available: boolean;
  use_case?: string;
  location_type?: "local" | "cloud";
  cost?: "free" | "paid";
}

export function EmbeddingSettings() {
  const { data: settings = [], isLoading: isLoadingSettings } = useSettings();
  const createSetting = useCreateSetting();

  const embeddingSetting = settings.find((s) => s.key === "embedding_model");
  const currentModel = embeddingSetting?.value?.model || "sentence-transformers/all-MiniLM-L6-v2";

  const { data: modelsData, isLoading: isLoadingModels } = useQuery({
    queryKey: ["embedding-models"],
    queryFn: () => api.getEmbeddingModels(),
  });

  const models: EmbeddingModelInfo[] = modelsData?.models || [];

  const handleSwitchModel = (model: string) => {
    createSetting.mutate({
      key: "embedding_model",
      value: { model },
    });
  };

  const isActive = (model: string) => {
    return currentModel === model || model.toLowerCase() === currentModel.toLowerCase();
  };

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
        <h3 className="text-sm font-medium">Current Model</h3>
        <div className="text-sm text-muted-foreground">{currentModel}</div>
      </div>

      <div className="space-y-4">
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {models.map((model) => {
            const active = isActive(model.model);

            return (
              <Card
                key={model.model}
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
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Dimensions:</span>
                      <span className="font-medium">{model.dimensions}</span>
                    </div>
                    {model.size && (
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Taille:</span>
                        <span className="font-medium">{model.size}</span>
                      </div>
                    )}
                    {model.use_case && (
                      <div className="flex flex-col gap-1">
                        <span className="text-muted-foreground">Usage:</span>
                        <span className="font-medium text-xs">{model.use_case}</span>
                      </div>
                    )}
                    {!model.available && (
                      <div className="text-xs text-destructive mt-2">
                        Model not available
                      </div>
                    )}
                  </div>
                  <Button
                    onClick={() => handleSwitchModel(model.model)}
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
    </div>
  );
}
