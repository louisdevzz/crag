"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Database, MessageSquare } from "lucide-react";

const TABS = [
  { href: "/", label: "Trò chuyện", icon: MessageSquare },
  { href: "/admin/", label: "Quản lý Dữ liệu", icon: Database },
];

export const AppTabs: React.FC = () => {
  const pathname = usePathname();

  return (
    <nav className="flex items-center gap-1 bg-dsh-surface border border-dsh-border rounded-full p-0.5">
      {TABS.map(({ href, label, icon: Icon }) => {
        const isActive = href === "/" ? pathname === "/" : pathname?.startsWith("/admin");
        return (
          <Link
            key={href}
            href={href}
            className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold transition-colors ${
              isActive
                ? "bg-white text-dsh-ink shadow-sm border border-dsh-border"
                : "text-dsh-muted hover:text-dsh-ink"
            }`}
          >
            <Icon className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">{label}</span>
          </Link>
        );
      })}
    </nav>
  );
};
