"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Settings } from "lucide-react";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { CategoryButtons } from "./CategoryButtons";

interface VisibilityRulesInlineProps {
  userInfoId: number;
  userId: number;
  onUpdate?: () => void;
}

type VisibilityLevel = "full" | "context_only" | "hidden";

interface VisibilityRule {
  id: number;
  relation_type_id: number | null;
  contact_id: number | null;
  can_use_for_response: boolean;
  can_say_explicitly: boolean;
  forbidden_for_response: boolean;
  forbidden_to_say: boolean;
}

// Convert 4-flag system to 3-level system
const flagsToLevel = (rule: VisibilityRule): VisibilityLevel => {
  if (rule.forbidden_for_response || rule.forbidden_to_say) {
    return "hidden";
  }
  if (rule.can_use_for_response && rule.can_say_explicitly) {
    return "full";
  }
  if (rule.can_use_for_response && !rule.can_say_explicitly) {
    return "context_only";
  }
  return "hidden";
};

// Convert 3-level system to 4-flag system
const levelToFlags = (level: VisibilityLevel) => {
  switch (level) {
    case "full":
      return {
        can_use_for_response: true,
        can_say_explicitly: true,
        forbidden_for_response: false,
        forbidden_to_say: false,
      };
    case "context_only":
      return {
        can_use_for_response: true,
        can_say_explicitly: false,
        forbidden_for_response: false,
        forbidden_to_say: false,
      };
    case "hidden":
      return {
        can_use_for_response: false,
        can_say_explicitly: false,
        forbidden_for_response: true,
        forbidden_to_say: true,
      };
  }
};

const LEVEL_LABELS: Record<VisibilityLevel, { label: string; color: string; emoji: string }> = {
  full: { label: "Full Access", color: "bg-green-500", emoji: "🟢" },
  context_only: { label: "Context Only", color: "bg-blue-500", emoji: "🔵" },
  hidden: { label: "Hidden", color: "bg-red-500", emoji: "🔴" },
};

export function VisibilityRulesInline({
  userInfoId,
  userId,
  onUpdate,
}: VisibilityRulesInlineProps) {
  const [visibilities, setVisibilities] = useState<VisibilityRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [defaultLevel, setDefaultLevel] = useState<VisibilityLevel>("context_only");

  useEffect(() => {
    if (open) {
      loadVisibilities();
    }
  }, [open, userInfoId]);

  const loadVisibilities = async () => {
    try {
      setLoading(true);
      const data = await api.getUserInfoVisibilities(userInfoId, userId);
      setVisibilities(data);
      
      // Find default rule (no relation_type_id and no contact_id)
      const defaultRule = data.find(
        (v: VisibilityRule) => v.relation_type_id === null && v.contact_id === null
      );
      if (defaultRule) {
        setDefaultLevel(flagsToLevel(defaultRule));
      }
    } catch (err) {
      console.error("Failed to load visibilities:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateLevel = async (level: VisibilityLevel, visibilityId?: number) => {
    try {
      const flags = levelToFlags(level);
      
      if (visibilityId) {
        // Update existing rule
        await api.updateUserInfoVisibility(userInfoId, visibilityId, userId, flags);
      } else {
        // Create or update default rule
        const defaultRule = visibilities.find(
          (v) => v.relation_type_id === null && v.contact_id === null
        );
        if (defaultRule) {
          await api.updateUserInfoVisibility(userInfoId, defaultRule.id, userId, flags);
        } else {
          await api.createUserInfoVisibility(userInfoId, userId, {
            relation_type_id: null,
            contact_id: null,
            ...flags,
          });
        }
      }
      
      await loadVisibilities();
      onUpdate?.();
    } catch (err: any) {
      const errorMessage = err instanceof Error ? err.message : String(err?.message || "Failed to update visibility");
      toast.error(errorMessage);
    }
  };

  const cycleLevel = () => {
    const levels: VisibilityLevel[] = ["full", "context_only", "hidden"];
    const currentIndex = levels.indexOf(defaultLevel);
    const nextIndex = (currentIndex + 1) % levels.length;
    handleUpdateLevel(levels[nextIndex]);
  };

  const getSummary = () => {
    const overrideCount = visibilities.filter(
      (v) => v.relation_type_id !== null || v.contact_id !== null
    ).length;
    const levelInfo = LEVEL_LABELS[defaultLevel];
    return `${levelInfo.emoji} ${levelInfo.label}${overrideCount > 0 ? ` (${overrideCount} overrides)` : ""}`;
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <div className="flex items-center gap-1">
        <Button
          variant="ghost"
          size="sm"
          className="h-7"
          onClick={cycleLevel}
          title="Click to cycle level"
        >
          <span className="text-xs">{getSummary()}</span>
        </Button>
        <DialogTrigger asChild>
          <Button variant="ghost" size="sm" className="h-7 w-7 p-0" title="Open visibility settings">
            <Settings className="h-3 w-3" />
          </Button>
        </DialogTrigger>
      </div>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Visibility Rules</DialogTitle>
          <DialogDescription>
            Control who can see and use this information
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          {loading ? (
            <div className="text-sm text-muted-foreground">Loading...</div>
          ) : (
            <>
              <div className="space-y-3">
                <div>
                  <label className="text-sm font-medium mb-2 block">Default Level</label>
                  <CategoryButtons
                    categories={["Full Access", "Context Only", "Hidden"]}
                    selected={[LEVEL_LABELS[defaultLevel].label]}
                    onChange={(selected) => {
                      const level = Object.entries(LEVEL_LABELS).find(
                        ([_, info]) => info.label === selected[0]
                      )?.[0] as VisibilityLevel;
                      if (level) {
                        handleUpdateLevel(level);
                      }
                    }}
                  />
                  <p className="text-xs text-muted-foreground mt-2">
                    {defaultLevel === "full" && "Agent can use as context and mention explicitly"}
                    {defaultLevel === "context_only" && "Agent can use as context but not mention explicitly"}
                    {defaultLevel === "hidden" && "Agent cannot use this information"}
                  </p>
                </div>

                {visibilities.filter((v) => v.relation_type_id !== null || v.contact_id !== null).length > 0 && (
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Overrides</label>
                    {visibilities
                      .filter((v) => v.relation_type_id !== null || v.contact_id !== null)
                      .map((visibility) => {
                        const level = flagsToLevel(visibility);
                        return (
                          <div key={visibility.id} className="border rounded-lg p-3 space-y-2">
                            <div className="text-xs font-medium">
                              {visibility.contact_id
                                ? `Contact #${visibility.contact_id}`
                                : visibility.relation_type_id
                                ? `Relation Type #${visibility.relation_type_id}`
                                : "Unknown"}
                            </div>
                            <CategoryButtons
                              categories={["Full Access", "Context Only", "Hidden"]}
                              selected={[LEVEL_LABELS[level].label]}
                              onChange={(selected) => {
                                const newLevel = Object.entries(LEVEL_LABELS).find(
                                  ([_, info]) => info.label === selected[0]
                                )?.[0] as VisibilityLevel;
                                if (newLevel) {
                                  handleUpdateLevel(newLevel, visibility.id);
                                }
                              }}
                            />
                          </div>
                        );
                      })}
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

