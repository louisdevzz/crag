"use client";

import React, { useEffect, useState } from "react";
import { Atom, CheckCircle2, ChevronDown, Search, Sparkles, Zap } from "lucide-react";
import { CitationReport } from "@/lib/types";
import { cn } from "@/lib/utils";

interface ThoughtDisclosureProps {
  isStreaming?: boolean;
  route?: string;
  cragAction?: string;
  citationReport?: CitationReport | null;
  evidenceCount?: number;
  durationMs?: number;
  liveStage?: number | null;
  className?: string;
}

export const ThoughtDisclosure: React.FC<ThoughtDisclosureProps> = ({
  isStreaming = false,
  route = "general",
  cragAction = "",
  citationReport,
  evidenceCount = 0,
  durationMs,
  liveStage,
  className,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [elapsedSec, setElapsedSec] = useState(0);

  useEffect(() => {
    if (!isStreaming) return;
    const start = Date.now();
    const timer = setInterval(() => {
      setElapsedSec(Math.max(1, Math.round((Date.now() - start) / 1000)));
    }, 500);
    return () => clearInterval(timer);
  }, [isStreaming]);

  const isRag = (route || "").toLowerCase() === "rag" || evidenceCount > 0 || !!cragAction;
  const actionUpper = (cragAction || "").toUpperCase();

  // Collapsed label
  let collapsedLabel = "Thought for a while";
  if (isStreaming) {
    collapsedLabel = elapsedSec > 0 ? `Đang suy nghĩ (${elapsedSec}s)...` : "Đang suy nghĩ...";
  } else if (durationMs && durationMs > 0) {
    const s = (durationMs / 1000).toFixed(1);
    collapsedLabel = isRag ? `Đã tra cứu & phân tích (${s}s)` : `Đã suy nghĩ (${s}s)`;
  } else {
    collapsedLabel = isRag ? "Đã tra cứu & đối chiếu pháp lý" : "Đã suy nghĩ";
  }

  return (
    <div className={cn("w-full my-1.5", className)}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="group inline-flex items-center gap-1.5 py-1 text-xs text-muted-foreground/80 hover:text-foreground transition-colors cursor-pointer select-none"
      >
        {isStreaming ? (
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-primary" />
          </span>
        ) : (
          <Sparkles className="h-3 w-3 text-muted-foreground/70 group-hover:text-primary transition-colors" />
        )}
        <span className="font-medium">{collapsedLabel}</span>
        <ChevronDown
          className={cn(
            "h-3 w-3 text-muted-foreground/60 group-hover:text-foreground transition-transform duration-200",
            isOpen && "rotate-180"
          )}
        />
      </button>

      {isOpen && (
        <div className="mt-1.5 mb-2 ml-1 pl-3 border-l border-border/70 space-y-2 text-xs py-1 transition-all">
          {/* Step 1: Think */}
          <div className="flex items-start gap-2 text-muted-foreground">
            <Atom className="h-3.5 w-3.5 text-indigo-500 mt-0.5 flex-shrink-0" />
            <div className="leading-relaxed">
              <span className="font-semibold text-foreground/90">Phân tích yêu cầu</span>
              <span className="mx-1.5 text-muted-foreground/40">·</span>
              {isRag ? (
                <span>Xác định vấn đề pháp lý và các căn cứ quy phạm liên quan trong kho tri thức doanh nghiệp.</span>
              ) : (
                <span>Trao đổi thông thường, giải thích và định hướng hỗ trợ tra cứu pháp luật.</span>
              )}
            </div>
          </div>

          {/* If RAG: Step 2: Search */}
          {isRag && (
            <div className="flex items-start gap-2 text-muted-foreground">
              <Search className="h-3.5 w-3.5 text-cyan-500 mt-0.5 flex-shrink-0" />
              <div className="leading-relaxed">
                <span className="font-semibold text-foreground/90">Tra cứu tri thức</span>
                <span className="mx-1.5 text-muted-foreground/40">·</span>
                <span>
                  {evidenceCount > 0
                    ? `Thu thập ${evidenceCount} bằng chứng từ cơ sở dữ liệu văn bản nội bộ (Hybrid Retrieval + Reranking).`
                    : "Truy hồi văn bản quy phạm pháp luật và điều khoản tương ứng."}
                </span>
              </div>
            </div>
          )}

          {/* If RAG & Action exists: Step 3: CRAG Action */}
          {isRag && actionUpper && (
            <div className="flex items-start gap-2 text-muted-foreground">
              <Zap className="h-3.5 w-3.5 text-amber-500 mt-0.5 flex-shrink-0" />
              <div className="leading-relaxed">
                <span className="font-semibold text-foreground/90">Đánh giá CRAG</span>
                <span className="mx-1.5 text-muted-foreground/40">·</span>
                {actionUpper === "CORRECT" ? (
                  <span className="text-foreground/80">
                    Nhánh <strong className="text-emerald-600 dark:text-emerald-400 font-semibold">CORRECT</strong> — Bằng chứng nội bộ đầy đủ, tiến hành tinh lọc tri thức (Knowledge Refinement).
                  </span>
                ) : actionUpper === "AMBIGUOUS" ? (
                  <span className="text-foreground/80">
                    Nhánh <strong className="text-amber-600 dark:text-amber-400 font-semibold">AMBIGUOUS</strong> — Bằng chứng một phần, kết hợp tìm kiếm mở rộng cổng thông tin chính thống.
                  </span>
                ) : actionUpper === "INCORRECT" ? (
                  <span className="text-foreground/80">
                    Nhánh <strong className="text-rose-600 dark:text-rose-400 font-semibold">INCORRECT</strong> — Bằng chứng nội bộ không đủ, kích hoạt truy vấn mạng chính thống.
                  </span>
                ) : (
                  <span>Áp dụng quy trình kiểm soát chất lượng bằng chứng.</span>
                )}
              </div>
            </div>
          )}

          {/* If citation report exists and has citations: Step 4: Verification */}
          {isRag && citationReport && citationReport.valid_citations && citationReport.valid_citations.length > 0 && (
            <div className="flex items-start gap-2 text-muted-foreground">
              <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500 mt-0.5 flex-shrink-0" />
              <div className="leading-relaxed">
                <span className="font-semibold text-foreground/90">Kiểm định trích dẫn</span>
                <span className="mx-1.5 text-muted-foreground/40">·</span>
                <span>
                  {citationReport.valid_citations.length} căn cứ được đối chiếu đạt độ chính xác{" "}
                  {Math.round((citationReport.citation_accuracy ?? 1) * 100)}% (Citation Validator).
                </span>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
