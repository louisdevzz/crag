"use client";

import React, { useRef, useState } from "react";
import { AlertTriangle, CheckCircle2, FolderUp, Loader2, UploadCloud } from "lucide-react";
import { uploadAdminDocument, uploadAdminDocumentsBatch } from "../../lib/api";
import { BatchUploadItem, BatchUploadResult, UploadResult } from "../../lib/types";

interface DocumentUploadPanelProps {
  onIngested: (result: UploadResult) => void;
  onBatchIngested: (result: BatchUploadResult) => void;
}

const ACCEPTED_EXTENSIONS = [".pdf", ".docx", ".doc", ".txt", ".md"];

// Non-standard DOM attributes for folder selection; not present in React's typed InputHTMLAttributes.
type DirectoryInputAttrs = { webkitdirectory?: string; directory?: string };
const DIRECTORY_INPUT_ATTRS: DirectoryInputAttrs = { webkitdirectory: "", directory: "" };

const BATCH_STATUS_STYLES: Record<BatchUploadItem["status"], string> = {
  QUEUED: "bg-emerald-100 text-emerald-800",
  SKIPPED: "bg-amber-100 text-amber-800",
  ERROR: "bg-red-100 text-red-800",
};

const BATCH_STATUS_LABELS: Record<BatchUploadItem["status"], string> = {
  QUEUED: "Đã đưa vào hàng đợi",
  SKIPPED: "Bỏ qua",
  ERROR: "Lỗi",
};

export const DocumentUploadPanel: React.FC<DocumentUploadPanelProps> = ({ onIngested, onBatchIngested }) => {
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [result, setResult] = useState<UploadResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pendingReplaceFile, setPendingReplaceFile] = useState<File | null>(null);
  const [batchResult, setBatchResult] = useState<BatchUploadResult | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const folderInputRef = useRef<HTMLInputElement>(null);

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

  const handleFolderSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = Array.from(e.target.files || []);
    const files = selected.filter((file) => {
      const ext = "." + (file.name.split(".").pop() || "").toLowerCase();
      return ACCEPTED_EXTENSIONS.includes(ext);
    });
    if (files.length === 0) {
      if (folderInputRef.current) folderInputRef.current.value = "";
      return;
    }

    setIsUploading(true);
    setError(null);
    setBatchResult(null);
    try {
      const res = await uploadAdminDocumentsBatch(files);
      setBatchResult(res);
      onBatchIngested(res);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setIsUploading(false);
      if (folderInputRef.current) folderInputRef.current.value = "";
    }
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

      <div className="mt-2 flex items-center justify-center">
        <button
          type="button"
          onClick={() => folderInputRef.current?.click()}
          disabled={isUploading}
          className="flex items-center gap-1.5 text-[11px] font-medium text-dsh-muted hover:text-dsh-ink disabled:opacity-50"
        >
          <FolderUp className="w-3.5 h-3.5" />
          <span>Hoặc tải lên cả một thư mục</span>
        </button>
        <input
          ref={folderInputRef}
          type="file"
          multiple
          {...DIRECTORY_INPUT_ATTRS}
          className="hidden"
          onChange={handleFolderSelect}
        />
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

      {batchResult && (
        <div className="mt-3 rounded-2xl border border-dsh-border p-3 text-xs">
          <div className="font-semibold text-dsh-ink mb-2">
            {batchResult.accepted}/{batchResult.total} tệp đã được đưa vào hàng đợi xử lý
          </div>
          <div className="space-y-1.5 max-h-48 overflow-y-auto">
            {batchResult.results.map((item, idx) => (
              <div key={`${item.filename}-${idx}`} className="flex items-start justify-between gap-2">
                <div className="min-w-0 flex-1">
                  <div className="truncate text-dsh-ink font-medium" title={item.filename}>
                    {item.filename}
                  </div>
                  {item.error && <div className="text-[10px] text-dsh-muted mt-0.5">{item.error}</div>}
                </div>
                <span
                  className={`text-[9px] font-bold px-1.5 py-0.5 rounded-full flex-shrink-0 ${BATCH_STATUS_STYLES[item.status]}`}
                >
                  {BATCH_STATUS_LABELS[item.status]}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
