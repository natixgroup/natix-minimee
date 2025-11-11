"use client";

import { ErrorBoundary } from "@/components/errors/ErrorBoundary";

export function ErrorBoundaryWrapper({ children }: { children: React.ReactNode }) {
  return <ErrorBoundary>{children}</ErrorBoundary>;
}


