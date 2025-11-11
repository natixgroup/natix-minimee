"use client";

import { useState, useEffect } from "react";
import { IngestionProgressFloating } from "./IngestionProgressFloating";
import { api } from "@/lib/api";

/**
 * Global component that displays active ingestion jobs from localStorage
 * This ensures progress indicators persist across page navigation
 */
export function GlobalIngestionProgress() {
  const [activeJobId, setActiveJobId] = useState<number | null>(null);
  const [jobTitle, setJobTitle] = useState<string>("Import en cours");

  const getJobTitle = (progress: any): string => {
    if (!progress) return "Import en cours";
    
    const source = progress.source;
    if (source === "gmail") {
      const days = progress.days || 30;
      return `Gmail - ${days} derniers jours`;
    } else if (source === "whatsapp") {
      const contactName = progress.contact_name;
      if (contactName) {
        return `WhatsApp - ${contactName}`;
      } else {
        return "WhatsApp - Import";
      }
    }
    return "Import en cours";
  };

  const fetchJobInfo = async (jobId: number) => {
    try {
      const job = await api.getIngestionJob(jobId);
      setJobTitle(getJobTitle(job.progress));
    } catch (error) {
      console.error("Failed to fetch job info:", error);
      setJobTitle("Import en cours");
    }
  };

  useEffect(() => {
    // Check localStorage for active job on mount
    const savedJobId = localStorage.getItem("activeIngestionJobId");
    if (savedJobId) {
      const jobId = parseInt(savedJobId);
      if (!isNaN(jobId)) {
        setActiveJobId(jobId);
        fetchJobInfo(jobId);
      }
    }

    // Listen for new jobs from other components
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === "activeIngestionJobId") {
        if (e.newValue) {
          const jobId = parseInt(e.newValue);
          if (!isNaN(jobId)) {
            setActiveJobId(jobId);
            fetchJobInfo(jobId);
          }
        } else {
          setActiveJobId(null);
        }
      }
    };

    // Listen for custom events (for same-tab communication)
    const handleJobStart = (e: CustomEvent<{ jobId: number }>) => {
      const jobId = e.detail.jobId;
      setActiveJobId(jobId);
      fetchJobInfo(jobId);
    };

    const handleJobComplete = () => {
      setActiveJobId(null);
    };

    window.addEventListener("storage", handleStorageChange);
    window.addEventListener("ingestionJobStart", handleJobStart as EventListener);
    window.addEventListener("ingestionJobComplete", handleJobComplete);

    return () => {
      window.removeEventListener("storage", handleStorageChange);
      window.removeEventListener("ingestionJobStart", handleJobStart as EventListener);
      window.removeEventListener("ingestionJobComplete", handleJobComplete);
    };
  }, []);

  const handleClose = () => {
    setActiveJobId(null);
    localStorage.removeItem("activeIngestionJobId");
  };

  if (!activeJobId) {
    return null;
  }

  const handleProgressUpdate = (progress: any) => {
    // Update title if metadata is available in progress
    if (progress && (progress.source === "gmail" || progress.source === "whatsapp")) {
      setJobTitle(getJobTitle(progress));
    }
  };

  return (
    <IngestionProgressFloating
      jobId={activeJobId}
      fileName={jobTitle}
      onClose={handleClose}
      onProgressUpdate={handleProgressUpdate}
    />
  );
}

