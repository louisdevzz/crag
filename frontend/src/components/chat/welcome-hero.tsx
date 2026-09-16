"use client";

import React from "react";
import { PromptComposer } from "./prompt-composer";

interface WelcomeHeroProps {
  onSend: (text: string) => void;
  isLoading: boolean;
  asOfDate: string;
  onAsOfDateChange: (date: string) => void;
  modelLabel: string;
  onOpenModelSettings: () => void;
  onNewChat?: () => void;
}

export const WelcomeHero: React.FC<WelcomeHeroProps> = ({
  onSend,
  isLoading,
  asOfDate,
  onAsOfDateChange,
  modelLabel,
  onOpenModelSettings,
  onNewChat,
}) => {
  return (
    <div className="mx-auto flex w-full max-w-2xl flex-1 flex-col items-center justify-center gap-6 px-4">
      <div className="text-center">
        <h1 className="text-3xl font-bold tracking-tight text-black dark:text-white">
          Xin chào, Tôi có thể giúp gì cho bạn?
        </h1>
      </div>

      <PromptComposer
        onSend={onSend}
        isLoading={isLoading}
        asOfDate={asOfDate}
        onAsOfDateChange={onAsOfDateChange}
        modelLabel={modelLabel}
        onOpenModelSettings={onOpenModelSettings}
        onNewChat={onNewChat}
        className="w-full"
      />
    </div>
  );
};
