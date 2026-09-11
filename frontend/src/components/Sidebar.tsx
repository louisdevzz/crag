"use client";

import React from "react";
import { BookOpen, PlusCircle, Trash2, UserCheck } from "lucide-react";
import { LegalDocument } from "../lib/types";

interface SidebarProps {
  documents: LegalDocument[];
  memories: Record<string, string>;
  onNewChat: () => void;
  onClearMemory: () => void;
}

const MEMORY_LABELS: Record<string, string> = {
  business_type: "Loại hình:",
  province: "Địa bàn:",
  industry: "Ngành nghề:",
  frequent_topic: "Chủ đề:",
  preferred_answer: "Phong cách:",
};

export const Sidebar: React.FC<SidebarProps> = ({
  documents,
  memories,
  onNewChat,
  onClearMemory,
}) => {
  const memoryEntries = Object.entries(memories);

  return (
    <aside className="w-72 bg-white border-r border-slate-200 flex flex-col p-4 flex-shrink-0 h-screen overflow-y-auto">
      {/* Brand Header */}
      <div className="pb-4 border-b border-slate-200">
        <div className="flex items-center gap-2 mb-3">
          <span className="bg-blue-600 text-white text-[11px] font-bold px-1.5 py-0.5 rounded">
            CRAG V3
          </span>
          <h2 className="text-base font-bold text-slate-900 tracking-tight">
            Legal Assistant
          </h2>
        </div>
        <button
          onClick={onNewChat}
          className="w-full flex items-center justify-center gap-2 bg-blue-50 text-blue-700 hover:bg-blue-600 hover:text-white border border-blue-200 hover:border-blue-600 text-xs font-semibold py-2 px-3 rounded-lg transition-all"
        >
          <PlusCircle className="w-3.5 h-3.5" />
          <span>Cuộc trò chuyện mới</span>
        </button>
      </div>

      {/* Semantic Memory Profile */}
      <div className="mt-5">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-1.5 text-[11px] font-bold tracking-wider text-slate-400 uppercase">
            <UserCheck className="w-3.5 h-3.5 text-slate-400" />
            <span>Hồ Sơ Doanh Nghiệp (Memory)</span>
          </div>
          {memoryEntries.length > 0 && (
            <button
              onClick={onClearMemory}
              className="text-[10px] text-red-500 hover:text-red-700 flex items-center gap-0.5"
              title="Xóa bộ nhớ doanh nghiệp"
            >
              <Trash2 className="w-3 h-3" />
              <span>Xóa</span>
            </button>
          )}
        </div>

        <div className="bg-slate-50 border border-slate-200 rounded-lg p-3 text-xs">
          {memoryEntries.length === 0 ? (
            <p className="text-slate-400 italic text-[11px] leading-relaxed">
              Chưa ghi nhận bối cảnh doanh nghiệp. Hãy nêu thông tin công ty trong câu hỏi để AI ghi nhớ.
            </p>
          ) : (
            <div className="space-y-1.5">
              {memoryEntries.map(([k, v]) => (
                <div key={k} className="flex items-start text-slate-700">
                  <span className="w-20 font-semibold text-slate-500 flex-shrink-0">
                    {MEMORY_LABELS[k] || k}
                  </span>
                  <span className="text-slate-900 font-medium">{v}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Knowledge Base Catalog */}
      <div className="mt-6 flex-1 flex flex-col min-h-0">
        <div className="flex items-center gap-1.5 text-[11px] font-bold tracking-wider text-slate-400 uppercase mb-2">
          <BookOpen className="w-3.5 h-3.5 text-slate-400" />
          <span>Kho Tri Thức Pháp Lý Nội Bộ</span>
        </div>

        <div className="space-y-2 overflow-y-auto pr-1 text-xs">
          {documents.length === 0 ? (
            <div className="text-slate-400 italic text-[11px]">Đang tải danh mục...</div>
          ) : (
            documents.map((doc) => (
              <div
                key={doc.id}
                className="p-2.5 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded-md transition-colors"
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="font-semibold text-blue-600 font-mono text-[11px]">
                    {doc.document_number}
                  </span>
                  <span
                    className={`text-[9px] font-bold px-1.5 py-0.2 rounded ${
                      doc.status === "effective"
                        ? "bg-emerald-100 text-emerald-800"
                        : "bg-red-100 text-red-800"
                    }`}
                  >
                    {doc.status === "effective" ? "Còn hiệu lực" : "Hết hiệu lực"}
                  </span>
                </div>
                <div className="text-slate-700 text-[11px] font-medium leading-snug line-clamp-2">
                  {doc.title}
                </div>
                <div className="text-slate-400 text-[10px] mt-1">
                  {doc.issuing_authority} {doc.effective_from && `• Từ ${doc.effective_from}`}
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </aside>
  );
};
