"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

/* ─────────────────────────────────────────────────────────
 * TOOL CHIPS
 * Tool calls and executions rendered as compact
 * chips, with expandable details showing parameters,
 * evidence collected, and status.
 * ───────────────────────────────────────────────────────── */

const STEP_MS = 600;

const Icons: Record<string, React.ReactNode> = {
  think: (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 2l2.4 7.2L22 12l-7.6 2.8L12 22l-2.4-7.2L2 12l7.6-2.8z" />
    </svg>
  ),
  search: (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <circle cx="11" cy="11" r="8" />
      <path d="m21 21-4.3-4.3" />
    </svg>
  ),
  write: (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M17 3a2.8 2.8 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5z" />
    </svg>
  ),
  run: (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 17l6-5-6-5M12 19h8" />
    </svg>
  ),
  read: (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <path d="M14 2v6h6" />
    </svg>
  ),
};

export type ToolDetailLine = { text: string; tone?: "add" | "del" | "ctx" };

export type ToolStep = {
  icon: string;
  label: string;
  chip: string;
  mono?: boolean;
  detailMono?: boolean;
  detail: ToolDetailLine[];
};

export type ToolDiff = { file: string; add: number; del: number };

export type ToolDiffLine = { text: string; tone: "add" | "del" | "ctx" };

export type ToolChipsLabels = {
  header: string;
  more?: string;
};

const DEFAULT_ROWS: ToolStep[] = [
  {
    icon: "search",
    label: "Tra cứu nội bộ",
    chip: "crag_search(query='thời giờ làm việc')",
    mono: true,
    detailMono: true,
    detail: [
      { text: "✓ Dense retrieve (Chroma): 0 candidates", tone: "ctx" },
      { text: "✓ BM25 retrieve: fallback empty corpus", tone: "ctx" },
      { text: "! CRAG action: INCORRECT -> trigger web search", tone: "add" },
    ],
  },
  {
    icon: "run",
    label: "Tra cứu cổng luật",
    chip: "controlled_web_search(query='Điều 105')",
    mono: true,
    detailMono: true,
    detail: [
      { text: "✓ TinyFish API query: 'Điều 105' (include_domains=vbpl.vn,chinhphu.vn...)", tone: "ctx" },
      { text: "+ 4 căn cứ pháp lý thu thập thành công", tone: "add" },
    ],
  },
  {
    icon: "read",
    label: "Kiểm tra trích dẫn",
    chip: "validate_citations()",
    mono: true,
    detailMono: true,
    detail: [
      { text: "✓ Trích dẫn hợp lệ: Điều 105, Điều 106", tone: "add" },
      { text: "✓ Độ chuẩn xác trích dẫn: 100%", tone: "add" },
    ],
  },
];

const DEFAULT_DIFFS: ToolDiff[] = [
  { file: "Bộ luật Lao động 2019", add: 48, del: 0 },
  { file: "Nghị định 145/2020/NĐ-CP", add: 12, del: 0 },
];

const DEFAULT_DIFF_LINES: Record<string, ToolDiffLine[]> = {
  "Bộ luật Lao động 2019": [
    { text: "Điều 105. Thời giờ làm việc bình thường", tone: "ctx" },
    { text: "+ 1. Thời giờ làm việc bình thường không quá 08 giờ trong 01 ngày", tone: "add" },
    { text: "+ và không quá 48 giờ trong 01 tuần.", tone: "add" },
  ],
  "Nghị định 145/2020/NĐ-CP": [
    { text: "Chương VII. Thời giờ làm việc, thời giờ nghỉ ngơi", tone: "ctx" },
    { text: "+ Chi tiết các công việc đặc thù và làm thêm giờ.", tone: "add" },
  ],
};

export interface ToolChipsProps {
  steps?: ToolStep[];
  diffs?: ToolDiff[];
  diffLines?: Record<string, ToolDiffLine[]>;
  labels?: Partial<ToolChipsLabels>;
  className?: string;
  defaultOpen?: boolean;
}

export default function ToolChips({
  steps = DEFAULT_ROWS,
  diffs = DEFAULT_DIFFS,
  diffLines = DEFAULT_DIFF_LINES,
  labels,
  className = "",
  defaultOpen = false,
}: ToolChipsProps) {
  const [open, setOpen] = useState(defaultOpen);
  const [openRows, setOpenRows] = useState<Set<string>>(new Set());
  const [preview, setPreview] = useState<{
    file: string;
    x: number;
    top?: number;
    bottom?: number;
  } | null>(null);

  const headerLabel =
    labels?.header ?? `${steps.length} lượt gọi công cụ hoàn tất`;

  const toggleRow = (label: string) => {
    setOpenRows((current) => {
      const next = new Set(current);
      if (next.has(label)) next.delete(label);
      else next.add(label);
      return next;
    });
  };

  const openPreview = (file: string) => (event: React.SyntheticEvent) => {
    const rect = (event.currentTarget as Element).getBoundingClientRect();
    const previewHeight = 38 + (diffLines[file]?.length ?? 0) * 19;
    const fitsBelow = rect.bottom + 6 + previewHeight <= window.innerHeight - 12;
    setPreview({
      file,
      x: Math.max(12, Math.min(rect.left, window.innerWidth - 320)),
      ...(fitsBelow
        ? { top: rect.bottom + 6 }
        : { bottom: window.innerHeight - rect.top + 6 }),
    });
  };

  const closePreview = (file: string) => () => {
    setPreview((current) => (current?.file === file ? null : current));
  };

  return (
    <div className={`w-full max-w-xl pb-1 ${className}`}>
      {/* collapsed run header button */}
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
        className="-mx-1.5 flex w-fit items-center gap-1.5 rounded-control px-2 py-1 text-[12.5px] text-ink-2 transition-colors duration-100 hover:bg-hover cursor-pointer select-none"
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
        <span className="font-medium tabular-nums">{headerLabel}</span>
      </button>

      {/* tool call rows */}
      <div
        className="grid transition-[grid-template-rows,opacity] duration-300"
        style={{
          gridTemplateRows: open ? "1fr" : "0fr",
          opacity: open ? 1 : 0,
        }}
      >
        <div className="-mx-1 overflow-hidden px-1.5 pb-1">
          <div className="mt-1.5 flex flex-col gap-1">
            {steps.map((row) => {
              const rowOpen = openRows.has(row.label);
              return (
                <div
                  key={row.label}
                  style={{ animation: "fade-up 300ms cubic-bezier(0.23,1,0.32,1) both" }}
                >
                  <button
                    type="button"
                    aria-expanded={rowOpen}
                    onClick={() => toggleRow(row.label)}
                    className="group/row -mx-[3px] flex h-7 w-[calc(100%+6px)] min-w-0 items-center gap-2 rounded-control px-[3px] text-left transition-colors duration-100 hover:bg-hover cursor-pointer"
                  >
                    <span className="relative flex size-4 shrink-0 items-center justify-center text-ink-3">
                      <span
                        className={`transition-opacity duration-100 group-hover/row:opacity-0 ${
                          rowOpen ? "opacity-0" : ""
                        }`}
                      >
                        {Icons[row.icon] || Icons.run}
                      </span>
                      <svg
                        width="12"
                        height="12"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2.2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        className={`absolute transition-[opacity,transform] duration-150 group-hover/row:opacity-100 ${
                          rowOpen ? "opacity-100" : "opacity-0"
                        }`}
                        style={{ transform: rowOpen ? "rotate(0deg)" : "rotate(-90deg)" }}
                      >
                        <path d="M6 9l6 6 6-6" />
                      </svg>
                    </span>

                    <span className="shrink-0 text-[12.5px] font-medium text-ink">
                      {row.label}
                    </span>

                    <span
                      className={`inline-flex h-5.5 min-w-0 flex-1 cursor-pointer items-center truncate rounded-chip bg-field px-1.5
                        text-[11.5px] text-ink-2 shadow-hairline transition-colors duration-100 hover:bg-hover
                        ${row.mono ? "font-mono" : ""}`}
                    >
                      {row.chip}
                    </span>
                  </button>

                  {/* expanded detail */}
                  <div
                    className="grid transition-[grid-template-rows,opacity] duration-300"
                    style={{
                      gridTemplateRows: rowOpen ? "1fr" : "0fr",
                      opacity: rowOpen ? 1 : 0,
                      transitionTimingFunction: "cubic-bezier(0.23, 1, 0.32, 1)",
                    }}
                  >
                    <div className="min-h-0 overflow-hidden">
                      <div className="mt-0.5 mb-1 ml-2 flex flex-col gap-0.5 border-l border-line py-0.5 pl-3.5">
                        {row.detail.map((line, li) => (
                          <span
                            key={li}
                            className={`truncate text-[11.5px] leading-[1.6] ${
                              row.detailMono ? "font-mono" : ""
                            } ${
                              line.tone === "add"
                                ? "text-green font-medium"
                                : line.tone === "del"
                                ? "text-red"
                                : "text-ink-2"
                            }`}
                          >
                            {line.text}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* file diff summary chips */}
          {diffs && diffs.length > 0 && (
            <div className="mt-2.5 flex flex-wrap items-center gap-1.5 border-t border-line/60 pt-2">
              <span className="text-[11px] font-medium text-ink-3">Văn bản liên quan:</span>
              {diffs.map((diff) => (
                <button
                  key={diff.file}
                  type="button"
                  data-diffchip
                  onMouseEnter={openPreview(diff.file)}
                  onMouseLeave={closePreview(diff.file)}
                  className="inline-flex h-5.5 items-center gap-1.5 rounded-chip bg-surface px-2 text-[11.5px] text-ink shadow-hairline transition-colors duration-150 hover:bg-hover"
                >
                  <span className="truncate max-w-[180px] font-medium">{diff.file}</span>
                  <span className="font-mono text-[10.5px] tabular-nums text-green font-semibold">
                    +{diff.add}
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* hover portal preview for diff */}
      {preview &&
        typeof document !== "undefined" &&
        createPortal(
          <div
            className="fixed z-50 w-72 rounded-card bg-surface p-2.5 shadow-raised border border-line"
            style={{
              left: preview.x,
              top: preview.top,
              bottom: preview.bottom,
              animation: "pop-in 150ms cubic-bezier(0.16,1,0.3,1) both",
            }}
          >
            <div className="mb-1.5 font-medium text-[12px] text-ink truncate border-b border-line pb-1">
              {preview.file}
            </div>
            <div className="flex flex-col gap-1 font-mono text-[10.5px] leading-relaxed">
              {(diffLines[preview.file] || []).map((l, i) => (
                <div
                  key={i}
                  className={`${
                    l.tone === "add" ? "text-green" : l.tone === "del" ? "text-red" : "text-ink-3"
                  }`}
                >
                  {l.text}
                </div>
              ))}
            </div>
          </div>,
          document.body,
        )}
    </div>
  );
}
