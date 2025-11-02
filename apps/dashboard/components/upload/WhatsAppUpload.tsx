"use client";

import { useState, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Upload, CheckCircle2, Loader2, AlertCircle, FileText, MessageSquare, Layers, Sparkles, Tag } from "lucide-react";
import { api, UploadStats } from "@/lib/api";
import { toast } from "sonner";

interface UploadResult {
  message: string;
  conversation_id: string;
  stats: UploadStats;
  warnings?: string[];
}

type UploadStep = "idle" | "uploading" | "parsing" | "chunking" | "embedding" | "summarizing" | "complete" | "error";

interface ProgressData {
  step?: string;
  message?: string;
  current?: number;
  total?: number;
  embeddings_created?: number;
  percent?: number;
}

export function WhatsAppUpload() {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadSuccess, setUploadSuccess] = useState(false);
  const [uploadStep, setUploadStep] = useState<UploadStep>("idle");
  const [uploadResult, setUploadResult] = useState<UploadResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [progressData, setProgressData] = useState<ProgressData | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile && selectedFile.name.endsWith(".txt")) {
      setFile(selectedFile);
      setUploadSuccess(false);
      setUploadResult(null);
      setError(null);
      setUploadStep("idle");
    } else {
      toast.error("Please select a .txt file");
      setFile(null);
    }
  };

  const handleUpload = () => {
    if (!file) {
      toast.error("Please select a file first");
      return;
    }

    setIsUploading(true);
    setUploadStep("uploading");
    setError(null);
    setUploadResult(null);
    setProgressData(null);

    api.uploadWhatsAppWithProgress(
      file,
      1, // TODO: Get userId from auth
      (update) => {
        if (update.type === "upload") {
          // Handle upload progress
          setUploadStep("uploading");
          setProgressData({
            step: "uploading",
            message: update.data?.message || `Uploading file... ${update.uploadPercent || 0}%`,
            percent: update.uploadPercent || update.data?.percent || 0,
            current: update.uploadPercent,
            total: 100,
          });
        } else if (update.type === "progress") {
          // Update step based on progress data
          const step = update.data?.step || update.step || "parsing";
          setUploadStep(step as UploadStep);
          setProgressData(update.data || null);
          
          // Log progress for debugging
          if (update.data) {
            const { current, total, message, embeddings_created } = update.data;
            if (current !== undefined && total !== undefined) {
              console.log(`Progress: ${message || step} - ${current}/${total}`);
            }
            if (embeddings_created !== undefined) {
              console.log(`Embeddings created: ${embeddings_created}`);
            }
          }
        } else if (update.type === "complete") {
          setUploadStep("complete");
          const result: UploadResult = {
            message: update.message || "Successfully imported",
            conversation_id: update.conversation_id || "",
            stats: update.stats || {
              messages_created: 0,
              chunks_created: 0,
              summaries_created: 0,
              embeddings_created: 0,
            },
            warnings: update.warnings,
          };
          setUploadResult(result);
          setUploadSuccess(true);
          setIsUploading(false);
          setFile(null);
          
          // Show success toast
          const stats = result.stats;
          const summary = `${stats.messages_created} messages, ${stats.chunks_created} chunks, ${stats.embeddings_created} embeddings`;
          toast.success(`WhatsApp conversation imported: ${summary}`);
        } else if (update.type === "error") {
          setUploadStep("error");
          const errorMessage = update.message || "Upload failed";
          setError(errorMessage);
          setIsUploading(false);
          toast.error(errorMessage);
        }
      },
      (error) => {
        setUploadStep("error");
        const errorMessage = error.message || "Upload failed";
        setError(errorMessage);
        setIsUploading(false);
        toast.error(errorMessage);
      }
    );
  };

  const getStepLabel = (step: UploadStep, percent?: number) => {
    const baseLabel = (() => {
      switch (step) {
        case "uploading":
          return "Uploading file";
        case "parsing":
          return "Parsing messages";
        case "chunking":
          return "Creating chunks";
        case "embedding":
          return "Generating embeddings";
        case "summarizing":
          return "Generating summaries";
        case "complete":
          return "Complete!";
        case "error":
          return "Error occurred";
        default:
          return "";
      }
    })();
    
    // Add percentage to label for better visibility
    if (percent !== undefined && step !== "complete" && step !== "error") {
      return `${baseLabel}... ${percent}%`;
    }
    
    return baseLabel + (step !== "complete" && step !== "error" ? "..." : "");
  };

  const handleChooseFile = () => {
    fileInputRef.current?.click();
  };

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Input
          ref={fileInputRef}
          type="file"
          accept=".txt"
          onChange={handleFileChange}
          className="hidden"
          disabled={isUploading}
        />
        <Button
          type="button"
          variant="outline"
          onClick={handleChooseFile}
          disabled={isUploading}
          className="w-full"
        >
          <FileText className="mr-2 h-4 w-4" />
          {file ? file.name : "Choose File"}
        </Button>
        <p className="text-sm text-muted-foreground">
          Select a WhatsApp conversation export (.txt file). Maximum size: 50MB.
        </p>
      </div>

      {file && !uploadSuccess && (
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <FileText className="h-5 w-5 text-muted-foreground" />
                <div>
                  <p className="font-medium">{file.name}</p>
                  <p className="text-sm text-muted-foreground">
                    {(file.size / 1024).toFixed(2)} KB
                  </p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Progress indicator with detailed info */}
      {isUploading && uploadStep !== "idle" && (
        <Card>
          <CardContent className="pt-6">
            <div className="space-y-3">
              <div className="flex items-center gap-3">
                <Loader2 className="h-5 w-5 animate-spin text-primary" />
                <div className="flex-1">
                  <div className="flex items-center justify-between">
                    <p className="font-medium">{getStepLabel(uploadStep, progressData?.percent)}</p>
                    {progressData?.percent !== undefined && (
                      <p className="font-semibold text-primary text-lg">
                        {progressData.percent}%
                      </p>
                    )}
                  </div>
                  {progressData?.message && (
                    <p className="text-sm text-muted-foreground mt-1">
                      {progressData.message}
                    </p>
                  )}
                </div>
              </div>
              
              {/* Detailed progress counters */}
              {progressData && (
                <div className="space-y-2 pl-8 border-l-2 border-primary/20">
                  {progressData.current !== undefined && progressData.total !== undefined && (
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">
                        {progressData.step === "saving_messages" && "Messages"}
                        {progressData.step === "embedding" && "Chunks"}
                        {progressData.step === "summarizing" && "Summaries"}
                        {!progressData.step && "Progress"}
                      </span>
                      <span className="text-sm font-medium">
                        {progressData.current} / {progressData.total}
                      </span>
                    </div>
                  )}
                  
                  {progressData.embeddings_created !== undefined && (
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">Embeddings vectorized</span>
                      <span className="text-sm font-medium">
                        {progressData.embeddings_created}
                      </span>
                    </div>
                  )}
                  
                  {/* Progress bar using percent if available, otherwise calculate from current/total */}
                  {(progressData.percent !== undefined || (progressData.current !== undefined && progressData.total !== undefined && progressData.total > 0)) && (
                    <div className="w-full bg-muted rounded-full h-2 overflow-hidden">
                      <div
                        className="bg-primary h-2 rounded-full transition-all duration-300"
                        style={{
                          width: `${progressData.percent !== undefined 
                            ? Math.min(100, progressData.percent) 
                            : Math.min(100, (progressData.current! / progressData.total!) * 100)}%`,
                        }}
                      />
                    </div>
                  )}
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Error display */}
      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Upload Failed</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Success stats */}
      {uploadSuccess && uploadResult && (
        <Card className="border-green-200 dark:border-green-800">
          <CardContent className="pt-6">
            <div className="space-y-4">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="h-5 w-5 text-green-500" />
                <p className="font-semibold text-green-700 dark:text-green-400">
                  Upload Successful!
                </p>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="flex items-center gap-2">
                  <MessageSquare className="h-4 w-4 text-muted-foreground" />
                  <div>
                    <p className="text-sm font-medium">{uploadResult.stats.messages_created}</p>
                    <p className="text-xs text-muted-foreground">Messages</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Layers className="h-4 w-4 text-muted-foreground" />
                  <div>
                    <p className="text-sm font-medium">{uploadResult.stats.chunks_created}</p>
                    <p className="text-xs text-muted-foreground">Chunks</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Sparkles className="h-4 w-4 text-muted-foreground" />
                  <div>
                    <p className="text-sm font-medium">{uploadResult.stats.embeddings_created}</p>
                    <p className="text-xs text-muted-foreground">Embeddings</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Tag className="h-4 w-4 text-muted-foreground" />
                  <div>
                    <p className="text-sm font-medium">{uploadResult.stats.summaries_created}</p>
                    <p className="text-xs text-muted-foreground">Summaries</p>
                  </div>
                </div>
              </div>

              {uploadResult.warnings && uploadResult.warnings.length > 0 && (
                <Alert>
                  <AlertCircle className="h-4 w-4" />
                  <AlertTitle>Warnings</AlertTitle>
                  <AlertDescription>
                    <ul className="list-disc list-inside space-y-1 mt-2">
                      {uploadResult.warnings.map((warning, idx) => (
                        <li key={idx} className="text-sm">{warning}</li>
                      ))}
                    </ul>
                  </AlertDescription>
                </Alert>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      <Button
        onClick={handleUpload}
        disabled={!file || isUploading || uploadSuccess}
        className="w-full"
      >
        {isUploading ? (
          <>
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            Processing...
          </>
        ) : uploadSuccess ? (
          <>
            <CheckCircle2 className="mr-2 h-4 w-4" />
            Imported
          </>
        ) : (
          <>
            <Upload className="mr-2 h-4 w-4" />
            Upload & Import
          </>
        )}
      </Button>

      {uploadSuccess && (
        <Button
          onClick={() => {
            setUploadSuccess(false);
            setUploadResult(null);
            setError(null);
            setUploadStep("idle");
            setFile(null);
          }}
          variant="outline"
          className="w-full"
        >
          Upload Another File
        </Button>
      )}
    </div>
  );
}

