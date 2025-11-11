"use client";

import { useState, useEffect } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface UserInfoFormProps {
  userInfo?: any | null;
  userId: number;
  onSubmit: (data: any) => void;
  onCancel: () => void;
}

const INFO_TYPES = [
  { value: "first_name", label: "First Name" },
  { value: "last_name", label: "Last Name" },
  { value: "birth_date", label: "Date of Birth" },
  { value: "address", label: "Address" },
  { value: "city", label: "City" },
  { value: "country", label: "Country" },
  { value: "phone", label: "Phone" },
  { value: "profession", label: "Profession" },
  { value: "company", label: "Company" },
  { value: "marital_status", label: "Marital Status" },
  { value: "spouse_name", label: "Spouse Name" },
  { value: "children", label: "Children" },
  { value: "education", label: "Education" },
  { value: "languages", label: "Languages" },
  { value: "interests", label: "Interests" },
  { value: "hobbies", label: "Hobbies" },
  { value: "humor_style", label: "Humor Style" },
  { value: "preferred_emojis", label: "Preferred Emojis" },
];

export function UserInfoForm({ userInfo, userId, onSubmit, onCancel }: UserInfoFormProps) {
  const [infoType, setInfoType] = useState(userInfo?.info_type || "");
  const [infoValue, setInfoValue] = useState(userInfo?.info_value || "");
  const [infoValueJson, setInfoValueJson] = useState<any>(userInfo?.info_value_json || null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    const data: any = {
      info_type: infoType,
    };

    // For array types, parse the value as JSON array
    const arrayTypes = ["languages", "interests", "hobbies", "preferred_emojis", "children"];
    if (arrayTypes.includes(infoType) && infoValue) {
      try {
        const items = infoValue.split(",").map((item) => item.trim()).filter(Boolean);
        data.info_value_json = items;
        data.info_value = items.join(", ");
      } catch (err) {
        toast.error("Invalid format for array type. Use comma-separated values.");
        return;
      }
    } else {
      data.info_value = infoValue;
    }

    onSubmit(data);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="info_type">Information Type</Label>
        <Select
          value={infoType}
          onValueChange={setInfoType}
          disabled={!!userInfo} // Can't change type when editing
          required
        >
          <SelectTrigger id="info_type">
            <SelectValue placeholder="Select information type" />
          </SelectTrigger>
          <SelectContent>
            {INFO_TYPES.map((type) => (
              <SelectItem key={type.value} value={type.value}>
                {type.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-2">
        <Label htmlFor="info_value">
          Value
          {["languages", "interests", "hobbies", "preferred_emojis", "children"].includes(infoType) && (
            <span className="text-muted-foreground text-sm ml-2">
              (comma-separated for multiple values)
            </span>
          )}
        </Label>
        {infoType === "children" ? (
          <Textarea
            id="info_value"
            value={infoValue}
            onChange={(e) => setInfoValue(e.target.value)}
            placeholder="e.g., 2 children: Alice (8 years old), Bob (5 years old)"
            rows={3}
          />
        ) : (
          <Input
            id="info_value"
            value={infoValue}
            onChange={(e) => setInfoValue(e.target.value)}
            placeholder="Enter value"
            required
          />
        )}
      </div>

      <div className="flex justify-end gap-2 pt-4">
        <Button type="button" variant="outline" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit">
          {userInfo ? "Update" : "Create"}
        </Button>
      </div>
    </form>
  );
}


