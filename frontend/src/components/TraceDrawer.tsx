"use client";

import React from "react";
import { AlertTriangle, CheckCircle2, FileText, X } from "lucide-react";
import { CitationReport, EvidenceItem } from "../lib/types";

interface TraceDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  route: string;
  cragAction: string;
  citationReport?: CitationReport | null;
  evidence: EvidenceItem[];
}

export const TraceDrawer: React.FC<TraceDrawerProps> = ({
  isOpen,
  onClose,
  route,
  cragAction,
  citationReport,
  evidence,
}) => {
  if (!isOpen) return null;

  const actionUpper = (cragAction || "CORRECT").toUpperCase();

  return (
    <aside className="w-84 md:w-96 bg-white border-l border-slate-200 flex flex-col h-screen flex-shrink-0 z-20 shadow-lg">
      <div className="p-4 border-b border-slate-200 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-bold text-slate-900">
            Vết Thực Thi (Execution Trace)
          </h3>
          <p className="text-[11px] text-slate-500">
            Quan sát luồng điều phối LangGraph & CRAG
          </p>
        </div>
        <button
          onClick={onClose}
          className="text-slate-400 hover:text-slate-600 p-1 rounded hover:bg-slate-100"
          title="Đóng bảng vết"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4 text-xs">
        {/* Route Block */}
        <div>
          <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block mb-1">
            Bộ Điều Hướng (Query Router)
          </span>
          <span
            className={`inline-block px-2.5 py-1 rounded text-xs font-bold font-mono ${
              route === "database"
                ? "bg-blue-100 text-blue-800 border border-blue-300"
                : "bg-slate-100 text-slate-800 border border-slate-300"
            }`}
          >
            ROUTE: {(route || "RAG").toUpperCase()}
          </span>
        </div>

        {/* CRAG Action Block */}
        <div>
          <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block mb-1">
            Hành Động Tự Hiệu Chỉnh (CRAG Action)
          </span>
          <span
            className={`inline-block px-2.5 py-1 rounded text-xs font-bold ${
              actionUpper === "CORRECT"
                ? "bg-emerald-100 text-emerald-800 border border-emerald-300"
                : actionUpper === "AMBIGUOUS"
                ? "bg-amber-100 text-amber-800 border border-amber-300"
                : actionUpper === "INCORRECT"
                ? "bg-red-100 text-red-800 border border-red-300"
                : "bg-blue-100 text-blue-800 border border-blue-300"
            }`}
          >
            ACTION: {actionUpper}
          </span>
        </div>

        {/* Citation Validation Block */}
        <div>
          <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block mb-1">
            Kiểm Định Trích Dẫn (Citation Validator)
          </span>
          {citationReport ? (
            <div
              className={`p-2.5 rounded-lg border flex items-start gap-2 ${
                citationReport.ok
                  ? "bg-emerald-50 border-emerald-200 text-emerald-900"
                  : "bg-red-50 border-red-200 text-red-900"
              }`}
            >
              {citationReport.ok ? (
                <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0 mt-0.5" />
              ) : (
                <AlertTriangle className="w-4 h-4 text-red-600 flex-shrink-0 mt-0.5" />
              )}
              <div className="space-y-1">
                <div className="font-semibold text-[11px]">
                  {citationReport.ok
                    ? `Trích dẫn hợp lệ 100% (${citationReport.valid_citations?.length || 1} căn cứ)`
                    : `Phát hiện ${citationReport.errors?.length || 1} lỗi trích dẫn`}
                </div>
                {citationReport.valid_citations?.length > 0 && (
                  <div className="text-[10px] text-slate-600 font-mono">
                    Nguồn: {citationReport.valid_citations.join(", ")}
                  </div>
                )}
                {citationReport.errors?.length > 0 && (
                  <div className="text-[10px] text-red-700">
                    {citationReport.errors.join("; ")}
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="text-slate-400 italic">Chưa thực hiện kiểm định.</div>
          )}
        </div>

        {/* Evidence List */}
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">
              Bằng Chứng Tinh Lọc (Evidence Strips)
            </span>
            <span className="text-[11px] text-slate-500 font-mono">
              {evidence.length} strips
            </span>
          </div>

          {evidence.length === 0 ? (
            <div className="text-slate-400 italic text-[11px] p-2 bg-slate-50 rounded">
              Không có bằng chứng nào được bóc tách.
            </div>
          ) : (
            <div className="space-y-2.5">
              {evidence.map((ev, idx) => {
                const sid = ev.strip_id || ev.locator || ev.evidence_id || `EV_${idx}`;
                const score = ev.score !== undefined ? `${(ev.score * 100).toFixed(1)}%` : "N/A";
                return (
                  <div
                    key={sid + idx}
                    className="p-2.5 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded-md transition-all"
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-mono text-[10px] font-bold text-purple-700 bg-purple-50 px-1.5 py-0.5 rounded border border-purple-200">
                        {sid}
                      </span>
                      <span className="text-[10px] font-bold text-slate-600">
                        Điểm: {score}
                      </span>
                    </div>
                    {ev.heading && (
                      <div className="font-semibold text-slate-800 text-[11px] line-clamp-1 mb-1">
                        {ev.heading}
                      </div>
                    )}
                    <div className="text-slate-600 text-[11px] leading-relaxed line-clamp-3">
                      {ev.text}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </aside>
  );
};
