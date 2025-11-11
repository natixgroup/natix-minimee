"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Plus, Trash2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";

interface VisibilityManagerProps {
  userInfo: any;
  userId: number;
  visibilities: any[];
  onReload: () => void;
}

export function VisibilityManager({
  userInfo,
  userId,
  visibilities,
  onReload,
}: VisibilityManagerProps) {
  const [relationTypes, setRelationTypes] = useState<any[]>([]);
  const [contacts, setContacts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadRelationTypes();
    // TODO: Load contacts if needed
    setLoading(false);
  }, []);

  const loadRelationTypes = async () => {
    try {
      // TODO: Use proper API endpoint for relation types
      // For now, using a placeholder
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/ingest/relation-types`);
      if (response.ok) {
        const data = await response.json();
        setRelationTypes(data);
      }
    } catch (err) {
      console.error("Failed to load relation types:", err);
    }
  };

  const handleCreateVisibility = async () => {
    try {
      await api.createUserInfoVisibility(userInfo.id, userId, {
        relation_type_id: null,
        contact_id: null,
        can_use_for_response: false,
        can_say_explicitly: false,
        forbidden_for_response: false,
        forbidden_to_say: false,
      });
      onReload();
    } catch (err: any) {
      const errorMessage = err instanceof Error ? err.message : String(err?.message || "Failed to create visibility rule");
      toast.error(errorMessage);
    }
  };

  const handleUpdateVisibility = async (visibilityId: number, updates: any) => {
    try {
      await api.updateUserInfoVisibility(userInfo.id, visibilityId, userId, updates);
      onReload();
    } catch (err: any) {
      const errorMessage = err instanceof Error ? err.message : String(err?.message || "Failed to update visibility rule");
      toast.error(errorMessage);
    }
  };

  const handleDeleteVisibility = async (visibilityId: number) => {
    if (!confirm("Are you sure you want to delete this visibility rule?")) {
      return;
    }
    try {
      await api.deleteUserInfoVisibility(userInfo.id, visibilityId, userId);
      onReload();
    } catch (err: any) {
      const errorMessage = err instanceof Error ? err.message : String(err?.message || "Failed to delete visibility rule");
      toast.error(errorMessage);
    }
  };

  const getVisibilityLabel = (visibility: any) => {
    if (visibility.contact_id) {
      return `Contact #${visibility.contact_id}`;
    }
    if (visibility.relation_type_id) {
      const rt = relationTypes.find((r) => r.id === visibility.relation_type_id);
      return rt ? rt.label_masculin || rt.code : `Relation Type #${visibility.relation_type_id}`;
    }
    return "Global (all contacts)";
  };

  if (loading) {
    return <div>Loading...</div>;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-semibold">{userInfo.info_type.replace(/_/g, " ")}</h3>
          <p className="text-sm text-muted-foreground">{userInfo.info_value || "No value"}</p>
        </div>
        <Button onClick={handleCreateVisibility} size="sm">
          <Plus className="h-4 w-4 mr-2" />
          Add Rule
        </Button>
      </div>

      <div className="space-y-3">
        {visibilities.length === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-4">
            No visibility rules. Click "Add Rule" to create one.
          </p>
        ) : (
          visibilities.map((visibility) => (
            <Card key={visibility.id}>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-sm">
                    {getVisibilityLabel(visibility)}
                  </CardTitle>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleDeleteVisibility(visibility.id)}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <Label htmlFor={`use-${visibility.id}`} className="text-sm">
                        Can Use for Response
                      </Label>
                      <Switch
                        id={`use-${visibility.id}`}
                        checked={visibility.can_use_for_response}
                        onCheckedChange={(checked) =>
                          handleUpdateVisibility(visibility.id, {
                            can_use_for_response: checked,
                          })
                        }
                      />
                    </div>
                    <p className="text-xs text-muted-foreground">
                      Allow using this info to inform responses
                    </p>
                  </div>

                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <Label htmlFor={`say-${visibility.id}`} className="text-sm">
                        Can Say Explicitly
                      </Label>
                      <Switch
                        id={`say-${visibility.id}`}
                        checked={visibility.can_say_explicitly}
                        onCheckedChange={(checked) =>
                          handleUpdateVisibility(visibility.id, {
                            can_say_explicitly: checked,
                          })
                        }
                      />
                    </div>
                    <p className="text-xs text-muted-foreground">
                      Allow explicitly mentioning this info
                    </p>
                  </div>

                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <Label htmlFor={`forbidden-use-${visibility.id}`} className="text-sm">
                        Forbidden for Response
                      </Label>
                      <Switch
                        id={`forbidden-use-${visibility.id}`}
                        checked={visibility.forbidden_for_response}
                        onCheckedChange={(checked) =>
                          handleUpdateVisibility(visibility.id, {
                            forbidden_for_response: checked,
                          })
                        }
                      />
                    </div>
                    <p className="text-xs text-muted-foreground">
                      Prevent using this info in responses
                    </p>
                  </div>

                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <Label htmlFor={`forbidden-say-${visibility.id}`} className="text-sm">
                        Forbidden to Say
                      </Label>
                      <Switch
                        id={`forbidden-say-${visibility.id}`}
                        checked={visibility.forbidden_to_say}
                        onCheckedChange={(checked) =>
                          handleUpdateVisibility(visibility.id, {
                            forbidden_to_say: checked,
                          })
                        }
                      />
                    </div>
                    <p className="text-xs text-muted-foreground">
                      Prevent explicitly mentioning this info
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))
        )}
      </div>
    </div>
  );
}


