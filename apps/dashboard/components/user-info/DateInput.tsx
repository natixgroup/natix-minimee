"use client";

import { Input } from "@/components/ui/input";
import { forwardRef } from "react";

interface DateInputProps extends React.ComponentProps<"input"> {
  value: string;
  onChange: (value: string) => void;
}

export const DateInput = forwardRef<HTMLInputElement, DateInputProps>(
  ({ value, onChange, ...props }, ref) => {
    const formatDate = (input: string): string => {
      // Remove all non-digits
      const digits = input.replace(/\D/g, "");
      
      // Format as DD/MM/YYYY
      if (digits.length <= 2) {
        return digits;
      } else if (digits.length <= 4) {
        return `${digits.slice(0, 2)}/${digits.slice(2)}`;
      } else {
        return `${digits.slice(0, 2)}/${digits.slice(2, 4)}/${digits.slice(4, 8)}`;
      }
    };

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      const formatted = formatDate(e.target.value);
      onChange(formatted);
    };

    return (
      <Input
        ref={ref}
        value={value}
        onChange={handleChange}
        placeholder="DD/MM/YYYY"
        maxLength={10}
        {...props}
      />
    );
  }
);

DateInput.displayName = "DateInput";


