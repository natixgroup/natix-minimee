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
>(({ className, side = "top", sideOffset = 4, children, ...props }, ref) => {
  const context = React.useContext(TooltipContext)
  if (!context || !context.open) return null
  
  const sideClasses = {
    top: "bottom-full left-0 mb-2",
    right: "left-full top-0 ml-2",
    bottom: "top-full left-0 mt-2",
    left: "right-full top-0 mr-2",
  }
  
  return (
    <div
      ref={ref}
      className={cn(
        "absolute z-50 overflow-hidden rounded-md border bg-popover shadow-md",
        sideClasses[side],
        className
      )}
      style={{ 
        marginLeft: side === "left" ? `${sideOffset}px` : undefined, 
        marginRight: side === "right" ? `${sideOffset}px` : undefined, 
        marginTop: side === "bottom" ? `${sideOffset}px` : undefined, 
        marginBottom: side === "top" ? `${sideOffset}px` : undefined 
      }}
      {...props}
    >
      {children}
    </div>
  )
})
TooltipContent.displayName = "TooltipContent"

export { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider }

