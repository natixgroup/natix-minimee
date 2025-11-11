"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Plus, Trash2 } from "lucide-react";
import { CategoryButtons } from "./CategoryButtons";

interface Email {
  id: string;
  address: string;
  tags: string[];
}

interface EmailInputProps {
  emails: Email[];
  onChange: (emails: Email[]) => void;
}

const AVAILABLE_EMAIL_TAGS = [
  "Personal",
  "Work",
  "Family",
  "Newsletter",
  "Shopping",
  "Social",
  "Primary",
];

export function EmailInput({ emails, onChange }: EmailInputProps) {
  const [newEmail, setNewEmail] = useState("");

  const handleAdd = () => {
    if (newEmail.trim() && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(newEmail.trim())) {
      onChange([
        ...emails,
        {
          id: Date.now().toString(),
          address: newEmail.trim(),
          tags: [],
        },
      ]);
      setNewEmail("");
    }
  };

  const handleUpdate = (id: string, updates: Partial<Email>) => {
    onChange(emails.map((e) => (e.id === id ? { ...e, ...updates } : e)));
  };

  const handleDelete = (id: string) => {
    onChange(emails.filter((e) => e.id !== id));
  };

  return (
    <div className="space-y-3">
      {emails.map((email) => (
        <div key={email.id} className="border rounded-lg p-3 space-y-2">
          <div className="flex items-start justify-between gap-2">
            <div className="flex-1">
              <div className="font-medium text-sm mb-2">{email.address}</div>
              <CategoryButtons
                categories={AVAILABLE_EMAIL_TAGS}
                selected={email.tags}
                onChange={(selected) => handleUpdate(email.id, { tags: selected })}
              />
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => handleDelete(email.id)}
              className="h-8 w-8 p-0"
            >
              <Trash2 className="h-4 w-4 text-destructive" />
            </Button>
          </div>
        </div>
      ))}

      <div className="border-2 border-dashed rounded-lg p-3">
        <div className="flex gap-2">
          <Input
            type="email"
            value={newEmail}
            onChange={(e) => setNewEmail(e.target.value)}
            placeholder="email@example.com"
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                handleAdd();
              }
            }}
            className="flex-1"
          />
          <Button onClick={handleAdd} size="sm">
            <Plus className="h-4 w-4 mr-1" />
            Add
          </Button>
        </div>
      </div>
    </div>
  );
}

