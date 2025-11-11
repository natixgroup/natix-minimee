"use client";

import { useState, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Upload, CheckCircle2, Loader2, AlertCircle, FileText } from "lucide-react";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { ContactFormDialog } from "./ContactFormDialog";
import { useAuth } from "@/lib/hooks/useAuth";

export function WhatsAppUpload() {
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const dropZoneRef = useRef<HTMLDivElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [isDetecting, setIsDetecting] = useState(false);
  const [showContactForm, setShowContactForm] = useState(false);
  const [contactData, setContactData] = useState<any>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [contactId, setContactId] = useState<number | null>(null);
  const [activeJobId, setActiveJobId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const { user } = useAuth();
  const userId = user?.id;

  const validateAndSetFile = (selectedFile: File | null) => {
    if (!selectedFile) {
      setFile(null);
      return false;
    }

    if (!selectedFile.name.endsWith(".txt")) {
      toast.error("Please select a .txt file");
      setFile(null);
      return false;
    }

    setFile(selectedFile);
    setError(null);
    setContactData(null);
    setShowContactForm(false);
    setActiveJobId(null);
    return true;
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    validateAndSetFile(selectedFile || null);
  };

  const handleUpload = async () => {
    if (!file) {
      toast.error("Please select a file first");
      return;
    }

    setIsDetecting(true);
    setError(null);

    try {
      // Step 1: Detect contact
      const detected = await api.detectContact(file, userId);
      setContactData(detected);
      
      // Generate conversation_id
      const convId = `whatsapp_${Date.now()}`;
      setConversationId(convId);
      
      // Step 2: Show contact form
      setShowContactForm(true);
    } catch (error: any) {
      // Extract error message properly
      let errorMessage = "Failed to detect contact";
      if (error instanceof Error) {
        errorMessage = error.message;
      } else if (error?.message) {
        errorMessage = error.message;
      } else if (typeof error === 'string') {
        errorMessage = error;
      } else {
        errorMessage = JSON.stringify(error);
      }
      setError(errorMessage);
      toast.error(errorMessage);
    } finally {
      setIsDetecting(false);
    }
  };

  const handleContactSave = async (formData: any) => {
    if (!conversationId) {
      toast.error("No conversation ID");
      return;
    }

    try {
      // Save contact
      const saved = await api.saveContact({
        user_id: userId,
        conversation_id: conversationId,
        ...formData,
      });
      
      setContactId(saved.id);
      setShowContactForm(false);
      
      // Step 3: Start async ingestion job
      const job = await api.uploadWhatsAppAsync(
        file!,
        userId,
        conversationId,
        saved.id
      );
      
      const jobId = job.job_id;
      setActiveJobId(jobId);
      
      // Store in localStorage for global component
      localStorage.setItem("activeIngestionJobId", jobId.toString());
      
      // Dispatch custom event for same-tab communication
      window.dispatchEvent(new CustomEvent("ingestionJobStart", { detail: { jobId } }));
      
      // Invalidate queries
      queryClient.invalidateQueries({
        queryKey: ["whatsapp-import-history"],
        exact: false,
      });
    } catch (error: any) {
      // Extract error message properly
      let errorMessage = "Failed to start import";
      if (error instanceof Error) {
        errorMessage = error.message;
      } else if (error?.message) {
        errorMessage = error.message;
      } else if (typeof error === 'string') {
        errorMessage = error;
      } else {
        errorMessage = JSON.stringify(error);
      }
      setError(errorMessage);
      toast.error(errorMessage);
    }
  };

  const handleCloseProgress = () => {
    setActiveJobId(null);
    localStorage.removeItem("activeIngestionJobId");
    setFile(null);
    setContactData(null);
    setConversationId(null);
    setContactId(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };


  const handleChooseFile = (e?: React.MouseEvent) => {
    if (e) {
      e.preventDefault();
      e.stopPropagation();
    }
    if (fileInputRef.current && !isDetecting && !activeJobId) {
      // Reset input to allow selecting same file again
      fileInputRef.current.value = "";
      // Use setTimeout to ensure the click happens after state updates
      setTimeout(() => {
        fileInputRef.current?.click();
      }, 0);
    }
  };

  const handleDragEnter = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    // Only set dragging to false if we're leaving the drop zone itself
    if (!dropZoneRef.current?.contains(e.relatedTarget as Node)) {
      setIsDragging(false);
    }
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    const droppedFiles = e.dataTransfer.files;
    if (droppedFiles.length > 0) {
      validateAndSetFile(droppedFiles[0]);
    }
  };

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Input
          ref={fileInputRef}
          type="file"
          accept=".txt"
          onChange={handleFileChange}
          className="absolute opacity-0 w-0 h-0 pointer-events-none"
          disabled={isDetecting || !!activeJobId}
          id="whatsapp-file-input"
        />
        
        {/* Drop Zone */}
        <div
          ref={dropZoneRef}
          onDragEnter={handleDragEnter}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            if (!isDetecting && !activeJobId) {
              handleChooseFile();
            }
          }}
          className={`
            relative border-2 border-dashed rounded-lg p-8 text-center cursor-pointer
            transition-all duration-200
            ${isDragging 
              ? "border-primary bg-primary/5 scale-[1.02]" 
              : "border-muted-foreground/25 hover:border-muted-foreground/50"
            }
            ${isDetecting ? "opacity-50 cursor-not-allowed pointer-events-none" : ""}
          `}
          role="button"
          tabIndex={isDetecting || activeJobId ? -1 : 0}
          onKeyDown={(e) => {
            if ((e.key === 'Enter' || e.key === ' ') && !isDetecting) {
              e.preventDefault();
              handleChooseFile();
            }
          }}
        >
          <div className="flex flex-col items-center gap-4">
            <div className={`
              rounded-full p-3
              ${isDragging ? "bg-primary/10" : "bg-muted"}
            `}>
              <FileText className={`h-6 w-6 ${isDragging ? "text-primary" : "text-muted-foreground"}`} />
            </div>
            {file ? (
              <div className="space-y-2 w-full">
                <div className="flex items-center justify-center gap-2">
                  <FileText className="h-5 w-5 text-primary" />
                  <p className="text-sm font-medium text-primary">{file.name}</p>
                </div>
                <p className="text-xs text-muted-foreground">
                  {(file.size / 1024).toFixed(2)} KB
                </p>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={(e) => {
                    e.stopPropagation();
                    setFile(null);
                    if (fileInputRef.current) {
                      fileInputRef.current.value = "";
                    }
                  }}
                  disabled={isDetecting || !!activeJobId}
                  className="text-xs"
                >
                  Remove file
                </Button>
              </div>
            ) : (
              <>
                <div className="space-y-1">
                  <p className="text-sm font-medium">
                    <span className="text-primary">Click to upload</span> or drag and drop
                  </p>
                  <p className="text-xs text-muted-foreground">
                    WhatsApp conversation export (.txt file). Maximum size: 50MB
                  </p>
                </div>
                <Button
                  type="button"
                  variant="outline"
                  onClick={(e) => {
                    e.stopPropagation();
                    e.preventDefault();
                    handleChooseFile(e);
                  }}
                  disabled={isDetecting || !!activeJobId}
                  size="sm"
                >
                  Browse Files
                </Button>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Error display */}
      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Contact Form Dialog */}
      {showContactForm && contactData && conversationId && (
        <ContactFormDialog
          open={showContactForm}
          onClose={() => {
            setShowContactForm(false);
            setContactData(null);
          }}
          onSave={handleContactSave}
          initialData={contactData}
          conversationId={conversationId}
          userId={userId}
        />
      )}


      <Button
        onClick={handleUpload}
        disabled={!file || isDetecting || !!activeJobId}
        className="w-full"
      >
        {isDetecting ? (
          <>
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            Detecting contact...
          </>
        ) : activeJobId ? (
          <>
            <CheckCircle2 className="mr-2 h-4 w-4" />
            Import in progress
          </>
        ) : (
          <>
            <Upload className="mr-2 h-4 w-4" />
            Start Import
          </>
        )}
      </Button>
    </div>
  );
}

