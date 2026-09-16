"use client";

import React, { ReactNode } from "react";
import { cn } from "@/lib/utils";

export interface ThinkingShimmerProps {
  children?: ReactNode;
  duration?: number;
  className?: string;
}

export function ThinkingShimmer({
  children = "Đang suy nghĩ…",
  duration = 1.8,
  className,
}: ThinkingShimmerProps) {
  return (
    <span
      style={{
        animationDuration: `${duration}s`,
      }}
      className={cn(
        "inline-flex items-center font-medium bg-gradient-to-r from-muted-foreground/40 via-foreground to-muted-foreground/40 bg-[length:200%_100%] bg-clip-text text-transparent animate-[shimmer_2s_infinite]",
        className
      )}
    >
      {children}
    </span>
  );
}
