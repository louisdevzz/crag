"use client";

import React, { useState } from "react";
import { Send } from "lucide-react";

interface ChatInputProps {
  onSendMessage: (text: string) => void;
  isLoading: boolean;
}

export const ChatInput: React.FC<ChatInputProps> = ({
  onSendMessage,
  isLoading,
}) => {
  const [input, setInput] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;
    onSendMessage(input.trim());
    setInput("");
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <div className="p-4 bg-white border-t border-slate-200 flex-shrink-0">
      <form
        onSubmit={handleSubmit}
        className="flex items-end gap-2 bg-slate-50 border border-slate-200 focus-within:border-blue-500 focus-within:bg-white rounded-xl p-2 transition-all"
      >
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Nhập câu hỏi tra cứu pháp lý bằng tiếng Việt... (Enter để gửi, Shift+Enter xuống dòng)"
          rows={1}
          className="flex-1 bg-transparent border-none outline-none text-sm text-slate-800 placeholder:text-slate-400 p-1 resize-none max-h-32"
          disabled={isLoading}
        />
        <button
          type="submit"
          disabled={!input.trim() || isLoading}
          className="bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white p-2 rounded-lg font-medium transition-colors flex-shrink-0 flex items-center justify-center"
          title="Gửi câu hỏi"
        >
          <Send className="w-4 h-4" />
        </button>
      </form>
      <div className="text-[11px] text-slate-400 text-center mt-2">
        Mọi câu trả lời đều được kiểm định xác thực từ kho văn bản quy phạm pháp luật nội bộ hoặc cổng thông tin chính thống.
      </div>
    </div>
  );
};
