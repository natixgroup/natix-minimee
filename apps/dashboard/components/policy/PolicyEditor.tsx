"use client";

import { useState, useEffect } from "react";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { usePolicies, useCreatePolicy, useUpdatePolicy } from "@/lib/hooks/usePolicies";
import { Loader2, FileText } from "lucide-react";
import { toast } from "sonner";

export function PolicyEditor() {
  const { data: policies = [] } = usePolicies();
  const createPolicy = useCreatePolicy();
  const updatePolicy = useUpdatePolicy();

  const [policyName, setPolicyName] = useState("");
  const [policyJson, setPolicyJson] = useState("{}");
  const [selectedPolicyId, setSelectedPolicyId] = useState<number | null>(null);

  useEffect(() => {
    if (selectedPolicyId) {
      const policy = policies.find((p) => p.id === selectedPolicyId);
      if (policy) {
        setPolicyName(policy.name);
        setPolicyJson(JSON.stringify(policy.rules, null, 2));
      }
    } else {
      setPolicyName("");
      setPolicyJson("{}");
    }
  }, [selectedPolicyId, policies]);

  const handleSave = () => {
    try {
      const rules = JSON.parse(policyJson);
      if (!policyName.trim()) {
        toast.error("Policy name is required");
        return;
      }

      if (selectedPolicyId) {
        updatePolicy.mutate(
          {
            id: selectedPolicyId,
            data: { name: policyName, rules },
          },
          {
            onSuccess: () => {
              toast.success("Policy updated");
              setSelectedPolicyId(null);
            },
          }
        );
      } else {
        createPolicy.mutate(
          {
            name: policyName,
            rules,
            user_id: 1, // TODO: Get from auth
          },
          {
            onSuccess: () => {
              toast.success("Policy created");
              setPolicyName("");
              setPolicyJson("{}");
            },
          }
        );
      }
    } catch (error) {
      toast.error("Invalid JSON format");
    }
  };

  const isValidJson = () => {
    try {
      JSON.parse(policyJson);
      return true;
    } catch {
      return false;
    }
  };

  return (
    <div className="space-y-6">
      {/* Policy Editor Form */}
      <div className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="policy-name">Policy Name</Label>
          <Input
            id="policy-name"
            type="text"
            value={policyName}
            onChange={(e) => setPolicyName(e.target.value)}
            placeholder="e.g., Email Response Policy, WhatsApp Guidelines"
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="policy-json">Policy Rules (JSON)</Label>
          <Textarea
            id="policy-json"
            value={policyJson}
            onChange={(e) => setPolicyJson(e.target.value)}
            rows={14}
            className="font-mono text-sm"
            placeholder='{\n  "max_length": 500,\n  "tone": "professional",\n  "require_approval": true\n}'
          />
          {!isValidJson() && policyJson !== "{}" && (
            <p className="text-sm text-destructive">Invalid JSON format</p>
          )}
          <p className="text-xs text-muted-foreground">
            Define rules and constraints for agent behavior in JSON format
          </p>
        </div>

        <div className="flex gap-2">
          <Button
            onClick={handleSave}
            disabled={!isValidJson() || !policyName.trim() || createPolicy.isPending || updatePolicy.isPending}
          >
            {(createPolicy.isPending || updatePolicy.isPending) && (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            )}
            <FileText className="mr-2 h-4 w-4" />
            {selectedPolicyId ? "Update Policy" : "Create Policy"}
          </Button>
          {selectedPolicyId && (
            <Button
              variant="outline"
              onClick={() => {
                setSelectedPolicyId(null);
                setPolicyName("");
                setPolicyJson("{}");
              }}
            >
              New Policy
            </Button>
          )}
        </div>
      </div>

      {/* Existing Policies List */}
      {policies.length > 0 && (
        <div className="border-t pt-6">
          <div className="flex items-center justify-between mb-4">
            <Label className="text-base font-semibold">Existing Policies</Label>
            <span className="text-sm text-muted-foreground">{policies.length} policy(ies)</span>
          </div>
          <div className="space-y-2">
            {policies.map((policy) => (
              <div
                key={policy.id}
                onClick={() => setSelectedPolicyId(policy.id)}
                className={`flex items-center justify-between rounded-md border p-3 text-sm transition-colors cursor-pointer ${
                  selectedPolicyId === policy.id
                    ? "bg-accent border-primary"
                    : "hover:bg-accent/50"
                }`}
              >
                <div className="flex items-center gap-2">
                  <FileText className="h-4 w-4" />
                  <span className="font-medium">{policy.name}</span>
                </div>
                {selectedPolicyId === policy.id && (
                  <span className="text-xs text-muted-foreground">Selected</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

