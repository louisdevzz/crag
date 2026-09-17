"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { Trash2 } from "lucide-react";
import { deleteAdminDocument } from "../../lib/api";
import { AdminDocumentSummary } from "../../lib/types";
import { StatusPill } from "./StatusPill";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";

interface DocumentsTableProps {
  documents: AdminDocumentSummary[];
  isLoading: boolean;
  onDeleted: (documentId: string) => void;
}

export const DocumentsTable: React.FC<DocumentsTableProps> = ({ documents, isLoading, onDeleted }) => {
  const router = useRouter();
  const [pendingDelete, setPendingDelete] = useState<AdminDocumentSummary | null>(null);

  const handleConfirmDelete = async () => {
    if (!pendingDelete) return;
    try {
      await deleteAdminDocument(pendingDelete.id);
      onDeleted(pendingDelete.id);
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : String(e));
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
                    <StatusPill status={doc.status} stage={doc.stage} detail={doc.detail} errorMessage={doc.error_message} />
                  </td>
                  <td className="px-4 py-2.5 text-right text-dsh-ink font-semibold tabular-nums">
                    {doc.status === "FAILED" ? "-" : doc.chunk_count}
                  </td>
                  <td className="px-4 py-2.5 text-right" onClick={(e) => e.stopPropagation()}>
                    <button
                      onClick={() => setPendingDelete(doc)}
                      className="text-dsh-muted hover:text-red-600 p-1.5 rounded-full hover:bg-red-50 transition-colors"
                      title="Xóa văn bản khỏi kho tri thức"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <ConfirmDialog
        open={pendingDelete !== null}
        onOpenChange={(open) => !open && setPendingDelete(null)}
        title="Xóa văn bản pháp lý?"
        description={
          pendingDelete
            ? `"${pendingDelete.filename}" sẽ bị xóa vĩnh viễn cùng toàn bộ ${pendingDelete.chunk_count} đoạn tri thức đã lập chỉ mục. Hành động này không thể hoàn tác.`
            : undefined
        }
        confirmLabel="Xóa"
        onConfirm={handleConfirmDelete}
      />
    </div>
  );
};
