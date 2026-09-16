"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, Trash2 } from "lucide-react";
import { deleteAdminDocument } from "../../lib/api";
import { AdminDocumentSummary } from "../../lib/types";
import { StatusPill } from "./StatusPill";

interface DocumentsTableProps {
  documents: AdminDocumentSummary[];
  isLoading: boolean;
  onDeleted: (documentId: string) => void;
}

export const DocumentsTable: React.FC<DocumentsTableProps> = ({ documents, isLoading, onDeleted }) => {
  const router = useRouter();
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
              <th className="text-left px-4 py-2">Tệp</th>
              <th className="text-left px-4 py-2">Cơ quan ban hành</th>
              <th className="text-left px-4 py-2">Hiệu lực từ</th>
              <th className="text-left px-4 py-2">Trạng thái</th>
              <th className="text-right px-4 py-2">Chunks</th>
              <th className="text-right px-4 py-2">Hành động</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-dsh-border">
            {isLoading && documents.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-dsh-muted italic">
                  Đang tải danh mục...
                </td>
              </tr>
            ) : documents.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-dsh-muted italic">
                  Chưa có văn bản nào được nạp vào kho tri thức.
                </td>
              </tr>
            ) : (
              documents.map((doc) => (
                <tr
                  key={doc.id}
                  onClick={() => router.push(`/admin/detail?id=${doc.id}`)}
                  className="hover:bg-dsh-surface transition-colors cursor-pointer"
                >
                  <td className="px-4 py-2.5 max-w-xs">
                    <div className="font-semibold text-dsh-ink truncate" title={doc.filename}>
                      {doc.filename}
                    </div>
                    <div className="text-[10px] text-dsh-muted truncate" title={doc.title}>
                      {doc.title}
                    </div>
                  </td>
                  <td className="px-4 py-2.5 text-dsh-muted whitespace-nowrap">{doc.issuing_authority || "—"}</td>
                  <td className="px-4 py-2.5 text-dsh-muted whitespace-nowrap">{doc.effective_from || "—"}</td>
                  <td className="px-4 py-2.5">
                    <StatusPill status={doc.status} stage={doc.stage} errorMessage={doc.error_message} />
                  </td>
                  <td className="px-4 py-2.5 text-right text-dsh-ink font-semibold tabular-nums">
                    {doc.status === "FAILED" ? "-" : doc.chunk_count}
                  </td>
                  <td className="px-4 py-2.5 text-right" onClick={(e) => e.stopPropagation()}>
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
