"use client";

import { Button } from "@/components/ui/button";
import { Check } from "lucide-react";
import { cn } from "@/lib/utils";

interface CategoryButtonsProps {
  categories: string[];
  selected: string[];
  onChange: (selected: string[]) => void;
  className?: string;
}

export function CategoryButtons({
  categories,
  selected,
  onChange,
  className,
}: CategoryButtonsProps) {
  const handleToggle = (category: string) => {
    if (selected.includes(category)) {
      onChange(selected.filter((c) => c !== category));
    } else {
      onChange([...selected, category]);
    }
  };

  return (
    <div className={cn("flex flex-wrap gap-2", className)}>
      {categories.map((category) => {
        const isSelected = selected.includes(category);
        return (
          <Button
            key={category}
            type="button"
            variant={isSelected ? "default" : "outline"}
            size="sm"
            onClick={() => handleToggle(category)}
            className="h-8"
          >
            {isSelected && <Check className="h-3 w-3 mr-1" />}
            {category}
          </Button>
        );
      })}
    </div>
  );
}


