"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Check, X } from "lucide-react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface ClassificationNotificationProps {
  notification: {
    contact_id: number;
    conversation_id: string;
    suggested_category_id: number;
    suggested_category_code: string;
    suggested_category_label: string;
    confidence: number;
    reasoning: string;
  };
  userId: number;
  onResolve: () => void;
}

export function ClassificationNotification({
  notification,
  userId,
  onResolve,
}: ClassificationNotificationProps) {
  const [selectedCategoryId, setSelectedCategoryId] = useState<number | null>(
    notification.suggested_category_id
  );
  const [categories, setCategories] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingCategories, setLoadingCategories] = useState(true);

  useEffect(() => {
    loadCategories();
  }, []);

  const loadCategories = async () => {
    try {
      setLoadingCategories(true);
      const data = await api.getContactCategories(userId);
      setCategories(data);
    } catch (err) {
      console.error("Failed to load categories:", err);
    } finally {
      setLoadingCategories(false);
    }
  };

  const handleAccept = async () => {
    try {
      setLoading(true);
      await api.updateContactCategory(notification.contact_id, userId, selectedCategoryId || undefined);
      onResolve();
    } catch (err: any) {
      alert(err.message || "Failed to accept classification");
    } finally {
      setLoading(false);
    }
  };

  const handleReject = async () => {
    try {
      setLoading(true);
      // Don't set any category (leave as null)
      await api.updateContactCategory(notification.contact_id, userId, undefined);
      onResolve();
    } catch (err: any) {
      alert(err.message || "Failed to reject classification");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">Contact Classification Suggestion</CardTitle>
          <Badge variant="outline" className="text-xs">
            {Math.round(notification.confidence * 100)}% confidence
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <p className="text-sm text-muted-foreground mb-2">Suggested category:</p>
          <p className="font-medium">{notification.suggested_category_label}</p>
        </div>

        {notification.reasoning && (
          <div>
            <p className="text-sm text-muted-foreground mb-1">Reasoning:</p>
            <p className="text-sm">{notification.reasoning}</p>
          </div>
        )}

        <div>
          <p className="text-sm text-muted-foreground mb-2">Select category:</p>
          <Select
            value={selectedCategoryId?.toString() || ""}
            onValueChange={(value) => setSelectedCategoryId(value ? parseInt(value) : null)}
            disabled={loadingCategories || loading}
          >
            <SelectTrigger>
              <SelectValue placeholder="Select category" />
            </SelectTrigger>
            <SelectContent>
              {categories.map((cat) => (
                <SelectItem key={cat.id} value={cat.id.toString()}>
                  {cat.label} {cat.is_system && "(System)"}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="flex gap-2">
          <Button
            onClick={handleAccept}
            disabled={loading || !selectedCategoryId}
            className="flex-1"
          >
            <Check className="h-4 w-4 mr-2" />
            Accept
          </Button>
          <Button
            onClick={handleReject}
            variant="outline"
            disabled={loading}
            className="flex-1"
          >
            <X className="h-4 w-4 mr-2" />
            Reject
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

