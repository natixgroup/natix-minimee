/**
 * Environment variables validation
 */
export function getEnv() {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";
  
  if (!apiUrl) {
    throw new Error("NEXT_PUBLIC_API_URL is not set");
  }
  
  const googlePlacesApiKey = process.env.NEXT_PUBLIC_GOOGLE_PLACES_API_KEY;
  
  return {
    apiUrl,
    googlePlacesApiKey,
  };
}

