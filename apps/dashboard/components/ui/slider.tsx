"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

export interface SliderProps extends Omit<React.HTMLAttributes<HTMLDivElement>, "onChange"> {
  value?: number[];
  onValueChange?: (value: number[]) => void;
  min?: number;
  max?: number;
  step?: number;
}

const Slider = React.forwardRef<HTMLDivElement, SliderProps>(
  ({ className, value = [0], onValueChange, min = 0, max = 100, step = 1, ...props }, ref) => {
    const currentValue = value[0] || min;
    const percentage = ((currentValue - min) / (max - min)) * 100;

    const handleMouseDown = (e: React.MouseEvent<HTMLDivElement>) => {
      const rect = e.currentTarget.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const percentage = (x / rect.width) * 100;
      const newValue = Math.round((percentage / 100) * (max - min) + min);
      const clampedValue = Math.max(min, Math.min(max, newValue));
      const steppedValue = Math.round(clampedValue / step) * step;
      onValueChange?.([steppedValue]);
    };

    return (
      <div
        ref={ref}
        className={cn("relative flex w-full touch-none select-none items-center", className)}
        {...props}
      >
        <div
          className="relative h-2 w-full grow overflow-hidden rounded-full bg-secondary"
          onMouseDown={handleMouseDown}
        >
          <div
            className="absolute h-full bg-primary transition-all"
            style={{ width: `${percentage}%` }}
          />
          <div
            className="absolute h-4 w-4 -translate-x-1/2 rounded-full border-2 border-primary bg-background shadow transition-all"
            style={{ left: `${percentage}%` }}
          />
        </div>
      </div>
    );
  }
);
Slider.displayName = "Slider";

export { Slider };

