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

interface AgentFormData {
  name: string;
  role: string;
  prompt: string;
  style: string;
  enabled: boolean;
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
      createAgent.mutate(
        {
          ...data,
          user_id: 1, // TODO: Get from auth
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

