import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { getCurrentUser, getAuthToken, setCurrentUser, setAuthToken, removeAuthToken, clearCurrentUser, type User } from "../auth";
import { getEnv } from "../env";
import { toast } from "sonner";

export function useAuth() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  useEffect(() => {
    // Check if user is authenticated on mount
    const token = getAuthToken();
    const currentUser = getCurrentUser();
    
    if (token && currentUser) {
      setUser(currentUser);
      setIsAuthenticated(true);
    }
    
    setIsLoading(false);
  }, []);

  const login = async (email: string, password: string) => {
    try {
      // Call backend login endpoint
      const apiUrl = getEnv().apiUrl;
      const response = await fetch(`${apiUrl}/auth/login`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ email, password }),
      });

      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: "Login failed" }));
        throw new Error(error.detail || "Login failed");
      }

      const data = await response.json();
      const { user, access_token } = data;

      // Store token and user
      setAuthToken(access_token);
      setCurrentUser(user);
      setUser(user);
      setIsAuthenticated(true);

      toast.success("Login successful");
      router.push("/");
      return { success: true };
    } catch (error) {
      const message = error instanceof Error ? error.message : "Login failed";
      toast.error(message);
      return { success: false, error: message };
    }
  };

  const signup = async (email: string, password: string, name?: string) => {
    try {
      const apiUrl = getEnv().apiUrl;
      const response = await fetch(`${apiUrl}/auth/signup`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ email, password, name }),
      });

      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: "Signup failed" }));
        throw new Error(error.detail || "Signup failed");
      }

      const data = await response.json();
      const { user, access_token } = data;

      // Store token and user
      setAuthToken(access_token);
      setCurrentUser(user);
      setUser(user);
      setIsAuthenticated(true);

      toast.success("Account created successfully");
      router.push("/");
      return { success: true };
    } catch (error) {
      const message = error instanceof Error ? error.message : "Signup failed";
      toast.error(message);
      return { success: false, error: message };
    }
  };

  const logout = () => {
    removeAuthToken();
    clearCurrentUser();
    setUser(null);
    setIsAuthenticated(false);
    toast.success("Logged out successfully");
    router.push("/auth/login");
  };

  const refreshUser = async () => {
    const token = getAuthToken();
    if (!token) return;

    try {
      const apiUrl = getEnv().apiUrl;
      const response = await fetch(`${apiUrl}/auth/me`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (response.ok) {
        const user = await response.json();
        setCurrentUser(user);
        setUser(user);
      }
    } catch (error) {
      console.error("Failed to refresh user:", error);
    }
  };

  return {
    user,
    isLoading,
    isAuthenticated,
    login,
    signup,
    logout,
    refreshUser,
  };
}

