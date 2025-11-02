"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { Loader2, Key, CheckCircle2, XCircle, Eye, EyeOff, Trash2 } from "lucide-react";
import { toast } from "sonner";
import {
  Alert,
  AlertDescription,
} from "@/components/ui/alert";

export function OpenAIConfig() {
  const [apiKey, setApiKey] = useState("");
  const [isValidating, setIsValidating] = useState(false);
  const [isChecking, setIsChecking] = useState(true);
  const [isConfigured, setIsConfigured] = useState(false);
  const [isValid, setIsValid] = useState(false);
  const [maskedKey, setMaskedKey] = useState<string | null>(null);
  const [showKey, setShowKey] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    checkStatus();
  }, []);

  const checkStatus = async () => {
    setIsChecking(true);
    try {
      const status = await api.getOpenAIStatus();
      setIsConfigured(status.configured);
      setIsValid(status.valid);
      setMaskedKey(status.masked_key || null);
      if (status.configured && status.masked_key) {
        // Pre-fill with masked key for editing
        setApiKey(status.masked_key);
      }
    } catch (error) {
      setIsConfigured(false);
      setIsValid(false);
      toast.error(error instanceof Error ? error.message : "Failed to check OpenAI status");
    } finally {
      setIsChecking(false);
    }
  };

  const handleValidate = async () => {
    if (!apiKey.trim()) {
      toast.error("Please enter an API key");
      return;
    }

    // If it's the masked key, don't try to validate
    if (apiKey.includes("...") || apiKey.length < 20) {
      toast.error("Please enter a complete API key (starts with 'sk-')");
      return;
    }

    setIsValidating(true);
    try {
      const result = await api.validateOpenAIKey(apiKey);
      
      if (result.valid && result.configured) {
        setIsConfigured(true);
        setIsValid(true);
        setMaskedKey(result.masked_key || null);
        setApiKey(""); // Clear input after successful save
        toast.success("OpenAI API key validated and saved successfully!");
        await checkStatus(); // Refresh status
      } else {
        setIsValid(false);
        toast.error(result.message || "Invalid API key");
      }
    } catch (error) {
      setIsValid(false);
      toast.error(error instanceof Error ? error.message : "Failed to validate API key");
    } finally {
      setIsValidating(false);
    }
  };

  const handleDelete = async () => {
    if (!confirm("Are you sure you want to remove the OpenAI API key? This will disable OpenAI models.")) {
      return;
    }

    setIsDeleting(true);
    try {
      await api.deleteOpenAIKey();
      setIsConfigured(false);
      setIsValid(false);
      setMaskedKey(null);
      setApiKey("");
      toast.success("OpenAI API key removed successfully");
      await checkStatus();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to remove API key");
    } finally {
      setIsDeleting(false);
    }
  };

  if (isChecking) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Key className="h-5 w-5" />
            <span>OpenAI API Key</span>
          </div>
          <Loader2 className="h-4 w-4 animate-spin" />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Key className="h-5 w-5" />
          <span>OpenAI API Key</span>
        </div>
        <div className="flex items-center gap-2">
          {isConfigured && (
            <>
              <Badge 
                variant={isValid ? "default" : "destructive"} 
                className={isValid ? "bg-green-600" : "bg-red-600"}
              >
                {isValid ? "Valid" : "Invalid"}
              </Badge>
            </>
          )}
          {!isConfigured && (
            <Badge variant="secondary">Not Configured</Badge>
          )}
        </div>
      </div>

      {isConfigured && isValid && (
        <Alert className="bg-green-50 dark:bg-green-950 border-green-200 dark:border-green-800">
          <CheckCircle2 className="h-4 w-4 text-green-600" />
          <AlertDescription className="text-green-800 dark:text-green-200">
            OpenAI API key is configured and validated. You can now use OpenAI models in the LLM provider settings.
          </AlertDescription>
        </Alert>
      )}

      {isConfigured && !isValid && (
        <Alert className="bg-yellow-50 dark:bg-yellow-950 border-yellow-200 dark:border-yellow-800">
          <XCircle className="h-4 w-4 text-yellow-600" />
          <AlertDescription className="text-yellow-800 dark:text-yellow-200">
            OpenAI API key is configured but validation failed. Please update it with a valid key.
          </AlertDescription>
        </Alert>
      )}

      {isConfigured && maskedKey && (
        <div className="space-y-2">
          <Label>Current API Key</Label>
          <div className="flex items-center gap-2">
            <Input
              type={showKey ? "text" : "password"}
              value={maskedKey}
              readOnly
              className="font-mono text-sm"
            />
            <Button
              type="button"
              variant="outline"
              size="icon"
              onClick={() => setShowKey(!showKey)}
            >
              {showKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">
            Your API key is securely stored. Enter a new key below to update it.
          </p>
        </div>
      )}

      <div className="space-y-2">
        <Label htmlFor="openai-key">
          {isConfigured ? "Update API Key" : "Enter API Key"}
        </Label>
        <div className="flex items-center gap-2">
          <Input
            id="openai-key"
            type={showKey ? "text" : "password"}
            placeholder={isConfigured ? "Enter new API key (sk-...)" : "sk-..."}
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            disabled={isValidating}
            className="font-mono"
          />
          <Button
            type="button"
            variant="outline"
            size="icon"
            onClick={() => setShowKey(!showKey)}
          >
            {showKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
          </Button>
        </div>
        <p className="text-xs text-muted-foreground">
          Your API key starts with "sk-" and is used to authenticate with OpenAI's API. 
          It will be validated before being saved.
        </p>
      </div>

      <div className="flex items-center gap-2">
        <Button
          onClick={handleValidate}
          disabled={isValidating || !apiKey.trim() || (apiKey.includes("...") && isConfigured)}
          className="flex-1"
        >
          {isValidating ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Validating...
            </>
          ) : (
            <>
              <Key className="mr-2 h-4 w-4" />
              {isConfigured ? "Update Key" : "Save & Validate"}
            </>
          )}
        </Button>

        {isConfigured && (
          <Button
            onClick={handleDelete}
            disabled={isDeleting}
            variant="destructive"
            size="icon"
          >
            {isDeleting ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Trash2 className="h-4 w-4" />
            )}
          </Button>
        )}
      </div>

      <div className="text-xs text-muted-foreground space-y-1">
        <p>
          • Get your API key from{" "}
          <a
            href="https://platform.openai.com/api-keys"
            target="_blank"
            rel="noopener noreferrer"
            className="text-primary hover:underline"
          >
            OpenAI Platform
          </a>
        </p>
        <p>• The key is validated before being saved to ensure it's working</p>
        <p>• Your key is encrypted and stored securely</p>
      </div>
    </div>
  );
}

