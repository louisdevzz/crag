"use client";

import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";

/* ─────────────────────────────────────────────────────────
 * THINKING — expandable agent trace, four variants
 *
 *   Steps      step list with spinner → muted checks
 *   Reasoning  prose reasoning that expands, then settles
 *   Search     web-search / CRAG trace: query + sources read
 *   Coding     tool trace: tool execution, parameters, diffs
 *
 * The trace runs during execution and remains expandable.
 * ───────────────────────────────────────────────────────── */

export type ThinkingRow = {
  primary: string;
  secondary?: string;
  mono?: boolean;
  add?: number;
  del?: number;
  href?: string;
};

const VARIANTS: Record<
  string,
  { active: string; done: string; rows: ThinkingRow[]; query?: string }
> = {
  Steps: {
    active: "Đang phân tích yêu cầu",
    done: "Đã phân tích các bước pháp lý",
    rows: [
      { primary: "Nhận diện từ khóa pháp lý & căn cứ áp dụng" },
      { primary: "Tra cứu kho tri thức văn bản quy phạm" },
      { primary: "Kiểm tra hiệu lực thời gian & đối chiếu điều khoản", secondary: "BLLĐ 2019" },
      { primary: "Tổng hợp kết luận & trích dẫn nguồn" },
    ],
  },
  Reasoning: {
    active: "Đang lập luận pháp lý",
    done: "Đã hoàn thành suy luận căn cứ",
    rows: [
      { primary: "Quy định về thời giờ làm việc bình thường áp dụng theo Điều 105 Bộ luật Lao động 2019." },
      { primary: "Cần đối chiếu thêm quy định làm thêm giờ tại Điều 106 để trả lời toàn diện cho doanh nghiệp." },
    ],
  },
  Search: {
    active: "Đang tra cứu cổng thông tin",
    done: "Đã tra cứu cổng pháp luật chính thống",
    query: "Điều 105 106 thời giờ làm việc BLLĐ 2019",
    rows: [
      { primary: "Bộ luật Lao động số 45/2019/QH14", secondary: "vbpl.vn", href: "https://vbpl.vn" },
      { primary: "Nghị định 145/2020/NĐ-CP", secondary: "chinhphu.vn", href: "https://chinhphu.vn" },
      { primary: "Cổng thông tin Bộ Tư pháp", secondary: "moj.gov.vn", href: "https://moj.gov.vn" },
    ],
  },
  Coding: {
    active: "Đang gọi công cụ tra cứu",
    done: "Đã hoàn thành 2 lệnh tra cứu",
    rows: [
      { primary: "crag_search", secondary: "query='thời giờ làm việc'", mono: true },
      { primary: "controlled_web_search", secondary: "domain='vbpl.vn'", mono: true, add: 4, del: 0 },
      { primary: "validate_citations", secondary: "accuracy=1.00", mono: true },
    ],
  },
};

function Dot({ tone }: { tone: string }) {
  return (
    <span className={`flex size-3.5 shrink-0 items-center justify-center rounded-full text-white ${tone}`}>
      <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
        <circle cx="12" cy="12" r="9" />
        <path d="M3.5 12h17M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18" />
      </svg>
    </span>
  );
}

const TONES = ["bg-accent", "bg-orange", "bg-green"];

export interface ThinkingStateProps {
  variant?: "Steps" | "Reasoning" | "Search" | "Coding" | string;
  isWorking?: boolean;
  rows?: ThinkingRow[];
  active?: string;
  done?: string;
  query?: string;
  duration?: number;
  icon?: ReactNode;
  defaultExpanded?: boolean;
  className?: string;
}

export default function ThinkingState({
  variant = "Steps",
  isWorking = false,
  rows: customRows,
  active: customActive,
  done: customDone,
  query: customQuery,
  duration,
  icon,
  defaultExpanded = false,
  className = "",
}: ThinkingStateProps) {
  const [manualExpanded, setManualExpanded] = useState<boolean | null>(defaultExpanded);
  const [selectedTool, setSelectedTool] = useState<string | null>(null);

  const base = VARIANTS[variant] ?? VARIANTS.Steps;
  const activeLabel = customActive ?? base.active;
  const doneLabel =
    customDone ??
    (duration !== undefined
      ? `Đã suy nghĩ trong ${duration.toFixed(1)}s`
      : base.done);

  const rows = customRows ?? base.rows;
  const query = customQuery ?? base.query;
  const expanded = manualExpanded ?? isWorking;

  const traceRef = useRef<HTMLDivElement>(null);
  const [lineHeight, setLineHeight] = useState(0);

  useLayoutEffect(() => {
    if (traceRef.current) setLineHeight(traceRef.current.offsetHeight);
  }, [rows.length, expanded, variant]);

  return (
    <div
      className={`flex w-full flex-col ${className}`}
      style={{
        transition: "min-height 400ms cubic-bezier(0.23,1,0.32,1)",
      }}
    >
      {/* header button */}
      <button
        type="button"
        aria-expanded={expanded}
        onClick={() => setManualExpanded((current) => !(current ?? isWorking))}
        className="-mx-1.5 flex w-fit items-center gap-2 rounded-control px-2 py-1 text-left
          transition-colors duration-100 hover:bg-hover cursor-pointer select-none"
      >
        {icon ? (
          <span
            className="flex shrink-0 transition-colors duration-200"
            style={{ color: isWorking ? "var(--ink-2)" : "var(--ink-3)" }}
          >
            {icon}
          </span>
        ) : (
          <svg
            width="15"
            height="15"
            viewBox="0 0 24 24"
            fill={isWorking ? "var(--accent)" : "var(--ink-3)"}
            className={isWorking ? "animate-pulse" : ""}
          >
            <path d="M12 2l2.4 7.2L22 12l-7.6 2.8L12 22l-2.4-7.2L2 12l7.6-2.8z" />
          </svg>
        )}

        <span role="status" className="contents">
          {isWorking ? (
            <span
              className="bg-clip-text text-[13px] font-medium whitespace-nowrap text-transparent"
              style={{
                backgroundImage:
                  "linear-gradient(90deg, var(--ink-3) 35%, var(--ink) 50%, var(--ink-3) 65%)",
                backgroundSize: "200% 100%",
                animation: "shimmer-text 1.4s linear infinite",
              }}
            >
              {activeLabel}
            </span>
          ) : (
            <span className="text-[13px] font-medium whitespace-nowrap text-ink-2">
              {doneLabel}
            </span>
          )}
        </span>

        <svg
          width="13"
          height="13"
          viewBox="0 0 24 24"
          fill="none"
          stroke="var(--ink-3)"
          strokeWidth="2.2"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="transition-transform duration-300"
          style={{ transform: expanded ? "rotate(180deg)" : "rotate(0)" }}
        >
          <path d="M6 9l6 6 6-6" />
        </svg>
      </button>

      {/* expandable trace */}
      <div
        className="grid transition-[grid-template-rows,opacity] duration-400"
        style={{
          gridTemplateRows: expanded ? "1fr" : "0fr",
          opacity: expanded ? 1 : 0,
          transitionTimingFunction: "cubic-bezier(0.23, 1, 0.32, 1)",
        }}
      >
        <div className="overflow-hidden">
          <div className="relative mt-1 ml-[5px] pl-4">
            <span
              aria-hidden
              className="absolute left-[3px] w-px bg-line"
              style={{
                top: -6,
                height: lineHeight ? Math.max(lineHeight - 2, 0) : 0,
                transition: "height 400ms cubic-bezier(0.23,1,0.32,1)",
              }}
            />
            <div ref={traceRef} className="flex flex-col gap-1 py-1">
              {query && (
                <div className="flex h-6 items-center gap-2 px-1.5 text-ink-3">
                  <svg
                    width="13"
                    height="13"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    className="shrink-0"
                  >
                    <circle cx="11" cy="11" r="7" />
                    <path d="M21 21l-4.3-4.3" />
                  </svg>
                  <span className="text-[12px] text-ink-2">{query}</span>
                </div>
              )}

              {rows.map((row, i) => {
                const content = (
                  <>
                    {variant === "Search" && <Dot tone={TONES[i % 3]} />}
                    {variant === "Steps" &&
                      (isWorking && i === rows.length - 1 ? (
                        <span
                          className="size-3 shrink-0 rounded-full border-[1.5px] border-line-strong border-t-ink-2"
                          style={{ animation: "spin 700ms linear infinite" }}
                        />
                      ) : (
                        <svg
                          width="13"
                          height="13"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="var(--green)"
                          strokeWidth="2.5"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          className="shrink-0"
                        >
                          <path d="M20 6L9 17l-5-5" />
                        </svg>
                      ))}

                    <span
                      className={`min-w-0 text-[12.5px] ${
                        variant === "Reasoning"
                          ? "whitespace-normal leading-relaxed text-ink-2"
                          : "font-medium text-ink"
                      } ${variant === "Search" ? "hover:underline text-accent-ink" : ""}`}
                    >
                      {row.primary}
                    </span>

                    {row.secondary && (
                      <span
                        className={`shrink-0 text-[11.5px] text-ink-3 ${
                          row.mono ? "font-mono" : ""
                        }`}
                      >
                        {row.secondary}
                      </span>
                    )}

                    {row.add !== undefined && (
                      <span className="shrink-0 font-mono text-[11px] tabular-nums">
                        <span className="text-green">+{row.add}</span>{" "}
                        {row.del !== undefined && (
                          <span className="text-red">−{row.del}</span>
                        )}
                      </span>
                    )}
                  </>
                );

                const rowClass =
                  "flex min-h-7 w-full items-center gap-2 rounded-md px-1.5 py-0.5 text-left";

                if (row.href) {
                  return (
                    <a
                      key={i}
                      href={row.href}
                      target="_blank"
                      rel="noreferrer"
                      className={`${rowClass} transition-colors duration-150 hover:bg-hover`}
                    >
                      {content}
                    </a>
                  );
                }

                if (variant === "Coding") {
                  const selected = selectedTool === row.primary;
                  return (
                    <button
                      key={i}
                      type="button"
                      aria-pressed={selected}
                      onClick={() => setSelectedTool(selected ? null : row.primary)}
                      className={`${rowClass} transition-colors duration-150 ${
                        selected ? "bg-inset" : "hover:bg-hover"
                      }`}
                    >
                      {content}
                    </button>
                  );
                }

                return (
                  <div key={i} className={rowClass}>
                    {content}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
