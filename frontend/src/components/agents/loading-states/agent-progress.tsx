"use client";

import React, { useEffect, useState } from "react";
import { cn } from "@/lib/utils";

export interface AgentProgressProps {
  label?: string;
  elapsedSeconds?: number;
  initialSeconds?: number;
  running?: boolean;
  className?: string;
}

export function AgentProgress({
  label = "Đang xử lý",
  elapsedSeconds,
  initialSeconds = 0,
  running = true,
  className,
}: AgentProgressProps) {
  const [internalSeconds, setInternalSeconds] = useState(initialSeconds);

  useEffect(() => {
    if (!running || elapsedSeconds !== undefined) return;
    const start = performance.now();
    const interval = setInterval(() => {
      const diff = (performance.now() - start) / 1000;
      setInternalSeconds(initialSeconds + diff);
    }, 100);
    return () => clearInterval(interval);
  }, [running, initialSeconds, elapsedSeconds]);

  const displaySeconds =
    elapsedSeconds !== undefined ? elapsedSeconds : internalSeconds;

  return (
    <div
      className={cn(
        "inline-flex items-center gap-2 text-xs font-medium text-muted-foreground",
        className
      )}
    >
      <span className="relative flex h-2 w-2">
        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75" />
        <span className="relative inline-flex rounded-full h-2 w-2 bg-primary" />
      </span>
      <span>{label}</span>
      <span className="font-mono tabular-nums text-muted-foreground/60">
        {displaySeconds.toFixed(1)}s
      </span>
    </div>
  );
}
