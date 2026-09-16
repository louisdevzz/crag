"use client";

import { useEffect, useState } from "react";

/* ─────────────────────────────────────────────────────────
 * STREAMING TEXT
 * Words resolve out of blur, inline citations appear in
 * context, then actions and follow-up prompts become usable.
 * ───────────────────────────────────────────────────────── */

export type StreamingToken = { text: string; cite?: boolean; sourceId?: string };

export type StreamingSource = {
  name: string;
  domain: string;
  href?: string;
  badge?: string;
};

export type StreamingLabels = {
  sources: string;
  followUps: string;
};

const DEFAULT_LABELS: StreamingLabels = {
  sources: "Căn cứ trích dẫn",
  followUps: "Gợi ý tra cứu tiếp theo",
};

export interface StreamingTextProps {
  content?: string | StreamingToken[];
  sources?: StreamingSource[];
  followUps?: string[];
  labels?: Partial<StreamingLabels>;
  isStreaming?: boolean;
  onCopy?: () => void;
  onRetry?: () => void;
  onFollowUp?: (prompt: string) => void;
  className?: string;
  children?: React.ReactNode;
}

export default function StreamingText({
  content,
  sources = [],
  followUps = [],
  labels,
  isStreaming = false,
  onCopy,
  onRetry,
  onFollowUp,
  className = "",
  children,
}: StreamingTextProps) {
  const l = { ...DEFAULT_LABELS, ...labels };
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const [feedback, setFeedback] = useState<"up" | "down" | null>(null);

  const handleCopy = () => {
    if (onCopy) onCopy();
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className={`w-full ${className}`}>
      {/* text content or markdown children */}
      <div className="text-[13.5px] leading-relaxed text-ink">
        {children ? (
          children
        ) : typeof content === "string" ? (
          <span>{content}</span>
        ) : (
          (content || []).map((token, i) =>
            token.cite ? (
              <span
                key={i}
                className="mx-1 inline-flex h-5 items-center gap-1 rounded-chip bg-inset px-1.5 align-middle font-mono text-[11px] font-medium text-accent shadow-hairline"
              >
                {token.sourceId || "Căn cứ"}
              </span>
            ) : (
              <span key={i}>{token.text} </span>
            ),
          )
        )}

        {isStreaming && (
          <span
            className="ml-1 inline-block h-3.5 w-1 translate-y-0.5 rounded-full bg-ink"
            style={{ animation: "caret-blink 900ms ease-out infinite" }}
          />
        )}
      </div>

      {/* action icons row & sources toggle */}
      <div
        className="flex flex-wrap items-center justify-between gap-2 transition-opacity duration-300"
        style={{ opacity: isStreaming ? 0.6 : 1 }}
      >
        <div className="flex items-center gap-1">
          {/* copy */}
          <button
            type="button"
            aria-label="Sao chép"
            onClick={handleCopy}
            className="flex size-7 items-center justify-center rounded-control text-ink-3 transition-colors duration-100 hover:bg-hover hover:text-ink cursor-pointer"
            title="Sao chép câu trả lời"
          >
            {copied ? (
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--green)" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
                <path d="M20 6L9 17l-5-5" />
              </svg>
            ) : (
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <rect x="9" y="9" width="12" height="12" rx="2.5" />
                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
              </svg>
            )}
          </button>

          {/* retry */}
          {onRetry && (
            <button
              type="button"
              aria-label="Tạo lại"
              onClick={onRetry}
              className="flex size-7 items-center justify-center rounded-control text-ink-3 transition-colors duration-100 hover:bg-hover hover:text-ink cursor-pointer"
              title="Tra cứu lại câu này"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 12a9 9 0 1 1-2.64-6.36M21 3v6h-6" />
              </svg>
            </button>
          )}

          {/* thumbs up */}
          <button
            type="button"
            aria-label="Hữu ích"
            onClick={() => setFeedback(feedback === "up" ? null : "up")}
            className={`flex size-7 items-center justify-center rounded-control transition-colors duration-100 cursor-pointer ${
              feedback === "up"
                ? "bg-green-tint text-green"
                : "text-ink-3 hover:bg-hover hover:text-ink"
            }`}
            title="Câu trả lời hữu ích"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <path d="M7 10v12M15 5.88L14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.76a2 2 0 0 0 1.79-1.11L12 2a3.13 3.13 0 0 1 3 3.88z" />
            </svg>
          </button>

          {/* thumbs down */}
          <button
            type="button"
            aria-label="Chưa chính xác"
            onClick={() => setFeedback(feedback === "down" ? null : "down")}
            className={`flex size-7 items-center justify-center rounded-control transition-colors duration-100 cursor-pointer ${
              feedback === "down"
                ? "bg-red-tint text-red"
                : "text-ink-3 hover:bg-hover hover:text-ink"
            }`}
            title="Chưa chính xác"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <path d="M17 14V2M9 18.12L10 14H4.17a2 2 0 0 1-1.92-2.56l2.33-8A2 2 0 0 1 6.5 2H20a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2.76a2 2 0 0 0-1.79 1.11L12 22a3.13 3.13 0 0 1-3-3.88z" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}
