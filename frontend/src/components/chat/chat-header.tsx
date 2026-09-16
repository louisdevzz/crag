"use client";

import React from "react";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { AppTabs } from "@/components/AppTabs";

interface ChatHeaderProps {
  rightAction?: React.ReactNode;
}

export const ChatHeader: React.FC<ChatHeaderProps> = ({ rightAction }) => {
  return (
    <header className="flex h-14 flex-shrink-0 items-center justify-between border-b border-border px-4 bg-background">
      <div className="flex items-center gap-3">
        <SidebarTrigger />
        <AppTabs />
      </div>
      {rightAction && <div className="flex items-center gap-2">{rightAction}</div>}
    </header>
  );
};
