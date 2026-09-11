"use client";

/**
 * Collapsible, per-turn CRAG pipeline trace — replaces the old side-panel
 * "Kế hoạch xử lý" drawer. Rendered inline, collapsed by default, directly
 * above the assistant's answer once a turn completes.
 */
import React, { useState } from "react";
import { AlertTriangle, Check, ChevronDown, ListTree } from "lucide-react";
import { cn } from "@/lib/utils";
import { CitationReport, EvidenceItem } from "@/lib/types";

interface TraceSummaryProps {
  route: string;
  cragAction: string;
  citationReport?: CitationReport | null;
  evidence: EvidenceItem[];
}

function branchLabel(action: string): string {
  switch (action) {
    case "CORRECT":
      return "Tinh lọc tri thức nội bộ (Knowledge Refinement)";
    case "AMBIGUOUS":
      return "Tinh lọc nội bộ + Tìm kiếm Web bổ trợ";
    case "INCORRECT":
      return "Viết lại truy vấn + Tìm kiếm Web chính thống";
    default:
      return "Không áp dụng";
  }
}

export const TraceSummary: React.FC<TraceSummaryProps> = ({
  route,
  cragAction,
  citationReport,
  evidence,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const routeLower = (route || "rag").toLowerCase();
  const actionUpper = (cragAction || "").toUpperCase();
  const isRagFlow = routeLower === "rag";

  return (
    <div className="mb-2 w-full max-w-xl rounded-xl border border-border bg-card">
      <button
        type="button"
        onClick={() => setIsOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-2 px-3 py-2"
      >
        <span className="flex items-center gap-1.5 text-[11px] font-semibold text-muted-foreground">
          <ListTree className="h-3.5 w-3.5" />
          <span>Kế hoạch xử lý</span>
          <span className="rounded-full border border-border bg-secondary px-1.5 py-0.5 font-mono text-[10px] font-bold text-foreground">
            {(route || "—").toUpperCase()}
          </span>
          {isRagFlow && (
            <span
              className={cn(
                "rounded-full px-1.5 py-0.5 text-[10px] font-bold",
                actionUpper === "CORRECT"
                  ? "bg-emerald-100 text-emerald-800"
                  : actionUpper === "AMBIGUOUS"
                    ? "bg-amber-100 text-amber-800"
                    : actionUpper === "INCORRECT"
                      ? "bg-red-100 text-red-800"
                      : "bg-secondary text-muted-foreground"
              )}
            >
              {actionUpper || "—"}
            </span>
          )}
          {citationReport &&
            (citationReport.ok ? (
              <Check className="h-3.5 w-3.5 text-emerald-600" />
            ) : (
              <AlertTriangle className="h-3.5 w-3.5 text-red-600" />
            ))}
        </span>
        <ChevronDown className={cn("h-3.5 w-3.5 flex-shrink-0 text-muted-foreground transition-transform", isOpen && "rotate-180")} />
      </button>

      {isOpen && (
        <div className="space-y-3 border-t border-border px-3 py-3 text-xs">
          <div>
            <div className="mb-1 text-[11px] font-bold text-foreground">Nhánh rẽ CRAG</div>
            {isRagFlow ? (
              <span className="text-foreground">{branchLabel(actionUpper)}</span>
            ) : (
              <span className="italic text-muted-foreground">
                Bỏ qua — truy vấn không đi qua nhánh RAG.
              </span>
            )}
          </div>

          <div>
            <div className="mb-1 text-[11px] font-bold text-foreground">Kiểm định trích dẫn</div>
            {citationReport ? (
              <div
                className={cn(
                  "flex items-start gap-2 rounded-xl border p-2",
                  citationReport.ok
                    ? "border-emerald-200 bg-emerald-50 text-emerald-900"
                    : "border-red-200 bg-red-50 text-red-900"
                )}
              >
                {citationReport.ok ? (
                  <Check className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 text-emerald-600" />
                ) : (
                  <AlertTriangle className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 text-red-600" />
                )}
                <div className="space-y-1">
                  <div className="text-[11px] font-semibold">
                    {citationReport.ok
                      ? `Trích dẫn hợp lệ 100% (${citationReport.valid_citations?.length || 1} căn cứ)`
                      : `Phát hiện ${citationReport.errors?.length || 1} lỗi trích dẫn`}
                  </div>
                  {citationReport.valid_citations?.length > 0 && (
                    <div className="font-mono text-[10px] text-muted-foreground">
                      Nguồn: {citationReport.valid_citations.join(", ")}
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <span className="italic text-muted-foreground">
                Không có dữ liệu kiểm định cho phiên đã lưu.
              </span>
            )}
          </div>

          <div>
            <div className="mb-1.5 flex items-center justify-between">
              <span className="text-[11px] font-bold text-foreground">Bằng chứng tinh lọc</span>
              <span className="font-mono text-[10px] text-muted-foreground">{evidence.length} strips</span>
            </div>
            {evidence.length === 0 ? (
              <div className="rounded-xl bg-secondary p-2 text-[11px] italic text-muted-foreground">
                Không có bằng chứng nào được bóc tách.
              </div>
            ) : (
              <div className="space-y-1.5">
                {evidence.map((ev, idx) => {
                  const sid = ev.strip_id || ev.locator || ev.evidence_id || `EV_${idx}`;
                  const score = ev.score !== undefined ? `${(ev.score * 100).toFixed(1)}%` : "N/A";
                  return (
                    <div key={sid + idx} className="rounded-lg border border-border bg-secondary/60 p-2">
                      <div className="mb-1 flex items-center justify-between">
                        <span className="font-mono text-[10px] font-bold text-foreground">{sid}</span>
                        <span className="text-[10px] font-bold text-muted-foreground">Điểm: {score}</span>
                      </div>
                      {ev.heading && (
                        <div className="mb-0.5 line-clamp-1 text-[11px] font-semibold text-foreground">
                          {ev.heading}
                        </div>
                      )}
                      <div className="line-clamp-2 text-[11px] leading-relaxed text-muted-foreground">
                        {ev.text}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
