"use client";

import React, { useState } from "react";
import { ArrowUp, Calendar, ChevronDown, SlidersHorizontal, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { useAutoResizeTextarea } from "@/hooks/use-auto-resize-textarea";
import { cn } from "@/lib/utils";

interface PromptComposerProps {
  onSend: (text: string) => void;
  isLoading: boolean;
  asOfDate: string;
  onAsOfDateChange: (date: string) => void;
  modelLabel: string;
  onOpenModelSettings: () => void;
  className?: string;
}

export const PromptComposer: React.FC<PromptComposerProps> = ({
  onSend,
  isLoading,
  asOfDate,
  onAsOfDateChange,
  modelLabel,
  onOpenModelSettings,
  className,
}) => {
  const [value, setValue] = useState("");
  const { textareaRef, adjustHeight } = useAutoResizeTextarea({ minHeight: 28, maxHeight: 220 });

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

  return (
    <div className={cn("rounded-3xl border border-border bg-card p-2.5 shadow-sm", className)}>
      <Textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => {
          setValue(e.target.value);
          adjustHeight();
        }}
        onKeyDown={handleKeyDown}
        placeholder="Hỏi tôi bất cứ điều gì..."
        rows={1}
        disabled={isLoading}
        className="min-h-[28px] resize-none border-none bg-transparent px-2 py-1.5 text-sm shadow-none focus-visible:ring-0"
      />

      <div className="mt-1 flex items-center justify-between px-1">
        <Popover>
          <PopoverTrigger asChild>
            <Button variant="ghost" size="sm" className="gap-1.5 rounded-full text-xs text-muted-foreground">
              <SlidersHorizontal className="h-3.5 w-3.5" />
              <span>Công cụ</span>
            </Button>
          </PopoverTrigger>
          <PopoverContent align="start" className="w-72 space-y-2">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-foreground">
              <Calendar className="h-3.5 w-3.5" />
              <span>Ngày hiệu lực áp dụng</span>
            </div>
            <p className="text-[11px] text-muted-foreground">
              Kiểm tra tình trạng hiệu lực văn bản tại thời điểm này.
            </p>
            <input
              type="date"
              value={asOfDate}
              onChange={(e) => onAsOfDateChange(e.target.value)}
              className="w-full rounded-lg border border-input bg-background px-2.5 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
            />
          </PopoverContent>
        </Popover>

        <div className="flex items-center gap-1.5">
          <Button
            variant="ghost"
            size="sm"
            onClick={onOpenModelSettings}
            className="gap-1.5 rounded-full text-xs text-muted-foreground"
            title="Đổi mô hình LLM trong Cài đặt"
          >
            <Sparkles className="h-3.5 w-3.5 text-primary" />
            <span>{modelLabel}</span>
            <ChevronDown className="h-3 w-3 opacity-60" />
          </Button>
          <Button
            size="icon"
            onClick={submit}
            disabled={!value.trim() || isLoading}
            className="h-8 w-8 flex-shrink-0 rounded-full"
            title="Gửi câu hỏi"
          >
            <ArrowUp className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
};
