"use client";

import { useEffect } from "react";
import { useForm } from "react-hook-form";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import {
  useCreateAgent,
  useUpdateAgent,
} from "@/lib/hooks/useAgents";
import { type Agent } from "@/lib/api";
import { AgentAvatarUpload } from "./AgentAvatarUpload";
import { useAuth } from "@/lib/hooks/useAuth";

interface AgentFormData {
  name: string;
  role: string;
  prompt: string;
  style: string;
  enabled: boolean;
  whatsapp_display_name?: string;
  approval_rules?: Record<string, any>;
}

interface AgentDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  agent?: Agent | null;
}

export function AgentDialog({
  open,
  onOpenChange,
  agent,
}: AgentDialogProps) {
  const { user } = useAuth();
  const createAgent = useCreateAgent();
  const updateAgent = useUpdateAgent();
  const {
    register,
    handleSubmit,
    reset,
    setValue,
    watch,
    formState: { errors },
  } = useForm<AgentFormData>({
    defaultValues: {
      name: "",
      role: "",
      prompt: "",
      style: "",
      enabled: true,
      whatsapp_display_name: "",
      approval_rules: {
        auto_approve_simple: true,
        threshold: 0.8,
        keywords_for_approval: [],
      },
    },
  });

  const enabled = watch("enabled");

  useEffect(() => {
    if (agent) {
      setValue("name", agent.name);
      setValue("role", agent.role);
      setValue("prompt", agent.prompt);
      setValue("style", agent.style || "");
      setValue("enabled", agent.enabled);
      setValue("whatsapp_display_name", agent.whatsapp_display_name || "");
      setValue("approval_rules", agent.approval_rules || {
        auto_approve_simple: true,
        threshold: 0.8,
        keywords_for_approval: [],
      });
    } else {
      reset();
    }
  }, [agent, setValue, reset]);

  const onSubmit = (data: AgentFormData) => {
    if (agent) {
      updateAgent.mutate(
        {
          id: agent.id,
          data,
        },
        {
          onSuccess: () => {
            onOpenChange(false);
            reset();
          },
        }
      );
    } else {
      if (!user) {
        return;
      }
      createAgent.mutate(
        {
          ...data,
          user_id: user.id,
        },
        {
          onSuccess: () => {
            onOpenChange(false);
            reset();
          },
        }
      );
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>{agent ? "Edit Agent" : "Create Agent"}</DialogTitle>
          <DialogDescription>
            Configure your AI agent's personality and behavior
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)}>
          <div className="space-y-4 py-4">
            <AgentAvatarUpload
              agent={agent}
              onUploadComplete={(avatarUrl) => {
                if (agent) {
                  // Update agent with new avatar URL
                  updateAgent.mutate({
                    id: agent.id,
                    data: { ...agent, avatar_url: avatarUrl },
                  });
                }
              }}
            />

            <div className="space-y-2">
              <Label htmlFor="name">Name</Label>
              <Input
                id="name"
                {...register("name", { required: "Name is required" })}
              />
              {errors.name && (
                <p className="text-sm text-destructive">{errors.name.message}</p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="role">Role</Label>
              <Input
                id="role"
                {...register("role", { required: "Role is required" })}
                placeholder="e.g., Customer Support, Personal Assistant"
              />
              {errors.role && (
                <p className="text-sm text-destructive">{errors.role.message}</p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="prompt">System Prompt</Label>
              <Textarea
                id="prompt"
                {...register("prompt", { required: "Prompt is required" })}
                rows={4}
                placeholder="Define the agent's personality and behavior..."
              />
              {errors.prompt && (
                <p className="text-sm text-destructive">
                  {errors.prompt.message}
                </p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="style">Communication Style</Label>
              <Textarea
                id="style"
                {...register("style")}
                rows={2}
                placeholder="e.g., Professional, Friendly, Casual..."
              />
            </div>

            <div className="flex items-center justify-between">
              <Label htmlFor="enabled">Enabled</Label>
              <Switch
                id="enabled"
                checked={enabled}
                onCheckedChange={(checked) => setValue("enabled", checked)}
              />
            </div>

            <div className="border-t pt-4 mt-4">
              <h3 className="text-sm font-semibold mb-3">WhatsApp Integration</h3>
              <div className="space-y-2">
                <Label htmlFor="whatsapp_display_name">WhatsApp Display Name</Label>
                <Input
                  id="whatsapp_display_name"
                  {...register("whatsapp_display_name")}
                  placeholder="Name shown in WhatsApp messages (e.g., [Agent Name])"
                />
                <p className="text-xs text-muted-foreground">
                  This name will appear as a prefix in WhatsApp messages sent by this agent
                </p>
              </div>
            </div>

            <div className="border-t pt-4 mt-4">
              <h3 className="text-sm font-semibold mb-3">Approval Rules</h3>
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <Label htmlFor="auto_approve_simple">Auto-approve simple messages</Label>
                  <Switch
                    id="auto_approve_simple"
                    checked={watch("approval_rules")?.auto_approve_simple ?? true}
                    onCheckedChange={(checked) => {
                      setValue("approval_rules", {
                        ...watch("approval_rules"),
                        auto_approve_simple: checked,
                      });
                    }}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="threshold">Confidence threshold (0-1)</Label>
                  <Input
                    id="threshold"
                    type="number"
                    step="0.1"
                    min="0"
                    max="1"
                    value={watch("approval_rules")?.threshold ?? 0.8}
                    onChange={(e) => {
                      setValue("approval_rules", {
                        ...watch("approval_rules"),
                        threshold: parseFloat(e.target.value),
                      });
                    }}
                  />
                  <p className="text-xs text-muted-foreground">
                    Messages below this confidence threshold will require approval
                  </p>
                </div>
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit">
              {agent ? "Update" : "Create"} Agent
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

