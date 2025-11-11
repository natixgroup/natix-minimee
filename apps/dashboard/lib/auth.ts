/**
 * Authentication utilities and NextAuth configuration
 */
import { getEnv } from "./env";

export const API_URL = getEnv().apiUrl;

export interface User {
  id: number;
  email: string;
  name: string | null;
  avatar_url?: string | null;
  created_at: string;
  updated_at: string;
}

export interface AuthSession {
  user: User;
  accessToken: string;
}

/**
 * Get authentication token from session
 */
export function getAuthToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("auth_token");
}

/**
 * Set authentication token
 */
export function setAuthToken(token: string): void {
  if (typeof window === "undefined") return;
  localStorage.setItem("auth_token", token);
}

/**
 * Remove authentication token
 */
export function removeAuthToken(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem("auth_token");
}

/**
 * Get current user from localStorage
 */
export function getCurrentUser(): User | null {
  if (typeof window === "undefined") return null;
  const userStr = localStorage.getItem("current_user");
  if (!userStr) return null;
  try {
    return JSON.parse(userStr);
  } catch {
    return null;
  }
}

/**
 * Set current user
 */
export function setCurrentUser(user: User): void {
  if (typeof window === "undefined") return;
  localStorage.setItem("current_user", JSON.stringify(user));
}

/**
 * Clear current user
 */
export function clearCurrentUser(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem("current_user");
}

