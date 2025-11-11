"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Plus, X, Trash2 } from "lucide-react";
import { CategoryButtons } from "./CategoryButtons";

interface Phone {
  id: string;
  number: string;
  tags: string[];
}

interface PhoneInputProps {
  phones: Phone[];
  onChange: (phones: Phone[]) => void;
}

const AVAILABLE_PHONE_TAGS = [
  "Personal",
  "Work",
  "Home",
  "Mobile",
  "WhatsApp",
  "WhatsApp Business",
  "Telegram",
  "Signal",
];

const COUNTRY_CODES = [
  { code: "+1", country: "US/CA" },
  { code: "+33", country: "FR" },
  { code: "+44", country: "UK" },
  { code: "+49", country: "DE" },
  { code: "+34", country: "ES" },
  { code: "+39", country: "IT" },
  { code: "+32", country: "BE" },
  { code: "+41", country: "CH" },
  { code: "+31", country: "NL" },
  { code: "+351", country: "PT" },
];

export function PhoneInput({ phones, onChange }: PhoneInputProps) {
  const [newNumber, setNewNumber] = useState("");
  const [newCountryCode, setNewCountryCode] = useState("+33");

  const handleAdd = () => {
    if (newNumber.trim()) {
      onChange([
        ...phones,
        {
          id: Date.now().toString(),
          number: `${newCountryCode} ${newNumber.trim()}`,
          tags: [],
        },
      ]);
      setNewNumber("");
      setNewCountryCode("+33");
    }
  };

  const handleUpdate = (id: string, updates: Partial<Phone>) => {
    onChange(phones.map((p) => (p.id === id ? { ...p, ...updates } : p)));
  };

  const handleDelete = (id: string) => {
    onChange(phones.filter((p) => p.id !== id));
  };

  return (
    <div className="space-y-3">
      {phones.map((phone) => (
        <div key={phone.id} className="border rounded-lg p-3 space-y-2">
          <div className="flex items-start justify-between gap-2">
            <div className="flex-1">
              <div className="font-medium text-sm mb-2">{phone.number}</div>
              <CategoryButtons
                categories={AVAILABLE_PHONE_TAGS}
                selected={phone.tags}
                onChange={(selected) => handleUpdate(phone.id, { tags: selected })}
              />
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => handleDelete(phone.id)}
              className="h-8 w-8 p-0"
            >
              <Trash2 className="h-4 w-4 text-destructive" />
            </Button>
          </div>
        </div>
      ))}

      <div className="border-2 border-dashed rounded-lg p-3 space-y-2">
        <div className="flex gap-2">
          <select
            value={newCountryCode}
            onChange={(e) => setNewCountryCode(e.target.value)}
            className="px-3 py-2 border rounded-md text-sm"
          >
            {COUNTRY_CODES.map((cc) => (
              <option key={cc.code} value={cc.code}>
                {cc.code} ({cc.country})
              </option>
            ))}
          </select>
          <Input
            value={newNumber}
            onChange={(e) => setNewNumber(e.target.value)}
            placeholder="Phone number"
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

