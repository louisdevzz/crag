"use client";

import React, { useEffect, useRef } from "react";
import { Sparkles } from "lucide-react";
import { Message } from "@/lib/types";
import { AgentProgress } from "./agent-progress";
import { TraceSummary } from "./trace-summary";

interface MessageListProps {
  messages: Message[];
  isLoading: boolean;
  /** Current real pipeline stage (0-3) from SSE `node` events, or `null` once
   * the answer has started streaming (or the turn finished). */
  liveStage: number | null;
}

function renderFormattedText(text: string) {
  const parts = text.split(/(\[[A-Za-z0-9_\-]+\])/g);
  return parts.map((part, i) => {
    if (part.startsWith("[") && part.endsWith("]")) {
      return (
        <span
          key={i}
          className="mx-0.5 inline-block rounded-md border border-border bg-secondary px-1.5 py-0.5 font-mono text-[11px] font-semibold text-foreground"
        >
          {part}
        </span>
      );
    }
    return part;
  });
}

export const MessageList: React.FC<MessageListProps> = ({ messages, isLoading, liveStage }) => {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-7 overflow-y-auto px-4 py-6">
      {messages.map((msg) => (
        <div
          key={msg.id}
          className={`flex flex-col ${msg.role === "user" ? "items-end" : "items-start"}`}
        >
          {msg.role === "user" ? (
            <div className="max-w-[75%] whitespace-pre-line rounded-2xl bg-secondary px-4 py-2.5 text-sm leading-relaxed text-secondary-foreground">
              {renderFormattedText(msg.content)}
            </div>
          ) : (
            <div className="flex w-full items-start gap-3">
              <div className="mt-0.5 flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground">
                <Sparkles className="h-3.5 w-3.5" />
              </div>
              <div className="min-w-0 flex-1">
                {msg.trace && !msg.isStreaming && (
                  <TraceSummary
                    route={msg.trace.route}
                    cragAction={msg.trace.cragAction}
                    citationReport={msg.citationReport}
                    evidence={msg.trace.evidence}
                  />
                )}
                <div className="whitespace-pre-line text-sm leading-relaxed text-foreground">
                  {renderFormattedText(msg.content)}
                  {msg.isStreaming && (
                    <span className="ml-0.5 inline-block h-3.5 w-1.5 animate-pulse bg-primary align-middle" />
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      ))}

      {isLoading && liveStage !== null && <AgentProgress stage={liveStage} />}

      <div ref={bottomRef} />
    </div>
  );
};
