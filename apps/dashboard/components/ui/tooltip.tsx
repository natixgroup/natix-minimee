"use client"

import * as React from "react"
import { cn } from "@/lib/utils"

interface TooltipContextType {
  open: boolean
  setOpen: (open: boolean) => void
}

const TooltipContext = React.createContext<TooltipContextType | undefined>(undefined)

const TooltipProvider = ({ children, delayDuration = 200 }: { children: React.ReactNode, delayDuration?: number }) => {
  return <>{children}</>
}

const Tooltip = ({ children, delayDuration = 200 }: { children: React.ReactNode, delayDuration?: number }) => {
  const [open, setOpen] = React.useState(false)
  return (
    <TooltipContext.Provider value={{ open, setOpen }}>
      {children}
    </TooltipContext.Provider>
  )
}

const TooltipTrigger = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement> & { asChild?: boolean }
>(({ className, children, asChild, ...props }, ref) => {
  const context = React.useContext(TooltipContext)
  if (!context) return <>{children}</>
  
  return (
    <div
      ref={ref}
      className={cn("cursor-help", className)}
      onMouseEnter={() => context.setOpen(true)}
      onMouseLeave={() => context.setOpen(false)}
      {...props}
    >
      {children}
    </div>
  )
})
TooltipTrigger.displayName = "TooltipTrigger"

const TooltipContent = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement> & { side?: "top" | "right" | "bottom" | "left"; sideOffset?: number }
>(({ className, side = "right", sideOffset = 8, children, ...props }, ref) => {
  const context = React.useContext(TooltipContext)
  if (!context || !context.open) return null
  
  const sideClasses = {
    top: "bottom-full left-1/2 -translate-x-1/2 mb-2",
    right: "left-full top-1/2 -translate-y-1/2 ml-2",
    bottom: "top-full left-1/2 -translate-x-1/2 mt-2",
    left: "right-full top-1/2 -translate-y-1/2 mr-2",
  }
  
  return (
    <div
      ref={ref}
      className={cn(
        "absolute z-[9999] overflow-hidden rounded-md border bg-popover shadow-lg text-popover-foreground",
        sideClasses[side],
        className
      )}
      style={{ 
        minWidth: side === "right" || side === "left" ? "400px" : undefined,
        maxWidth: side === "right" || side === "left" ? "600px" : "80vw",
      }}
      onMouseEnter={() => context.setOpen(true)}
      onMouseLeave={() => context.setOpen(false)}
      {...props}
    >
      {children}
    </div>
  )
})
TooltipContent.displayName = "TooltipContent"

export { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider }

