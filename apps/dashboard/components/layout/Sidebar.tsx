"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { Home, Bot, FileText, Settings, Moon, Sun, MessageSquare, Sparkles, TestTube } from "lucide-react";
import { cn } from "@/lib/utils";
import { useTheme } from "next-themes";
import { Button } from "@/components/ui/button";

const navigation = [
  { name: "Overview", href: "/", icon: Home },
  { name: "Minimee", href: "/minimee", icon: MessageSquare },
  { name: "Agents", href: "/agents", icon: Bot },
  { name: "Logs", href: "/logs", icon: FileText },
  { name: "Embeddings", href: "/embeddings", icon: Sparkles },
  { name: "Tests", href: "/tests", icon: TestTube },
  { name: "Settings", href: "/settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  const { theme, setTheme } = useTheme();
  
  // Use mounted state from useTheme if available, otherwise track it ourselves
  const [mounted, setMounted] = useState(false);

  // Prevent hydration mismatch by only showing theme-dependent content after mount
  useEffect(() => {
    setMounted(true);
  }, []);

  return (
    <div className="flex h-full w-64 flex-col border-r bg-sidebar">
      <div className="flex h-24 items-center justify-center border-b px-6">
        <div className="flex items-center gap-4">
          <div className="relative h-14 w-14 flex-shrink-0">
            <Image
              src="/icon.png"
              alt="Minimee"
              fill
              className="object-contain opacity-85 transition-opacity hover:opacity-100"
              priority
            />
          </div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground/90">
            Minimee
          </h1>
        </div>
      </div>

      <nav className="flex-1 space-y-1 p-4">
        {navigation.map((item) => {
          const isActive = pathname === item.href;
          const Icon = item.icon;
          return (
            <Link
              key={item.name}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-sidebar-accent text-sidebar-accent-foreground"
                  : "text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
              )}
            >
              <Icon className="h-5 w-5" />
              {item.name}
            </Link>
          );
        })}
      </nav>

      <div className="border-t p-4">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          className="w-full justify-start"
        >
          {!mounted ? (
            // Render placeholder during SSR to match client
            <>
              <Moon className="mr-2 h-4 w-4" />
              Dark Mode
            </>
          ) : theme === "dark" ? (
            <>
              <Sun className="mr-2 h-4 w-4" />
              Light Mode
            </>
          ) : (
            <>
              <Moon className="mr-2 h-4 w-4" />
              Dark Mode
            </>
          )}
        </Button>
      </div>
    </div>
  );
}

