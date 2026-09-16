"use client";

/**
 * Agent Thinking — pixel-grid loader with shimmer and elapsed time.
 * Adapted from Beautiful UI (LoadingState) & BoardUI Agent Thinking.
 */
import React from "react";
import LoadingState from "@/components/beautiful/LoadingState";
import { cn } from "@/lib/utils";

export type AgentThinkingVariant = "wave" | "spin" | "stars" | "infinity" | "Drive" | "Dots" | "Orbit";
export type AgentThinkingTone = "subtle" | "default" | "primary" | "accent";

export interface AgentThinkingProps {
  variant?: AgentThinkingVariant;
  /** Status label, e.g. "Đang xử lý" or "Đang truy hồi bằng chứng". */
  label?: string;
  tone?: AgentThinkingTone;
  shimmer?: boolean;
  showTimer?: boolean;
  elapsed?: string;
  className?: string;
}

export function AgentThinking({
  variant = "Drive",
  label = "Đang xử lý...",
  className,
}: AgentThinkingProps) {
  // Map legacy variant names to Beautiful UI LoadingState variants
  const mappedVariant =
    variant === "wave" || variant === "Drive"
      ? "Drive"
      : variant === "spin" || variant === "Dots"
      ? "Dots"
      : variant === "infinity" || variant === "Orbit"
      ? "Orbit"
      : "Drive";

  return (
    <LoadingState
      variant={mappedVariant}
      label={label}
      className={cn("my-1", className)}
    />
  );
}

export { LoadingState };
export default AgentThinking;
