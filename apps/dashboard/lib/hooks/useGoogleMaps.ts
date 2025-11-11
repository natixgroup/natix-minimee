"use client";

import { useEffect, useState } from "react";

interface UseGoogleMapsResult {
  isLoaded: boolean;
  error: Error | null;
}

/**
 * Hook to dynamically load Google Maps JavaScript API with Places library
 * @param apiKey - Google Places API key (optional, will use env var if not provided)
 * @returns Object with isLoaded status and error state
 */
export function useGoogleMaps(apiKey?: string): UseGoogleMapsResult {
  const [isLoaded, setIsLoaded] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    // Check if already loaded
    if ((window as any).google?.maps?.places) {
      setIsLoaded(true);
      return;
    }

    // Get API key from parameter or environment
    const key = apiKey || process.env.NEXT_PUBLIC_GOOGLE_PLACES_API_KEY;

    if (!key) {
      setError(new Error("Google Places API key is not configured"));
      return;
    }

    // Check if script is already being loaded
    const existingScript = document.querySelector(
      'script[src*="maps.googleapis.com/maps/api/js"]'
    );

    if (existingScript) {
      // Script exists, wait for it to load
      existingScript.addEventListener("load", () => {
        if ((window as any).google?.maps?.places) {
          setIsLoaded(true);
        }
      });
      return;
    }

    // Create script element
    const script = document.createElement("script");
    script.src = `https://maps.googleapis.com/maps/api/js?key=${key}&libraries=places`;
    script.async = true;
    script.defer = true;

    script.onload = () => {
      if ((window as any).google?.maps?.places) {
        setIsLoaded(true);
        setError(null);
      } else {
        setError(new Error("Google Maps Places library failed to load"));
      }
    };

    script.onerror = () => {
      setError(new Error("Failed to load Google Maps JavaScript API"));
    };

    // Append to document head
    document.head.appendChild(script);

    // Cleanup function
    return () => {
      // Don't remove the script on unmount as it might be used by other components
      // The script will remain cached by the browser
    };
  }, [apiKey]);

  return { isLoaded, error };
}


