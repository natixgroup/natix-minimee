"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Upload, CheckCircle2, Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import { toast } from "sonner";

export function WhatsAppUpload() {
  const [file, setFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadSuccess, setUploadSuccess] = useState(false);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile && selectedFile.name.endsWith(".txt")) {
      setFile(selectedFile);
      setUploadSuccess(false);
    } else {
      toast.error("Please select a .txt file");
    }
  };

  const handleUpload = async () => {
    if (!file) {
      toast.error("Please select a file first");
      return;
    }

    setIsUploading(true);
    try {
      await api.uploadWhatsApp(file, 1); // TODO: Get userId from auth
      setUploadSuccess(true);
      setFile(null);
      toast.success("WhatsApp conversation imported successfully");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Upload failed");
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Input
          type="file"
          accept=".txt"
          onChange={handleFileChange}
          className="cursor-pointer"
        />
        <p className="text-sm text-muted-foreground">
          Select a WhatsApp conversation export (.txt file)
        </p>
      </div>

      {file && (
        <div className="rounded-lg border p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium">{file.name}</p>
              <p className="text-sm text-muted-foreground">
                {(file.size / 1024).toFixed(2)} KB
              </p>
            </div>
            {uploadSuccess && (
              <CheckCircle2 className="h-5 w-5 text-green-500" />
            )}
          </div>
        </div>
      )}

      <Button
        onClick={handleUpload}
        disabled={!file || isUploading || uploadSuccess}
        className="w-full"
      >
        {isUploading ? (
          <>
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            Uploading...
          </>
        ) : (
          <>
            <Upload className="mr-2 h-4 w-4" />
            Upload & Import
          </>
        )}
      </Button>
    </div>
  );
}

