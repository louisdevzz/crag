"use client";

import React from "react";
import { Activity, Calendar, Layers, ShieldCheck } from "lucide-react";

interface NavbarProps {
  asOfDate: string;
  onDateChange: (date: string) => void;
  isTraceOpen: boolean;
  onToggleTrace: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  asOfDate,
  onDateChange,
  isTraceOpen,
  onToggleTrace,
}) => {
  return (
    <header className="h-14 bg-white border-b border-slate-200 px-5 flex items-center justify-between flex-shrink-0">
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 text-xs font-medium text-slate-700 bg-slate-50 px-2.5 py-1 rounded-md border border-slate-200">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
          <span>FastAPI Gateway: 8000</span>
        </div>
        <div className="hidden sm:flex items-center gap-1.5 text-xs text-slate-600 bg-purple-50 text-purple-700 border border-purple-200 px-2.5 py-1 rounded-md font-semibold">
          <Layers className="w-3.5 h-3.5" />
          <span>LangGraph + Chroma + BM25</span>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 text-xs text-slate-600">
          <Calendar className="w-3.5 h-3.5 text-slate-400" />
          <label htmlFor="as-of-date" className="hidden md:inline font-medium">
            Ngày hiệu lực:
          </label>
          <input
            id="as-of-date"
            type="date"
            value={asOfDate}
            onChange={(e) => onDateChange(e.target.value)}
            className="border border-slate-200 rounded px-2 py-1 text-xs text-slate-800 bg-white focus:outline-none focus:border-blue-500"
            title="Kiểm tra tình trạng hiệu lực văn bản tại thời điểm này"
          />
        </div>

        <button
          onClick={onToggleTrace}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium border transition-colors ${
            isTraceOpen
              ? "bg-blue-50 text-blue-700 border-blue-300"
              : "bg-white text-slate-700 border-slate-200 hover:bg-slate-50"
          }`}
          title="Bật/Tắt bảng theo dõi vết thực thi CRAG"
        >
          <Activity className="w-3.5 h-3.5 text-blue-600" />
          <span>Bảng Vết Thực Thi</span>
        </button>
      </div>
    </header>
  );
};
