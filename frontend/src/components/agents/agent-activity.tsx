"use client";

import React, { ReactNode, useCallback, useEffect, useId, useRef, useState } from "react";
import {
  Atom,
  CheckCircle2,
  ChevronDown,
  Circle,
  Globe,
  Loader2,
  Scale,
  Search,
  Zap,
} from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { ThinkingShimmer } from "@/components/agents/loading-states/thinking-shimmer";
import { AgentDisclosure } from "@/components/agents/agent-disclosure";
import { EASE_OUT, SPRING_LAYOUT, SPRING_SWAP } from "@/lib/ease";
import { cn } from "@/lib/utils";

export type AgentActivityStatus = "working" | "complete" | "error";

export interface AgentActivityItem {
  id: string;
  type: "text" | "step" | "tool" | "search";
  label: string;
  content?: ReactNode;
  status?: "active" | "complete" | "pending" | "error";
  meta?: ReactNode;
}

export interface AgentActivityProps {
  items: AgentActivityItem[];
  status?: AgentActivityStatus;
  duration?: number;
  open?: boolean;
  defaultOpen?: boolean;
  onOpenChange?: (open: boolean) => void;
  collapseOnComplete?: boolean;
  activeLabel?: string;
  summary?: ReactNode;
  maxHeight?: number;
  className?: string;
}

function formatDuration(duration: number): string {
  const seconds = Math.max(0, Math.round(duration));
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  return remainder === 0 ? `${minutes}m` : `${minutes}m ${remainder}s`;
}

export function AgentActivity({
  items,
  status = "working",
  duration = 0,
  open,
  defaultOpen = false,
  onOpenChange,
  collapseOnComplete = true,
  activeLabel = "Đang suy nghĩ & phân tích…",
  summary,
  maxHeight = 220,
  className,
}: AgentActivityProps) {
  const reduce = useReducedMotion() ?? false;
  const baseId = useId();
  const triggerId = `${baseId}-trigger`;
  const contentId = `${baseId}-content`;

  const [internalOpen, setInternalOpen] = useState(defaultOpen);
  const previousStatus = useRef(status);

  const controlled = open !== undefined;
  const currentOpen = open ?? internalOpen;

  const setOpen = useCallback(
    (next: boolean) => {
      if (!controlled) setInternalOpen(next);
      onOpenChange?.(next);
    },
    [controlled, onOpenChange]
  );

  const working = status === "working";
  const expanded = working || currentOpen;

  useEffect(() => {
    if (previousStatus.current === "working" && status === "complete") {
      setOpen(!collapseOnComplete);
    }
    previousStatus.current = status;
  }, [collapseOnComplete, setOpen, status]);

  const toggle = () => {
    setOpen(!currentOpen);
  };

  const completedSummary =
    summary ?? (
      <>
        Thought for{" "}
        <span className="font-mono tabular-nums font-semibold">
          {formatDuration(duration)}
        </span>
      </>
    );

  const renderIcon = (item: AgentActivityItem) => {
    if (item.status === "active") {
      return <Loader2 className="h-3.5 w-3.5 animate-spin text-primary flex-shrink-0" />;
    }
    if (item.status === "complete") {
      return <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500 flex-shrink-0" />;
    }
    if (item.type === "search") {
      return <Search className="h-3.5 w-3.5 text-cyan-500 flex-shrink-0" />;
    }
    if (item.type === "tool") {
      return <Zap className="h-3.5 w-3.5 text-amber-500 flex-shrink-0" />;
    }
    return <Atom className="h-3.5 w-3.5 text-indigo-500 flex-shrink-0" />;
  };

  return (
    <div
      data-state={working ? "working" : expanded ? "open" : "closed"}
      aria-busy={working}
      className={cn("w-full text-xs my-2", className)}
    >
      {working ? (
        <div
          id={triggerId}
          role="status"
          className="flex h-7 items-center gap-2 text-muted-foreground"
        >
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-primary" />
          </span>
          <ThinkingShimmer>{activeLabel}</ThinkingShimmer>
          {duration > 0 && (
            <span className="font-mono tabular-nums text-[11px] text-muted-foreground/60">
              ({duration.toFixed(1)}s)
            </span>
          )}
        </div>
      ) : (
        <button
          id={triggerId}
          type="button"
          aria-expanded={expanded}
          aria-controls={contentId}
          onClick={toggle}
          className="group flex h-7 items-center gap-1.5 rounded-lg px-1.5 font-medium text-muted-foreground outline-none transition-colors hover:bg-muted/50 hover:text-foreground focus-visible:ring-1 focus-visible:ring-ring cursor-pointer select-none"
        >
          <span>{completedSummary}</span>
          <motion.span
            aria-hidden="true"
            animate={{ rotate: expanded ? 180 : 0 }}
            transition={reduce ? { duration: 0 } : SPRING_SWAP}
            className="text-muted-foreground/60 group-hover:text-foreground"
          >
            <ChevronDown className="size-3" />
          </motion.span>
        </button>
      )}

      <AgentDisclosure id={contentId} open={expanded}>
        <div
          className="mt-1 pl-3 border-l border-border/70 space-y-2 py-1.5 overflow-y-auto max-h-[220px]"
          style={{ maxHeight }}
        >
          <AnimatePresence mode="popLayout">
            {items.map((item) => (
              <motion.div
                key={item.id}
                initial={reduce ? { opacity: 1 } : { opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={reduce ? { opacity: 0 } : { opacity: 0, y: -4 }}
                transition={
                  reduce
                    ? { duration: 0 }
                    : { opacity: { duration: 0.15, ease: EASE_OUT }, y: SPRING_LAYOUT }
                }
                className="flex items-start gap-2 text-muted-foreground leading-relaxed"
              >
                <div className="mt-0.5">{renderIcon(item)}</div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span className="font-semibold text-foreground/90">{item.label}</span>
                    {item.meta && (
                      <span className="text-[10px] text-muted-foreground/60 bg-muted px-1 rounded">
                        {item.meta}
                      </span>
                    )}
                  </div>
                  {item.content && (
                    <div className="text-[11px] text-muted-foreground/80 mt-0.5">
                      {item.content}
                    </div>
                  )}
                </div>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      </AgentDisclosure>
    </div>
  );
}
