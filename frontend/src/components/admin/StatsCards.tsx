"use client";

import React from "react";
import { AlertTriangle, CheckCircle2, FileText, Loader2 } from "lucide-react";
import { AdminStats } from "../../lib/types";

interface StatsCardsProps {
  stats: AdminStats | null;
  isLoading: boolean;
}

const CARD_DEFS = [
  { key: "total_documents", label: "Tổng văn bản", icon: FileText },
  { key: "ready", label: "Sẵn sàng", icon: CheckCircle2 },
  { key: "processing", label: "Đang xử lý", icon: Loader2 },
  { key: "failed", label: "Lỗi", icon: AlertTriangle },
] as const;

export const StatsCards: React.FC<StatsCardsProps> = ({ stats, isLoading }) => {
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
      {CARD_DEFS.map(({ key, label, icon: Icon }) => (
        <div
          key={key}
          className="bg-white border border-dsh-border rounded-2xl p-4 flex items-center gap-3"
        >
          <div className="w-9 h-9 rounded-xl bg-dsh-surface border border-dsh-border flex items-center justify-center flex-shrink-0 text-dsh-ink">
            <Icon className="w-4.5 h-4.5" />
          </div>
          <div className="min-w-0">
            <div className="text-lg font-bold text-dsh-ink tabular-nums leading-tight">
              {isLoading || !stats ? "—" : stats[key].toLocaleString("vi-VN")}
            </div>
            <div className="text-[11px] text-dsh-muted font-medium truncate">{label}</div>
          </div>
        </div>
      ))}
    </div>
  );
};
