"use client";

import React from "react";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { AppTabs } from "@/components/AppTabs";

export const ChatHeader: React.FC = () => {
  return (
    <header className="flex h-14 flex-shrink-0 items-center gap-3 border-b border-border px-4">
      <SidebarTrigger />
      <AppTabs />
    </header>
  );
};
