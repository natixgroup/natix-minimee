"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";

interface Tag {
  id: string;
  label: string;
}

interface TagInputProps {
  tags: Tag[];
  availableTags: string[];
  onTagsChange: (tags: Tag[]) => void;
  placeholder?: string;
}

export function TagInput({ tags, availableTags, onTagsChange, placeholder }: TagInputProps) {
  const [inputValue, setInputValue] = useState("");
  const [showSuggestions, setShowSuggestions] = useState(false);

  const handleAddTag = (tagLabel: string) => {
    if (tagLabel.trim() && !tags.some((t) => t.label === tagLabel)) {
      onTagsChange([...tags, { id: Date.now().toString(), label: tagLabel.trim() }]);
      setInputValue("");
      setShowSuggestions(false);
    }
  };

  const handleRemoveTag = (tagId: string) => {
    onTagsChange(tags.filter((t) => t.id !== tagId));
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && inputValue.trim()) {
      e.preventDefault();
      handleAddTag(inputValue);
    } else if (e.key === "Escape") {
      setShowSuggestions(false);
    }
  };

  const filteredSuggestions = availableTags.filter(
    (tag) => !tags.some((t) => t.label === tag) && tag.toLowerCase().includes(inputValue.toLowerCase())
  );

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-2 min-h-[32px] p-2 border rounded-md">
        {tags.map((tag) => (
          <Badge key={tag.id} variant="secondary" className="flex items-center gap-1">
            {tag.label}
            <button
              type="button"
              onClick={() => handleRemoveTag(tag.id)}
              className="ml-1 hover:bg-destructive/20 rounded-full p-0.5"
            >
              <X className="h-3 w-3" />
            </button>
          </Badge>
        ))}
        <div className="relative flex-1 min-w-[120px]">
          <Input
            value={inputValue}
            onChange={(e) => {
              setInputValue(e.target.value);
              setShowSuggestions(true);
            }}
            onFocus={() => setShowSuggestions(true)}
            onKeyDown={handleKeyDown}
            placeholder={tags.length === 0 ? (placeholder || "Type and press Enter") : ""}
            className="border-0 focus-visible:ring-0 h-auto p-0"
          />
          {showSuggestions && filteredSuggestions.length > 0 && (
            <div className="absolute z-10 mt-1 w-full bg-popover border rounded-md shadow-md max-h-40 overflow-auto">
              {filteredSuggestions.map((suggestion) => (
                <button
                  key={suggestion}
                  type="button"
                  onClick={() => handleAddTag(suggestion)}
                  className="w-full text-left px-3 py-2 hover:bg-accent text-sm"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

