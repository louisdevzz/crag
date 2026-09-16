"use client";

/**
 * Live, multi-step processing indicator shown inline in the message stream
 * while a turn is in flight — inspired by boardui's "Agent Progress" pattern
 * (collapsible multi-step task list with animated active/pending/completed
 * states): https://www.boardui.com/components/agent-progress
 *
 * `stage` is driven by real `{"type":"node",...}` SSE events emitted as the
 * ReAct Agent Core loop (agent <-> tools) actually executes (see
 * /api/chat/stream) — not a client-side timer. There is no router step: the
 * agent itself decides whether to call a tool. The component unmounts the
 * instant the first live answer token arrives and is replaced by the
 * streaming assistant bubble.
 */
import React, { useState } from "react";
import { Check, ChevronDown, Circle, Loader2, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";
import { AgentThinking } from "./agent-thinking";

const STEP_TITLES = [
  "Phân tích câu hỏi & lựa chọn công cụ",
  "Truy hồi bằng chứng (CRAG / tìm kiếm ngoài)",
  "Tổng hợp & đánh giá bằng chứng",
  "Sinh câu trả lời & kiểm định trích dẫn",
];

interface AgentProgressProps {
  /** Index (0-based) of the currently active pipeline stage. */
  stage: number;
}

export const AgentProgress: React.FC<AgentProgressProps> = ({ stage }) => {
  const [isOpen, setIsOpen] = useState(true);
  const activeIndex = Math.min(stage, STEP_TITLES.length - 1);

  return (
    <div className="flex w-full items-start gap-3">
      <div className="mt-0.5 flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground">
        <Sparkles className="h-3.5 w-3.5" />
      </div>

      <div className="min-w-0 flex-1 rounded-2xl border border-border bg-card">
        <button
          type="button"
          onClick={() => setIsOpen((v) => !v)}
          className="flex w-full items-center justify-between gap-2 px-3.5 py-2.5 text-left"
        >
          <AgentThinking variant="wave" label="Đang xử lý truy vấn" />
          <span className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
            {activeIndex + 1}/{STEP_TITLES.length}
            <ChevronDown className={cn("h-3.5 w-3.5 transition-transform", isOpen && "rotate-180")} />
          </span>
        </button>

        {isOpen && (
          <div className="space-y-2.5 border-t border-border px-3.5 py-3">
            {STEP_TITLES.map((title, i) => {
              const status = i < activeIndex ? "done" : i === activeIndex ? "active" : "pending";
              return (
                <div key={title} className="flex items-center gap-2.5">
                  {status === "done" ? (
                    <Check className="h-3.5 w-3.5 flex-shrink-0 text-primary" />
                  ) : status === "active" ? (
                    <Loader2 className="h-3.5 w-3.5 flex-shrink-0 animate-spin text-primary" />
                  ) : (
                    <Circle className="h-3.5 w-3.5 flex-shrink-0 text-muted-foreground/40" />
                  )}
                  <span
                    className={cn(
                      "text-xs",
                      status === "pending" ? "text-muted-foreground/60" : "text-foreground"
                    )}
                  >
                    {title}
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
