"use client";

import React, { useMemo, useState } from "react";
import { Check, Copy, Globe, RotateCcw, Scale, Sparkles, ThumbsDown, ThumbsUp } from "lucide-react";
import { EvidenceItem, Message } from "@/lib/types";
import { MarkdownMessage } from "./markdown-message";
import { MessageScroller } from "./message-scroller";
import LoadingState from "@/components/beautiful/LoadingState";
import ThinkingState, { ThinkingRow } from "@/components/beautiful/ThinkingState";
import ToolChips, { ToolDiff, ToolStep } from "@/components/beautiful/ToolChips";
import ContextCards, { ContextChunk } from "@/components/beautiful/ContextCards";
import SelectionActions from "@/components/beautiful/SelectionActions";
import StreamingText from "@/components/beautiful/StreamingText";
import { cn } from "@/lib/utils";

interface MessageListProps {
  messages: Message[];
  isLoading: boolean;
  liveStage: number | null;
  onFollowUp?: (query: string) => void;
  onRetry?: () => void;
}

function toContextChunks(evidence?: EvidenceItem[]): ContextChunk[] {
  if (!evidence || evidence.length === 0) return [];
  return evidence.map((e, idx) => {
    const isExt = Boolean(e.source_url || (e.strip_id && e.strip_id.startsWith("EXT_")));
    return {
      title: e.heading || `Căn cứ pháp lý #${idx + 1}`,
      chars: e.strip_id || e.locator || `${(e.text || "").length} ký tự`,
      body: e.text || "",
      source:
        e.metadata?.document_title ||
        (isExt ? "Cổng thông tin pháp luật chính thống" : "Kho văn bản QPPL nội bộ"),
      badge: isExt ? "Cổng Web" : "Văn bản QPPL",
      tone: isExt ? "bg-orange" : "bg-accent",
      sourceUrl: e.source_url,
    };
  });
}

function toToolSteps(msg: Message): ToolStep[] {
  const steps: ToolStep[] = [];
  const trace = msg.trace;
  if (!trace) return steps;

  if (trace.route === "rag" || (trace.evidence && trace.evidence.length > 0)) {
    steps.push({
      icon: "search",
      label: "crag_search",
      chip: `evidence: ${trace.evidence?.length || 0} mục`,
      mono: true,
      detailMono: true,
      detail: [
        { text: `✓ Phân luồng: ${trace.route.toUpperCase()}`, tone: "ctx" },
        {
          text: `✓ Đánh giá CRAG: ${trace.cragAction || "CORRECT"}`,
          tone: trace.cragAction === "CORRECT" ? "add" : "ctx",
        },
      ],
    });
  }

  const extEvidence = (trace.evidence || []).filter(
    (e) => e.source_url || (e.strip_id && e.strip_id.startsWith("EXT_")),
  );
  if (extEvidence.length > 0) {
    steps.push({
      icon: "run",
      label: "controlled_web_search",
      chip: `${extEvidence.length} kết quả TinyFish`,
      mono: true,
      detailMono: true,
      detail: [
        {
          text: `✓ Nguồn tra cứu: ${extEvidence
            .map((e) => e.source_domain || "vbpl.vn")
            .slice(0, 3)
            .join(", ")}`,
          tone: "add",
        },
      ],
    });
  }

  if (msg.citationReport && msg.citationReport.valid_citations?.length > 0) {
    steps.push({
      icon: "read",
      label: "validate_citations",
      chip: `độ chính xác ${(msg.citationReport.citation_accuracy * 100).toFixed(0)}%`,
      mono: true,
      detailMono: true,
      detail: [
        {
          text: `✓ Căn cứ hợp lệ: ${msg.citationReport.valid_citations.join(", ")}`,
          tone: "add",
        },
      ],
    });
  }

  return steps;
}

function toThinkingRows(msg: Message): ThinkingRow[] {
  const rows: ThinkingRow[] = [];
  const isRag =
    (msg.trace?.route || "").toLowerCase() === "rag" ||
    (msg.trace?.evidence?.length || 0) > 0;

  rows.push({ primary: "Phân tích yêu cầu pháp lý của người dùng" });
  if (isRag) {
    rows.push({
      primary: "Tra cứu kho tri thức văn bản quy phạm",
      secondary: `${msg.trace?.evidence?.length || 0} căn cứ`,
    });
    if (msg.trace?.cragAction) {
      rows.push({
        primary: `Tự hiệu chỉnh CRAG: ${msg.trace.cragAction}`,
        secondary:
          msg.trace.cragAction === "CORRECT"
            ? "Bằng chứng đầy đủ"
            : "Mở rộng tra cứu cổng công quyền",
      });
    }
  }
  if (
    msg.citationReport?.valid_citations &&
    msg.citationReport.valid_citations.length > 0
  ) {
    rows.push({
      primary: "Kiểm tra hiệu lực thời gian & đối chiếu điều khoản",
      secondary: `${msg.citationReport.valid_citations.length} điều luật`,
    });
  }
  rows.push({ primary: "Hoàn thiện kết luận pháp lý và trích dẫn chuẩn hóa" });
  return rows;
}

function getFollowUpsForMessage(content: string): string[] {
  const lower = content.toLowerCase();
  if (lower.includes("thời giờ làm việc") || lower.includes("giờ làm")) {
    return [
      "Quy định về thời gian nghỉ ngơi giữa ca làm việc?",
      "Tiền lương làm thêm giờ vào ban đêm tính thế nào?",
      "Người lao động làm việc vào ngày lễ được hưởng lương bao nhiêu?",
    ];
  }
  if (lower.includes("nghỉ phép") || lower.includes("nghỉ hàng năm")) {
    return [
      "Số ngày nghỉ phép năm tăng theo thâm niên làm việc ra sao?",
      "Tiền lương những ngày chưa nghỉ hết phép năm được tính thế nào?",
    ];
  }
  if (lower.includes("hợp đồng lao động") || lower.includes("sa thải")) {
    return [
      "Thời hạn báo trước khi đơn phương chấm dứt hợp đồng?",
      "Điều kiện được hưởng trợ cấp thôi việc?",
    ];
  }
  return [
    "Văn bản pháp luật nào quy định chi tiết vấn đề này?",
    "Doanh nghiệp cần lưu ý những thủ tục gì để tránh bị phạt?",
  ];
}

export const MessageList: React.FC<MessageListProps> = ({
  messages,
  isLoading,
  liveStage,
  onFollowUp,
  onRetry,
}) => {
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const handleCopy = (id: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const getStageLabel = (stage: number | null) => {
    switch (stage) {
      case 0:
        return "Đang suy nghĩ...";
      case 1:
        return "Đang tra cứu kho tri thức pháp lý...";
      case 2:
        return "Đang đánh giá căn cứ & cổng pháp luật...";
      case 3:
        return "Đang hoàn thiện câu trả lời...";
      default:
        return "Đang xử lý...";
    }
  };

  return (
    <MessageScroller
      busy={isLoading}
      label="Hội thoại pháp lý"
      className="flex-1"
      contentClassName="mx-auto flex w-full max-w-3xl flex-col gap-6 px-4 py-6"
    >
      {messages.map((msg) => {
        const contextChunks = toContextChunks(msg.trace?.evidence);
        const toolSteps = toToolSteps(msg);
        const thinkingRows = toThinkingRows(msg);
        const followUps = getFollowUpsForMessage(msg.content);

        return (
          <div
            key={msg.id}
            className={`flex flex-col ${
              msg.role === "user" ? "items-end" : "items-start"
            }`}
          >
            {msg.role === "user" ? (
              <div className="group flex flex-col items-end gap-1 max-w-[80%] sm:max-w-[70%]">
                <div className="rounded-2xl bg-secondary px-4 py-2.5 text-sm leading-relaxed text-secondary-foreground shadow-xs">
                  {msg.content}
                </div>
                <div className="flex items-center gap-2 px-1 text-[11px] text-muted-foreground/60 opacity-0 group-hover:opacity-100 transition-opacity">
                  <span>
                    {new Date(msg.timestamp).toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </span>
                  <button
                    type="button"
                    onClick={() => handleCopy(msg.id, msg.content)}
                    className="hover:text-foreground transition-colors p-0.5 cursor-pointer"
                    title="Sao chép câu hỏi"
                  >
                    {copiedId === msg.id ? (
                      <Check className="h-3 w-3 text-emerald-500" />
                    ) : (
                      <Copy className="h-3 w-3" />
                    )}
                  </button>
                </div>
              </div>
            ) : (
              <div className="flex w-full items-start gap-3.5 group">
                <div className="min-w-0 flex-1 flex flex-col gap-3">
                  {/* 02 Thinking: Expandable traces — steps, reasoning, search */}
                  <ThinkingState
                    variant={
                      (msg.trace?.evidence || []).some((e) => e.source_url)
                        ? "Search"
                        : "Steps"
                    }
                    isWorking={msg.isStreaming}
                    rows={thinkingRows}
                    duration={
                      msg.durationMs ? msg.durationMs / 1000 : undefined
                    }
                    query={
                      (msg.trace?.evidence || []).find((e) => e.source_url)
                        ? "Cổng thông tin pháp luật chính thống"
                        : undefined
                    }
                  />

                  {/* 04 Tool Chips: compact chips showing tool calls */}
                  {toolSteps.length > 0 && (
                    <ToolChips
                      steps={toolSteps}
                      labels={{
                        header: `${toolSteps.length} công cụ tra cứu đã thực thi`,
                      }}
                    />
                  )}

                  {/* 06 Selection Actions wrapped around the Markdown message */}
                  <SelectionActions
                    onAction={(actionId, selectedText) => {
                      if (actionId === "handoff" && onFollowUp) {
                        onFollowUp(`Giải thích thêm về quy định: "${selectedText}"`);
                      }
                    }}
                  >
                    <MarkdownMessage
                      content={msg.content}
                      evidence={msg.trace?.evidence}
                      claims={msg.claims}
                      isStreaming={msg.isStreaming}
                    />
                  </SelectionActions>

                  {/* 05 Context Cards: Retrieved knowledge chunks with their sources */}
                  {contextChunks.length > 0 && (
                    <div className="mt-2">
                      <ContextCards
                        chunks={contextChunks}
                        labels={{
                          header: "Căn cứ pháp lý viện dẫn",
                          count: `${contextChunks.length} căn cứ`,
                        }}
                      />
                    </div>
                  )}

                  {/* 03 Streaming Text Actions Bar (Copy, Retry, Thumbs Up/Down, Follow-ups) */}
                  <StreamingText
                    isStreaming={msg.isStreaming}
                    onCopy={() => handleCopy(msg.id, msg.content)}
                    onRetry={onRetry}
                    onFollowUp={onFollowUp}
                    followUps={followUps}
                    sources={contextChunks.map((c) => ({
                      name: c.title,
                      domain: c.source,
                      href: c.sourceUrl,
                    }))}
                  />
                </div>
              </div>
            )}
          </div>
        );
      })}

      {/* 01 Loading State: Pixel-grid loader with shimmer and live elapsed time */}
      {isLoading && liveStage !== null && (
        <div className="flex w-full items-start gap-3.5 pt-1">
          <LoadingState
            variant="Drive"
            label={getStageLabel(liveStage)}
            className="shadow-sm"
          />
        </div>
      )}
    </MessageScroller>
  );
};
