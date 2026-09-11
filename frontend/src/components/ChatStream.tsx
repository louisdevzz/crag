"use client";

import React, { useEffect, useRef } from "react";
import { Message } from "../lib/types";

interface ChatStreamProps {
  messages: Message[];
  isLoading: boolean;
  onSelectPrompt: (prompt: string) => void;
}

const SAMPLE_PROMPTS = [
  "Đối tượng tham gia bảo hiểm xã hội bắt buộc theo quy định hiện hành gồm những ai?",
  "Văn bản số 41/2024/QH15 còn hiệu lực không?",
  "Tôi phụ trách công ty TNHH tại Long An, điều kiện hưởng chế độ thai sản thế nào?",
];

export const ChatStream: React.FC<ChatStreamProps> = ({
  messages,
  isLoading,
  onSelectPrompt,
}) => {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  const renderFormattedText = (text: string) => {
    // Replace citations [DOC_...] or [EXT_...] with styled span
    const parts = text.split(/(\[[A-Za-z0-9_\-]+\])/g);
    return parts.map((part, i) => {
      if (part.startsWith("[") && part.endsWith("]")) {
        return (
          <span
            key={i}
            className="inline-block bg-purple-100 text-purple-800 font-mono text-[11px] font-semibold px-1.5 py-0.5 rounded border border-purple-200 mx-0.5"
          >
            {part}
          </span>
        );
      }
      return part;
    });
  };

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6">
      {messages.length === 0 ? (
        <div className="max-w-2xl mx-auto my-12 text-center flex flex-col items-center space-y-4">
          <span className="text-xs font-semibold text-blue-700 bg-blue-50 border border-blue-200 px-3 py-1 rounded-full">
            Hệ thống Tác tử Tự hiệu chỉnh Truy hồi CRAG
          </span>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
            Trợ lý Tuân thủ & Pháp lý Doanh nghiệp
          </h1>
          <p className="text-sm text-slate-600 max-w-lg leading-relaxed">
            Hệ thống tự động đánh giá chất lượng bằng chứng, tự hiệu chỉnh truy hồi qua 3 nhánh rẽ và kiểm định trích dẫn xác định từ kho văn bản quy phạm pháp luật.
          </p>

          <div className="flex flex-wrap justify-center gap-2 pt-2">
            {SAMPLE_PROMPTS.map((prompt, idx) => (
              <button
                key={idx}
                onClick={() => onSelectPrompt(prompt)}
                className="bg-white hover:bg-slate-50 text-slate-700 hover:text-blue-600 border border-slate-200 hover:border-blue-300 text-xs px-3 py-2 rounded-xl transition-all shadow-sm text-left max-w-md"
              >
                {prompt}
              </button>
            ))}
          </div>
        </div>
      ) : (
        messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex flex-col ${
              msg.role === "user" ? "items-end" : "items-start"
            }`}
          >
            <span className="text-[11px] font-semibold text-slate-400 mb-1 px-1">
              {msg.role === "user" ? "BẠN" : "TRỢ LÝ PHÁP LÝ AI"}
            </span>
            <div
              className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed whitespace-pre-line ${
                msg.role === "user"
                  ? "bg-blue-600 text-white rounded-br-sm shadow-sm"
                  : "bg-white text-slate-900 border border-slate-200 rounded-bl-sm shadow-sm"
              }`}
            >
              {renderFormattedText(msg.content)}
            </div>
          </div>
        ))
      )}

      {isLoading && (
        <div className="flex flex-col items-start">
          <span className="text-[11px] font-semibold text-slate-400 mb-1 px-1">
            TRỢ LÝ PHÁP LÝ AI
          </span>
          <div className="bg-white border border-slate-200 rounded-2xl rounded-bl-sm px-4 py-3 text-sm text-slate-500 italic shadow-sm flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-blue-500 animate-ping"></span>
            <span>Đang phân luồng và truy hồi bằng chứng pháp lý...</span>
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
};
