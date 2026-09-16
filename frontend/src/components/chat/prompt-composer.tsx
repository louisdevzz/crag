"use client";

import React, { useRef, useState } from "react";
import { ArrowUp, Paperclip } from "lucide-react";
import { useAutoResizeTextarea } from "@/hooks/use-auto-resize-textarea";
import { cn } from "@/lib/utils";
import { uploadAdminDocument } from "@/lib/api";

interface PromptComposerProps {
  onSend: (text: string) => void;
  isLoading: boolean;
  asOfDate?: string;
  onAsOfDateChange?: (date: string) => void;
  modelLabel?: string;
  onOpenModelSettings?: () => void;
  onNewChat?: () => void;
  className?: string;
}

export const PromptComposer: React.FC<PromptComposerProps> = ({
  onSend,
  isLoading,
  onNewChat,
  className,
}) => {
  const [value, setValue] = useState("");
  const [isUploading, setIsUploading] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const { textareaRef, adjustHeight } = useAutoResizeTextarea({ minHeight: 44, maxHeight: 220 });

  const submit = () => {
    const trimmed = value.trim();
    if (!trimmed || isLoading) return;
    onSend(trimmed);
    setValue("");
    adjustHeight(true);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    const file = files[0];
    setIsUploading(true);
    try {
      await uploadAdminDocument(file);
      alert(`Đã tải lên văn bản "${file.name}" thành công và bắt đầu lập chỉ mục.`);
    } catch (err) {
      alert(`Tải file thất bại: ${err}`);
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  return (
    <div
      className={cn(
        "relative flex flex-col rounded-[22px] border border-border/80 bg-card shadow-xs transition-all focus-within:border-border focus-within:shadow-sm",
        className
      )}
    >
      {/* Hidden File Input */}
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,.docx,.txt"
        className="hidden"
        onChange={handleFileChange}
      />

      {/* Textarea */}
      <div className="w-full px-3.5 pt-3 pb-1">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => {
            setValue(e.target.value);
            adjustHeight();
          }}
          onKeyDown={handleKeyDown}
          placeholder="Message or run a task, / commands, @ files or sessions"
          rows={1}
          disabled={isLoading}
          className="w-full resize-none border-0 bg-transparent p-0 text-sm leading-6 text-foreground placeholder:text-muted-foreground/60 focus:outline-none focus:ring-0 disabled:opacity-50"
        />
      </div>

      {/* Bottom Action Bar */}
      <div className="flex items-center justify-between px-3 pb-2 pt-0.5">
        {/* Left Toolbar: Attachment only */}
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={isUploading}
            className="flex h-7 w-7 items-center justify-center rounded-full text-muted-foreground hover:bg-muted hover:text-foreground transition-colors cursor-pointer disabled:opacity-50"
            title="Đính kèm tệp văn bản (.pdf, .docx, .txt)"
            aria-label="Đính kèm tệp"
          >
            <Paperclip className="h-3.5 w-3.5" />
          </button>
        </div>

        {/* Right Controls: Send Button */}
        <div className="flex items-center gap-2">
          {/* Send Button (34px Blue Circle with ArrowUp) */}
          <button
            type="button"
            onClick={submit}
            disabled={!value.trim() || isLoading}
            className={cn(
              "flex h-[34px] w-[34px] items-center justify-center rounded-full bg-[#3964FE] text-white shadow-xs transition-all",
              value.trim() && !isLoading
                ? "hover:bg-[#2e56e4] opacity-100 cursor-pointer"
                : "opacity-40 cursor-not-allowed"
            )}
            title="Gửi câu hỏi"
            aria-label="Gửi tin nhắn"
          >
            <ArrowUp className="h-4 w-4 stroke-[2.5]" />
          </button>
        </div>
      </div>
    </div>
  );
};
