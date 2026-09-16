"use client";

import { useEffect, useState } from "react";

/* ─────────────────────────────────────────────────────────
 * CONTEXT CARDS
 * Retrieved knowledge chunks with their legal sources.
 * Displays title, locator/char count, body snippet,
 * source document name, and legal type badge.
 * ───────────────────────────────────────────────────────── */

export type ContextChunk = {
  title: string;
  chars?: string;
  body: string;
  source: string;
  badge: string;
  tone?: string;
  sourceUrl?: string;
};

export type ContextCardsLabels = {
  header: string;
  count: string;
};

const DEFAULT_LABELS: ContextCardsLabels = {
  header: "Căn cứ pháp lý thu thập được",
  count: "2 căn cứ",
};

const DEFAULT_CHUNKS: ContextChunk[] = [
  {
    title: "Điều 105. Thời giờ làm việc bình thường",
    chars: "320 ký tự",
    body: "1. Thời giờ làm việc bình thường không quá 08 giờ trong 01 ngày và không quá 48 giờ trong 01 tuần. Người sử dụng lao động có quyền quy định làm việc theo ngày hoặc theo tuần...",
    source: "Bộ luật Lao động số 45/2019/QH14",
    badge: "Luật",
    tone: "bg-accent",
  },
  {
    title: "Điều 106. Giờ làm việc ban đêm",
    chars: "180 ký tự",
    body: "Giờ làm việc ban đêm được tính từ 22 giờ đến 06 giờ sáng ngày hôm sau.",
    source: "Bộ luật Lao động số 45/2019/QH14",
    badge: "Luật",
    tone: "bg-green",
  },
];

export interface ContextCardsProps {
  chunks?: ContextChunk[];
  labels?: Partial<ContextCardsLabels>;
  className?: string;
  defaultOpen?: boolean;
}

export default function ContextCards({
  chunks = DEFAULT_CHUNKS,
  labels,
  className = "",
  defaultOpen = false,
}: ContextCardsProps) {
  const [open, setOpen] = useState(defaultOpen);
  const [expandedChunk, setExpandedChunk] = useState<number | null>(null);

  const headerLabel = labels?.header ?? DEFAULT_LABELS.header;
  const countLabel =
    labels?.count ?? `${chunks.length} căn cứ`;

  if (!chunks || chunks.length === 0) return null;

  return (
    <div className={`flex w-full flex-col gap-2 ${className}`}>
      {/* accordion toggle header */}
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((c) => !c)}
        className="-mx-1 flex w-fit items-center gap-2 rounded-control px-2 py-1 text-left transition-colors duration-100 hover:bg-hover cursor-pointer select-none"
      >
        <svg
          width="12"
          height="12"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.2"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="transition-transform duration-200"
          style={{ transform: open ? "rotate(0deg)" : "rotate(-90deg)" }}
        >
          <path d="M6 9l6 6 6-6" />
        </svg>
        <span className="text-[13px] font-semibold text-ink">{headerLabel}</span>
        <span className="inline-flex h-5 items-center rounded-md bg-inset px-1.5 text-[11px] font-medium text-ink-2 shadow-hairline tabular-nums">
          {countLabel}
        </span>
      </button>

      {/* cards container */}
      <div
        className="grid transition-[grid-template-rows,opacity] duration-300"
        style={{
          gridTemplateRows: open ? "1fr" : "0fr",
          opacity: open ? 1 : 0,
        }}
      >
        <div className="overflow-hidden">
          <div className="flex flex-col gap-2.5 pt-1">
            {chunks.map((chunk, i) => {
              const isExpanded = expandedChunk === i;
              return (
                <div
                  key={i}
                  className="overflow-hidden rounded-card bg-surface shadow-card border border-line transition-all duration-150"
                  style={{
                    animation: `fade-up 350ms cubic-bezier(0.23,1,0.32,1) ${i * 70}ms both`,
                  }}
                >
                  {/* card top bar */}
                  <div className="flex items-center justify-between gap-2.5 border-b border-line px-3 py-2 bg-canvas/40">
                    <span className="flex min-w-0 items-center gap-1.5 text-[12.5px] font-medium text-ink">
                      <span
                        className={`size-2 shrink-0 rounded-full ${
                          chunk.tone || "bg-accent"
                        }`}
                      />
                      <span className="truncate">{chunk.title}</span>
                    </span>

                    <div className="flex shrink-0 items-center gap-1.5">
                      {chunk.chars && (
                        <span className="font-mono text-[11px] text-ink-3">
                          {chunk.chars}
                        </span>
                      )}
                      <span className="rounded-[5px] bg-inset px-1.5 py-0.5 font-mono text-[10.5px] font-medium text-ink-2 shadow-hairline">
                        {chunk.badge}
                      </span>
                    </div>
                  </div>

                  {/* body text */}
                  <div className="p-3 text-[12.5px] leading-relaxed text-ink-2">
                    <p className={isExpanded ? "" : "line-clamp-3"}>
                      {chunk.body}
                    </p>
                    {chunk.body.length > 200 && (
                      <button
                        type="button"
                        onClick={() => setExpandedChunk(isExpanded ? null : i)}
                        className="mt-1.5 text-[11.5px] font-medium text-accent hover:underline cursor-pointer"
                      >
                        {isExpanded ? "Thu gọn" : "Xem thêm"}
                      </button>
                    )}
                  </div>

                  {/* source footer */}
                  <div className="flex items-center justify-between border-t border-line/60 bg-inset/40 px-3 py-1.5 text-[11px] text-ink-3">
                    <span className="truncate max-w-[80%] font-medium">
                      Nguồn: {chunk.source}
                    </span>
                    {chunk.sourceUrl && (
                      <a
                        href={chunk.sourceUrl}
                        target="_blank"
                        rel="noreferrer"
                        className="text-accent hover:underline"
                      >
                        Xem gốc →
                      </a>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
