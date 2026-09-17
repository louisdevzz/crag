"use client";

import React from "react";
import { AdminDocumentSummary } from "../../lib/types";

const STAGE_LABELS: Record<string, string> = {
  PARSING: "Đọc và trích xuất văn bản",
  OCR: "Nhận diện văn bản quét (OCR)",
  CLEANING: "Làm sạch & chuẩn hoá văn bản",
  STRUCTURING: "Phát hiện cấu trúc pháp lý (Chương/Điều/Khoản)",
  CHUNKING: "Tạo các đoạn tri thức (chunks)",
  EMBEDDING: "Lập chỉ mục tri thức",
  INDEXING: "Lập chỉ mục tri thức",
  DONE: "Sẵn sàng",
};

export function stageLabel(stage: string): string {
  return STAGE_LABELS[stage] || stage;
}

interface StatusPillProps {
  status: AdminDocumentSummary["status"];
  stage?: string | null;
  detail?: string | null;
  errorMessage?: string | null;
}

const STATUS_STYLES: Record<AdminDocumentSummary["status"], string> = {
  READY: "bg-emerald-100 text-emerald-800",
  PROCESSING: "bg-amber-100 text-amber-800",
  FAILED: "bg-red-100 text-red-800",
  UPLOADED: "bg-zinc-100 text-zinc-700",
};

const STATUS_LABELS: Record<AdminDocumentSummary["status"], string> = {
  READY: "Sẵn sàng",
  PROCESSING: "Đang xử lý",
  FAILED: "Lỗi",
  UPLOADED: "Đang chờ xử lý",
};

export const StatusPill: React.FC<StatusPillProps> = ({ status, stage, detail, errorMessage }) => {
  return (
    <div className="inline-flex flex-col items-start gap-0.5">
      <span
        className={`text-[9px] font-bold px-1.5 py-0.5 rounded-full ${STATUS_STYLES[status]}`}
        title={status === "FAILED" && errorMessage ? errorMessage : undefined}
      >
        {STATUS_LABELS[status]}
      </span>
      {status === "PROCESSING" && stage && (
        <span className="text-[9px] text-dsh-muted font-medium">
          {stageLabel(stage)}
          {detail ? ` · ${detail}` : ""}
        </span>
      )}
    </div>
  );
};
