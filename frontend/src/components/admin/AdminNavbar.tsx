"use client";

import React from "react";
import { RefreshCw, Settings } from "lucide-react";
import { AppTabs } from "../AppTabs";

interface AdminNavbarProps {
  onRefresh: () => void;
  isRefreshing: boolean;
  onOpenSettings: () => void;
}

export const AdminNavbar: React.FC<AdminNavbarProps> = ({ onRefresh, isRefreshing, onOpenSettings }) => {
  return (
    <header className="h-14 bg-white border-b border-dsh-border px-5 flex items-center justify-between flex-shrink-0">
      <div className="flex items-center gap-3">
        <AppTabs />
        <div className="hidden md:flex items-center gap-2 text-xs font-medium text-dsh-ink bg-dsh-surface px-2.5 py-1 rounded-full border border-dsh-border">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
          <span>FastAPI Gateway: 8000</span>
        </div>
        <div className="hidden lg:flex items-center gap-1.5 text-xs text-dsh-muted bg-dsh-surface border border-dsh-border px-2.5 py-1 rounded-full font-semibold">
          <span>SQLite · Chroma · BM25</span>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <button
          onClick={onRefresh}
          disabled={isRefreshing}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border border-dsh-border text-dsh-ink hover:bg-dsh-surface disabled:opacity-50 transition-colors"
          title="Tải lại danh mục và số liệu thống kê"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? "animate-spin" : ""}`} />
          <span>Làm mới</span>
        </button>
        <button
          onClick={onOpenSettings}
          className="flex items-center justify-center p-2 rounded-full border border-dsh-border text-dsh-ink hover:bg-dsh-surface transition-colors"
          title="Cài đặt"
        >
          <Settings className="w-3.5 h-3.5" />
        </button>
      </div>
    </header>
  );
};
