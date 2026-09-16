"use client";

import React, { ReactNode, useEffect, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { cn } from "@/lib/utils";

export type ReasoningTextVariant = "scramble" | "cascade" | "swap";

export interface ReasoningTextProps {
  phrases?: string[];
  variant?: ReasoningTextVariant;
  interval?: number;
  shimmerDuration?: number;
  indicator?: ReactNode;
  className?: string;
}

const DEFAULT_PHRASES = [
  "Đang phân tích câu hỏi",
  "Tra cứu văn bản quy phạm",
  "Đánh giá căn cứ pháp luật",
  "Chuẩn bị câu trả lời",
];

const ASCII_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"];

export function ReasoningText({
  phrases = DEFAULT_PHRASES,
  variant = "cascade",
  interval = 2200,
  indicator,
  className,
}: ReasoningTextProps) {
  const [index, setIndex] = useState(0);
  const [frame, setFrame] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => {
      setIndex((prev) => (prev + 1) % phrases.length);
    }, interval);
    return () => clearInterval(timer);
  }, [phrases.length, interval]);

  useEffect(() => {
    const spinner = setInterval(() => {
      setFrame((prev) => (prev + 1) % ASCII_FRAMES.length);
    }, 80);
    return () => clearInterval(spinner);
  }, []);

  const currentPhrase = phrases[index] || phrases[0];

  return (
    <div className={cn("inline-flex items-center gap-2 text-xs font-medium text-muted-foreground", className)}>
      <span className="font-mono text-primary text-xs w-3.5 inline-block text-center select-none" aria-hidden>
        {indicator ?? ASCII_FRAMES[frame]}
      </span>
      <AnimatePresence mode="wait">
        <motion.span
          key={currentPhrase}
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -4 }}
          transition={{ duration: 0.2 }}
          className="truncate"
        >
          {currentPhrase}
        </motion.span>
      </AnimatePresence>
    </div>
  );
}
