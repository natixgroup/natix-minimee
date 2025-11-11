"use client";

import { useState, useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Loader2, Upload, X } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import type { Agent } from "@/lib/api";
import { getEnv } from "@/lib/env";

interface AgentAvatarUploadProps {
  agent: Agent | null;
  onUploadComplete?: (avatarUrl: string) => void;
}

export function AgentAvatarUpload({ agent, onUploadComplete }: AgentAvatarUploadProps) {
  const [isUploading, setIsUploading] = useState(false);
  const [preview, setPreview] = useState<string | null>(agent?.avatar_url || null);

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    const file = acceptedFiles[0];
    if (!file || !agent) return;

    // Validate file type
    if (!file.type.startsWith("image/")) {
      toast.error("Please upload an image file");
      return;
    }

    // Validate file size (max 5MB)
    if (file.size > 5 * 1024 * 1024) {
      toast.error("Image size must be less than 5MB");
      return;
    }

    // Create preview
    const reader = new FileReader();
    reader.onload = () => {
      setPreview(reader.result as string);
    };
    reader.readAsDataURL(file);

    // Upload file
    setIsUploading(true);
    try {
      const apiUrl = getEnv().apiUrl;
      const token = localStorage.getItem("auth_token");
      
      const formData = new FormData();
      formData.append("avatar", file);
      formData.append("agent_id", agent.id.toString());

      const response = await fetch(`${apiUrl}/agents/${agent.id}/avatar`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
        },
        body: formData,
      });

      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: "Upload failed" }));
        throw new Error(error.detail || "Upload failed");
      }

      const data = await response.json();
      setPreview(data.avatar_url);
      toast.success("Agent avatar updated successfully");
      onUploadComplete?.(data.avatar_url);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to upload avatar");
      setPreview(agent.avatar_url || null);
    } finally {
      setIsUploading(false);
    }
  }, [agent, onUploadComplete]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "image/*": [".png", ".jpg", ".jpeg", ".gif", ".webp"],
    },
    maxFiles: 1,
    disabled: isUploading || !agent,
  });

  const removeAvatar = async () => {
    if (!agent) return;
    
    setIsUploading(true);
    try {
      const apiUrl = getEnv().apiUrl;
      const token = localStorage.getItem("auth_token");
      
      const response = await fetch(`${apiUrl}/agents/${agent.id}/avatar`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error("Failed to remove avatar");
      }

      setPreview(null);
      toast.success("Avatar removed successfully");
      onUploadComplete?.("");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to remove avatar");
    } finally {
      setIsUploading(false);
    }
  };

  if (!agent) {
    return (
      <div className="space-y-2">
        <Label>Avatar</Label>
        <p className="text-sm text-muted-foreground">
          Save the agent first to upload an avatar
        </p>
      </div>
    );
  }

  const initials = agent.name
    .split(" ")
    .map((n) => n[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);

  return (
    <div className="space-y-2">
      <Label>Avatar</Label>
      <div className="flex items-center gap-4">
        <Avatar className="h-20 w-20">
          <AvatarImage src={preview || undefined} alt={agent.name} />
          <AvatarFallback>{initials}</AvatarFallback>
        </Avatar>
        
        <div className="flex flex-col gap-2">
          <div
            {...getRootProps()}
            className={`cursor-pointer rounded-md border-2 border-dashed p-2 text-sm transition-colors ${
              isDragActive
                ? "border-primary bg-primary/5"
                : "border-muted-foreground/25 hover:border-primary/50"
            } ${isUploading ? "opacity-50 cursor-not-allowed" : ""}`}
          >
            <input {...getInputProps()} />
            {isUploading ? (
              <div className="flex items-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin" />
                <span>Uploading...</span>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <Upload className="h-4 w-4" />
                <span>{isDragActive ? "Drop image here" : "Click or drag to upload"}</span>
              </div>
            )}
          </div>
          
          {preview && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={removeAvatar}
              disabled={isUploading}
              className="w-fit"
            >
              <X className="mr-2 h-4 w-4" />
              Remove
            </Button>
          )}
        </div>
      </div>
      <p className="text-xs text-muted-foreground">
        Recommended: Square image, at least 200x200px, max 5MB
      </p>
    </div>
  );
}

