"use client";

import React, { useState } from "react";
import { Loader2, Trash2 } from "lucide-react";
import { deleteAdminDocument } from "../../lib/api";
import { AdminDocument } from "../../lib/types";

interface DocumentsTableProps {
  documents: AdminDocument[];
  isLoading: boolean;
  onDeleted: (documentId: string) => void;
}

export const DocumentsTable: React.FC<DocumentsTableProps> = ({ documents, isLoading, onDeleted }) => {
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const handleConfirmDelete = async (id: string) => {
    setDeletingId(id);
    try {
      await deleteAdminDocument(id);
      onDeleted(id);
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : String(e));
    } finally {
      setDeletingId(null);
      setPendingDeleteId(null);
    }
  };

  return (
    <div className="bg-white border border-dsh-border rounded-2xl overflow-hidden">
      <div className="px-4 py-3 border-b border-dsh-border flex items-center justify-between">
        <h3 className="text-sm font-bold text-dsh-ink">Kho Tri Thức Pháp Lý Nội Bộ</h3>
        <span className="text-[11px] text-dsh-muted font-medium">{documents.length} văn bản</span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="bg-dsh-surface text-dsh-muted uppercase text-[10px] font-bold tracking-wider">
              <th className="text-left px-4 py-2">Số hiệu</th>
              <th className="text-left px-4 py-2">Tiêu đề</th>
              <th className="text-left px-4 py-2">Cơ quan ban hành</th>
              <th className="text-left px-4 py-2">Hiệu lực từ</th>
              <th className="text-left px-4 py-2">Trạng thái</th>
              <th className="text-right px-4 py-2">Điều khoản</th>
              <th className="text-right px-4 py-2">Hành động</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-dsh-border">
            {isLoading && documents.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-dsh-muted italic">
                  Đang tải danh mục...
                </td>
              </tr>
            ) : documents.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-dsh-muted italic">
                  Chưa có văn bản nào được nạp vào kho tri thức.
                </td>
              </tr>
            ) : (
              documents.map((doc) => (
                <tr key={doc.id} className="hover:bg-dsh-surface transition-colors">
                  <td className="px-4 py-2.5 font-mono font-semibold text-dsh-ink whitespace-nowrap">
                    {doc.document_number}
                  </td>
                  <td className="px-4 py-2.5 text-dsh-ink font-medium max-w-xs truncate" title={doc.title}>
                    {doc.title}
                  </td>
                  <td className="px-4 py-2.5 text-dsh-muted whitespace-nowrap">{doc.issuing_authority || "—"}</td>
                  <td className="px-4 py-2.5 text-dsh-muted whitespace-nowrap">{doc.effective_from || "—"}</td>
                  <td className="px-4 py-2.5">
                    <span
                      className={`text-[9px] font-bold px-1.5 py-0.5 rounded-full ${
                        doc.status === "effective"
                          ? "bg-emerald-100 text-emerald-800"
                          : "bg-red-100 text-red-800"
                      }`}
                    >
                      {doc.status === "effective" ? "Còn hiệu lực" : "Hết hiệu lực"}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-right text-dsh-ink font-semibold tabular-nums">
                    {doc.provisions_count}
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    {pendingDeleteId === doc.id ? (
                      <div className="flex items-center justify-end gap-1.5">
                        <span className="text-[10px] text-dsh-muted">Xác nhận xóa?</span>
                        <button
                          onClick={() => handleConfirmDelete(doc.id)}
                          disabled={deletingId === doc.id}
                          className="text-[10px] font-semibold text-white bg-red-600 hover:bg-red-700 px-2.5 py-1 rounded-full disabled:opacity-50"
                        >
                          {deletingId === doc.id ? <Loader2 className="w-3 h-3 animate-spin" /> : "Xóa"}
                        </button>
                        <button
                          onClick={() => setPendingDeleteId(null)}
                          className="text-[10px] font-semibold text-dsh-muted hover:text-dsh-ink px-2 py-1"
                        >
                          Hủy
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={() => setPendingDeleteId(doc.id)}
                        className="text-dsh-muted hover:text-red-600 p-1.5 rounded-full hover:bg-red-50 transition-colors"
                        title="Xóa văn bản khỏi kho tri thức"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
