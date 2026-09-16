"use client";

import React, { useMemo, useState } from "react";
import { Check, Copy, Globe, Scale, Sparkles } from "lucide-react";
import { EvidenceItem, Message } from "@/lib/types";
import { MarkdownMessage } from "./markdown-message";
import { MessageScroller } from "./message-scroller";
import { StreamingResponse } from "@/components/agents/streaming-response";
import { AgentActivity, AgentActivityItem } from "@/components/agents/agent-activity";
import { CitationItem } from "@/components/agents/citations";
import { cn } from "@/lib/utils";

interface MessageListProps {
  messages: Message[];
  isLoading: boolean;
  liveStage: number | null;
}

function toCitationItems(evidence?: EvidenceItem[]): CitationItem[] {
  if (!evidence || evidence.length === 0) return [];
  const unique: CitationItem[] = [];
  const seen = new Set<string>();

  evidence.forEach((item, i) => {
    const key = item.strip_id || item.evidence_id || `${item.document_number}_${item.heading}` || `ref_${i}`;
    if (!seen.has(key)) {
      seen.add(key);
      const isWeb = item.retrieval_source === "web" || item.strip_id?.startsWith("WEB_");
      unique.push({
        id: item.strip_id || item.evidence_id || `source-${i + 1}`,
        title: item.document_title || item.document_number || item.heading || `Văn bản QPPL #${i + 1}`,
        domain: isWeb ? "Cổng thông tin pháp luật chính thống" : (item.heading || "Kho tri thức văn bản QPPL"),
        excerpt: item.text,
        score: item.score,
      });
    }
  });

  return unique;
}

function toActivityItems(msg: Message): AgentActivityItem[] {
  const items: AgentActivityItem[] = [];
  const isRag = (msg.trace?.route || "").toLowerCase() === "rag" || (msg.trace?.evidence?.length || 0) > 0;
  const action = (msg.trace?.cragAction || "").toUpperCase();

  // Step 1: Think
  items.push({
    id: `${msg.id}-think`,
    type: "text",
    label: "Phân tích yêu cầu",
    content: isRag
      ? "Xác định câu hỏi pháp lý và các văn bản quy phạm liên quan trong kho tri thức doanh nghiệp."
      : "Trao đổi thông thường, giải thích và định hướng tra cứu pháp luật.",
    status: "complete",
  });

  // Step 2: Search (if RAG)
  if (isRag) {
    const evidenceList = msg.trace?.evidence || [];
    items.push({
      id: `${msg.id}-search`,
      type: "search",
      label: "Tra cứu & Bóc tách phân đoạn (Chunking Retrieval)",
      status: "complete",
      meta: evidenceList.length > 0 ? `${evidenceList.length} phân đoạn` : undefined,
      content: (
        <div className="mt-1 space-y-2">
          <p className="text-[11px] text-muted-foreground">
            {evidenceList.length > 0
              ? `Đã bóc tách và nạp ${evidenceList.length} phân đoạn (chunks) từ kho quy phạm pháp luật:`
              : "Truy hồi các điều khoản quy phạm tương ứng."}
          </p>
          {evidenceList.length > 0 && (
            <div className="space-y-1.5 pt-0.5">
              {evidenceList.slice(0, 5).map((chunk, idx) => {
                const title =
                  chunk.heading || chunk.document_title || chunk.locator || `Phân đoạn #${idx + 1}`;
                const scorePercent = chunk.score != null ? Math.round(chunk.score * 100) : null;
                const isWeb = chunk.retrieval_source === "web" || chunk.strip_id?.startsWith("WEB_");
                return (
                  <div
                    key={chunk.strip_id || idx}
                    className="rounded-lg border border-border/70 bg-card/60 p-2 text-left shadow-2xs"
                  >
                    <div className="flex items-center justify-between gap-2 text-[11px]">
                      <span className="font-semibold text-foreground/90 flex items-center gap-1 truncate">
                        {isWeb ? (
                          <Globe className="h-3 w-3 text-blue-500 shrink-0" />
                        ) : (
                          <Scale className="h-3 w-3 text-primary shrink-0" />
                        )}
                        <span className="truncate">{title}</span>
                      </span>
                      {scorePercent != null && (
                        <span className="text-[10px] font-medium text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded shrink-0">
                          {scorePercent}% phù hợp
                        </span>
                      )}
                    </div>
                    {chunk.text && (
                      <div className="mt-1 text-[11px] text-muted-foreground/90 leading-relaxed font-mono bg-muted/30 p-1.5 rounded border border-border/40 line-clamp-2">
                        &ldquo;{chunk.text}&rdquo;
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      ),
    });
  }

  // Step 3: CRAG evaluation (if action exists)
  if (isRag && action) {
    items.push({
      id: `${msg.id}-crag`,
      type: "tool",
      label: `Đánh giá CRAG: Nhánh ${action}`,
      content: action === "CORRECT"
        ? "Bằng chứng pháp lý đầy đủ, thực hiện tinh lọc tri thức (Knowledge Refinement)."
        : action === "AMBIGUOUS"
        ? "Bằng chứng một phần, kết hợp tìm kiếm mở rộng cổng thông tin chính thống."
        : "Bằng chứng nội bộ không đủ, kích hoạt tìm kiếm mạng chính thống.",
      status: "complete",
      meta: action,
    });
  }

  // Step 4: Citation validator
  if (isRag && msg.citationReport && msg.citationReport.valid_citations?.length > 0) {
    const validCount = msg.citationReport.valid_citations.length;
    const accuracy = Math.round((msg.citationReport.citation_accuracy ?? 1) * 100);
    items.push({
      id: `${msg.id}-cite`,
      type: "step",
      label: "Kiểm định trích dẫn",
      content: `${validCount} căn cứ đối chiếu hợp lệ qua Citation Validator.`,
      status: "complete",
      meta: `${accuracy}% chính xác`,
    });
  }

  return items;
}

export const MessageList: React.FC<MessageListProps> = ({ messages, isLoading, liveStage }) => {
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const handleCopy = (id: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <MessageScroller
      busy={isLoading}
      label="Hội thoại pháp lý"
      className="flex-1"
      contentClassName="mx-auto flex w-full max-w-3xl flex-col gap-6 px-4 py-6"
    >
      {messages.map((msg) => {
        const sources = toCitationItems(msg.trace?.evidence);
        const activityItems = toActivityItems(msg);

        return (
          <div
            key={msg.id}
            className={`flex flex-col ${msg.role === "user" ? "items-end" : "items-start"}`}
          >
            {msg.role === "user" ? (
              <div className="group flex flex-col items-end gap-1 max-w-[80%] sm:max-w-[70%]">
                <div className="rounded-2xl bg-secondary px-4 py-2.5 text-sm leading-relaxed text-secondary-foreground shadow-xs">
                  {msg.content}
                </div>
                <div className="flex items-center gap-2 px-1 text-[11px] text-muted-foreground/60 opacity-0 group-hover:opacity-100 transition-opacity">
                  <span>
                    {new Date(msg.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
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
                <div className="mt-0.5 flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary border border-primary/20 shadow-xs">
                  <Sparkles className="h-4 w-4" />
                </div>
                <div className="min-w-0 flex-1">
                  <StreamingResponse
                    status={msg.isStreaming ? "streaming" : "complete"}
                    copyText={msg.content}
                    sources={sources}
                  >
                    {/* Agent Activity Timeline (beui.dev/components/agents/agent-activity) */}
                    {(activityItems.length > 0 || msg.isStreaming) && (
                      <AgentActivity
                        items={activityItems}
                        status={msg.isStreaming ? "working" : "complete"}
                        duration={(msg.durationMs || 0) / 1000}
                        defaultOpen={false}
                        collapseOnComplete={true}
                      />
                    )}

                    {/* Markdown Answer with inline citations (beui.dev/components/agents/citations) */}
                    <MarkdownMessage
                      content={msg.content}
                      evidence={msg.trace?.evidence}
                      claims={msg.claims}
                      isStreaming={msg.isStreaming}
                    />
                  </StreamingResponse>
                </div>
              </div>
            )}
          </div>
        );
      })}

      {/* Streaming state before first token arrives */}
      {isLoading && liveStage !== null && (
        <div className="flex w-full items-start gap-3.5">
          <div className="mt-0.5 flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary border border-primary/20 animate-pulse">
            <Sparkles className="h-4 w-4" />
          </div>
          <div className="min-w-0 flex-1">
            <AgentActivity
              items={[
                {
                  id: "live-step",
                  type: "step",
                  label:
                    liveStage === 0
                      ? "Phân tích câu hỏi & lựa chọn công cụ"
                      : liveStage === 1
                      ? "Truy hồi bằng chứng (CRAG / Web)"
                      : liveStage === 2
                      ? "Đánh giá & tinh lọc căn cứ"
                      : "Kiểm định trích dẫn & hoàn thiện câu trả lời",
                  status: "active",
                },
              ]}
              status="working"
              activeLabel={
                liveStage === 0
                  ? "Đang phân tích câu hỏi…"
                  : liveStage === 1
                  ? "Đang tra cứu kho tri thức…"
                  : liveStage === 2
                  ? "Đang đánh giá căn cứ…"
                  : "Đang hoàn thiện câu trả lời…"
              }
            />
          </div>
        </div>
      )}
    </MessageScroller>
  );
};
