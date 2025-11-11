"use client";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Check, X } from "lucide-react";

interface SelectInputProps {
  options: { value: string; label: string }[];
  selected: string[];
  onChange: (selected: string[]) => void | Promise<void>;
  multiple?: boolean;
  placeholder?: string;
}

export function SelectInput({
  options,
  selected,
  onChange,
  multiple = false,
  placeholder = "Select...",
}: SelectInputProps) {
  const handleToggle = async (value: string) => {
    let newSelected: string[];
    if (multiple) {
      if (selected.includes(value)) {
        newSelected = selected.filter((v) => v !== value);
      } else {
        newSelected = [...selected, value];
      }
    } else {
      newSelected = [value];
    }
    
    try {
      await onChange(newSelected);
    } catch (err) {
      // Error should be handled by the onChange callback
      console.error("Error in SelectInput onChange:", err);
    }
  };

  return (
    <div className="space-y-2">
      {selected.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {selected.map((value) => {
            const option = options.find((o) => o.value === value);
            return (
              <Badge key={value} variant="secondary" className="flex items-center gap-1">
                {option?.label || value}
                {multiple && (
                  <button
                    type="button"
                    onClick={() => handleToggle(value)}
                    className="ml-1 hover:bg-destructive/20 rounded-full p-0.5"
                  >
                    <X className="h-3 w-3" />
                  </button>
                )}
              </Badge>
            );
          })}
        </div>
      )}

      <div className="grid grid-cols-2 gap-2">
        {options.map((option) => {
          const isSelected = selected.includes(option.value);
          return (
            <Button
              key={option.value}
              type="button"
              variant={isSelected ? "default" : "outline"}
              onClick={() => handleToggle(option.value)}
              className="justify-start"
            >
              {isSelected && <Check className="h-4 w-4 mr-2" />}
              {option.label}
            </Button>
          );
        })}
      </div>
    </div>
  );
}


