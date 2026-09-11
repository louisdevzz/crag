"use client";

import React from "react";
import { Building2, HeartPulse, Receipt, Scale } from "lucide-react";
import { PromptComposer } from "./prompt-composer";

const QUICK_PROMPTS = [
  {
    icon: Scale,
    label: "Kiểm tra hiệu lực văn bản",
    prompt: "Văn bản số 41/2024/QH15 còn hiệu lực không?",
  },
  {
    icon: HeartPulse,
    label: "Bảo hiểm xã hội",
    prompt:
      "Đối tượng tham gia bảo hiểm xã hội bắt buộc theo quy định hiện hành gồm những ai?",
  },
  {
    icon: Building2,
    label: "Chế độ thai sản",
    prompt: "Tôi phụ trách công ty TNHH tại Long An, điều kiện hưởng chế độ thai sản thế nào?",
  },
  {
    icon: Receipt,
    label: "Thuế doanh nghiệp",
    prompt: "Doanh nghiệp mới thành lập được miễn, giảm những loại thuế nào?",
  },
];

interface WelcomeHeroProps {
  onSend: (text: string) => void;
  isLoading: boolean;
  asOfDate: string;
  onAsOfDateChange: (date: string) => void;
  modelLabel: string;
  onOpenModelSettings: () => void;
}

export const WelcomeHero: React.FC<WelcomeHeroProps> = ({
  onSend,
  isLoading,
  asOfDate,
  onAsOfDateChange,
  modelLabel,
  onOpenModelSettings,
}) => {
  return (
    <div className="mx-auto flex w-full max-w-2xl flex-1 flex-col items-center justify-center gap-6 px-4">
      <div className="space-y-2 text-center">
        <h1 className="bg-gradient-to-r from-primary to-indigo-400 bg-clip-text text-3xl font-bold tracking-tight text-transparent">
          Xin chào, Tôi có thể giúp gì cho bạn?
        </h1>
        <p className="mx-auto max-w-lg text-sm leading-relaxed text-muted-foreground">
          Trợ lý tự hiệu chỉnh truy hồi (CRAG) — tra cứu pháp luật doanh nghiệp Việt Nam với bằng
          chứng được kiểm định và trích dẫn xác thực từ kho văn bản quy phạm pháp luật.
        </p>
      </div>

      <PromptComposer
        onSend={onSend}
        isLoading={isLoading}
        asOfDate={asOfDate}
        onAsOfDateChange={onAsOfDateChange}
        modelLabel={modelLabel}
        onOpenModelSettings={onOpenModelSettings}
        className="w-full"
      />

      <div className="flex flex-wrap justify-center gap-2">
        {QUICK_PROMPTS.map(({ icon: Icon, label, prompt }) => (
          <button
            key={label}
            type="button"
            onClick={() => onSend(prompt)}
            disabled={isLoading}
            className="flex items-center gap-1.5 rounded-full border border-border bg-card px-3.5 py-2 text-xs font-medium text-foreground transition-colors hover:bg-accent disabled:opacity-50"
          >
            <Icon className="h-3.5 w-3.5 text-primary" />
            <span>{label}</span>
          </button>
        ))}
      </div>
    </div>
  );
};
