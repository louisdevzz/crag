"use client";

import React, { useRef, useState } from "react";
import { AlertTriangle, CheckCircle2, Loader2, UploadCloud } from "lucide-react";
import { uploadAdminDocument } from "../../lib/api";
import { UploadResult } from "../../lib/types";

interface DocumentUploadPanelProps {
  onIngested: (result: UploadResult) => void;
}

const ACCEPTED_EXTENSIONS = [".pdf", ".docx", ".doc", ".txt", ".md"];

export const DocumentUploadPanel: React.FC<DocumentUploadPanelProps> = ({ onIngested }) => {
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [result, setResult] = useState<UploadResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pendingReplaceFile, setPendingReplaceFile] = useState<File | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = async (file: File, replace?: boolean) => {
    const ext = "." + (file.name.split(".").pop() || "").toLowerCase();
    if (!ACCEPTED_EXTENSIONS.includes(ext)) {
      setError(`Định dạng '${ext}' không được hỗ trợ. Chỉ nhận: ${ACCEPTED_EXTENSIONS.join(", ")}`);
      setResult(null);
      setPendingReplaceFile(null);
      return;
    }

    setIsUploading(true);
    setError(null);
    setResult(null);
    try {
      const res = await uploadAdminDocument(file, replace);
      setResult(res);
      setPendingReplaceFile(null);
      onIngested(res);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
      setPendingReplaceFile(file);
    } finally {
      setIsUploading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) handleFile(file);
  };

  return (
    <div className="bg-white border border-dsh-border rounded-2xl p-4">
      <h3 className="text-sm font-bold text-dsh-ink mb-1">Nạp Văn bản Pháp lý Mới</h3>
      <p className="text-[11px] text-dsh-muted mb-3">
        Tải lên PDF (số hóa hoặc scan), DOCX, hoặc TXT. Hệ thống sẽ tự động bóc tách cấu trúc Chương/Điều/Khoản/Điểm
        và lập chỉ mục tri thức.
      </p>

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        className={`flex flex-col items-center justify-center gap-2 border-2 border-dashed rounded-2xl py-8 px-4 cursor-pointer transition-colors ${
          isDragging ? "border-dsh-ink bg-dsh-surface" : "border-dsh-border hover:border-zinc-400 hover:bg-dsh-surface"
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED_EXTENSIONS.join(",")}
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) handleFile(file);
          }}
        />
        {isUploading ? (
          <>
            <Loader2 className="w-7 h-7 text-dsh-ink animate-spin" />
            <span className="text-xs font-medium text-dsh-muted">Đang tải lên...</span>
          </>
        ) : (
          <>
            <UploadCloud className="w-7 h-7 text-dsh-muted" />
            <span className="text-xs font-medium text-dsh-ink">
              Kéo thả tệp vào đây, hoặc bấm để chọn tệp
            </span>
            <span className="text-[10px] text-dsh-muted">{ACCEPTED_EXTENSIONS.join(" · ")}</span>
          </>
        )}
      </div>

      {result && (
        <div className="mt-3 flex items-start gap-2 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-2xl p-3 text-xs">
          <CheckCircle2 className="w-4 h-4 flex-shrink-0 mt-0.5" />
          <div className="font-semibold">Đã tải lên, đang xử lý...</div>
        </div>
      )}

      {error && (
        <div className="mt-3 flex items-start gap-2 bg-red-50 border border-red-200 text-red-800 rounded-2xl p-3 text-xs">
          <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <div className="font-medium">{error}</div>
            {pendingReplaceFile && (
              <button
                onClick={() => handleFile(pendingReplaceFile, true)}
                disabled={isUploading}
                className="mt-2 text-[11px] font-semibold text-white bg-red-600 hover:bg-red-700 px-2.5 py-1 rounded-full disabled:opacity-50"
              >
                Thay thế
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
