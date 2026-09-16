"use client";

import React, { useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { AlertTriangle, ArrowLeft, CheckCircle2, Circle, Loader2 } from "lucide-react";
import {
  fetchAdminDocumentChunks,
  fetchAdminDocumentDetail,
  fetchDocuments,
  fetchHistory,
} from "../../../lib/api";
import {
  AdminDocumentDetail,
  ChunkItem,
  HistoryItem,
  LegalDocument,
} from "../../../lib/types";
import { summarizeHistoryBySession } from "../../../lib/history";
import { StatusPill, stageLabel } from "../../../components/admin/StatusPill";
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";
import { AppSidebar } from "../../../components/chat/app-sidebar";
import { ChatHeader } from "../../../components/chat/chat-header";

const POLL_INTERVAL_MS = 1500;

type StageRowKey = "PARSING" | "OCR" | "STRUCTURING" | "CHUNKING" | "EMBEDDING_INDEXING" | "DONE";

const STAGE_ROWS: { key: StageRowKey; rawStage: string }[] = [
  { key: "PARSING", rawStage: "PARSING" },
  { key: "OCR", rawStage: "OCR" },
  { key: "STRUCTURING", rawStage: "STRUCTURING" },
  { key: "CHUNKING", rawStage: "CHUNKING" },
  { key: "EMBEDDING_INDEXING", rawStage: "EMBEDDING" },
  { key: "DONE", rawStage: "DONE" },
];

const STAGE_ROW_KEY_BY_RAW_STAGE: Record<string, StageRowKey> = {
  PARSING: "PARSING",
  OCR: "OCR",
  STRUCTURING: "STRUCTURING",
  CHUNKING: "CHUNKING",
  EMBEDDING: "EMBEDDING_INDEXING",
  INDEXING: "EMBEDDING_INDEXING",
  DONE: "DONE",
};

function formatChunkPages(pageStart: number | null, pageEnd: number | null): string | null {
  if (pageStart === null) return null;
  if (pageEnd === null || pageEnd === pageStart) return `Trang ${pageStart}`;
  return `Trang ${pageStart}-${pageEnd}`;
}

function chunkHeading(chunk: ChunkItem): string {
  const parts = [chunk.chapter, chunk.article, chunk.clause, chunk.point].filter((p): p is string => !!p);
  if (parts.length > 0) return parts.join(" - ");
  return chunk.heading || `Đoạn #${chunk.chunk_index + 1}`;
}

function Meta({ label, value }: { label: string; value: string | null }) {
  if (!value) return null;
  return (
    <div>
      <div className="text-[10px] text-muted-foreground uppercase font-bold tracking-wider">{label}</div>
      <div className="text-foreground font-medium mt-0.5">{value}</div>
    </div>
  );
}

export default function DocumentDetailPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const id = searchParams.get("id") || "";

  const [doc, setDoc] = useState<AdminDocumentDetail | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [loading, setLoading] = useState(true);
  const [observedStages, setObservedStages] = useState<Set<string>>(new Set());
  const [chunks, setChunks] = useState<ChunkItem[]>([]);
  const [chunksLoading, setChunksLoading] = useState(true);
  const pollRef = useRef<number | null>(null);
  const prevStatusRef = useRef<string | null>(null);

  // Sidebar states
  const [clientId, setClientId] = useState<string>("");
  const [sidebarDocs, setSidebarDocs] = useState<LegalDocument[]>([]);
  const [historyItems, setHistoryItems] = useState<HistoryItem[]>([]);

  useEffect(() => {
    let cid = localStorage.getItem("legal_crag_client_id");
    if (!cid) {
      cid = "client_" + Math.random().toString(36).substring(2, 11);
      localStorage.setItem("legal_crag_client_id", cid);
    }
    setClientId(cid);

    fetchDocuments().then(setSidebarDocs);
    fetchHistory(cid).then(setHistoryItems);
  }, []);

  const loadChunks = async (docId: string) => {
    setChunksLoading(true);
    const items = await fetchAdminDocumentChunks(docId);
    setChunks(items);
    setChunksLoading(false);
  };

  useEffect(() => {
    if (!id) {
      setNotFound(true);
      setLoading(false);
      return;
    }
    let cancelled = false;
    (async () => {
      setLoading(true);
      const detail = await fetchAdminDocumentDetail(id);
      if (cancelled) return;
      if (!detail) {
        setNotFound(true);
        setLoading(false);
        return;
      }
      setDoc(detail);
      if (detail.job?.stage) {
        setObservedStages((prev) => new Set(prev).add(detail.job!.stage));
      }
      prevStatusRef.current = detail.status;
      setLoading(false);
      await loadChunks(id);
    })();
    return () => {
      cancelled = true;
    };
  }, [id]);

  useEffect(() => {
    if (!id || !doc || doc.status !== "PROCESSING") {
      if (pollRef.current) {
        window.clearInterval(pollRef.current);
        pollRef.current = null;
      }
      return;
    }

    pollRef.current = window.setInterval(async () => {
      const updated = await fetchAdminDocumentDetail(id);
      if (!updated) return;
      setDoc(updated);
      if (updated.job?.stage) {
        setObservedStages((prev) => new Set(prev).add(updated.job!.stage));
      }
      if (prevStatusRef.current === "PROCESSING" && updated.status === "READY") {
        await loadChunks(id);
      }
      prevStatusRef.current = updated.status;
      if (updated.status !== "PROCESSING") {
        if (pollRef.current) {
          window.clearInterval(pollRef.current);
          pollRef.current = null;
        }
      }
    }, POLL_INTERVAL_MS);

    return () => {
      if (pollRef.current) {
        window.clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [doc?.status, id]);

  const currentRawStage = doc?.job?.stage ?? null;
  const currentRowKey = currentRawStage ? STAGE_ROW_KEY_BY_RAW_STAGE[currentRawStage] ?? null : null;
  const visibleRows = STAGE_ROWS.filter(
    (row) => row.key !== "OCR" || observedStages.has("OCR") || currentRawStage === "OCR"
  );
  const currentIndex = currentRowKey ? visibleRows.findIndex((row) => row.key === currentRowKey) : -1;
  const errorMessage = doc?.job?.error_message || doc?.error_message;

  const conversations = summarizeHistoryBySession(historyItems);

  return (
    <SidebarProvider>
      <AppSidebar
        clientId={clientId}
        documents={sidebarDocs}
        conversations={conversations}
        activeSessionId=""
        memoryCount={0}
        onNewChat={() => router.push("/")}
        onSelectConversation={(sessionId) => router.push(`/?session_id=${sessionId}`)}
        onSelectPrompt={(prompt) => router.push(`/?prompt=${encodeURIComponent(prompt)}`)}
      />

      <SidebarInset className="flex h-screen flex-col overflow-hidden bg-background">
        <ChatHeader
          rightAction={
            <Link
              href="/admin"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border border-border bg-card hover:bg-muted text-foreground transition-colors cursor-pointer shadow-2xs"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>Quay lại danh mục</span>
            </Link>
          }
        />

        <main className="flex-1 overflow-y-auto p-6 space-y-6">
          {loading ? (
            <div className="flex h-64 items-center justify-center text-sm text-muted-foreground">
              <Loader2 className="h-5 w-5 animate-spin mr-2" />
              <span>Đang tải thông tin văn bản...</span>
            </div>
          ) : notFound || !doc ? (
            <div className="flex flex-col h-64 items-center justify-center gap-3">
              <p className="text-sm text-muted-foreground">Không tìm thấy văn bản quy phạm pháp luật.</p>
              <Link href="/admin" className="text-xs font-semibold text-primary underline">
                Quay lại danh mục
              </Link>
            </div>
          ) : (
            <>
              {/* Header card */}
              <div className="bg-card border border-border rounded-2xl p-5 shadow-xs">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h1 className="text-base font-bold text-foreground truncate">{doc.filename}</h1>
                    <p className="text-xs text-muted-foreground mt-0.5 truncate">{doc.title}</p>
                  </div>
                  <StatusPill status={doc.status} stage={doc.stage} errorMessage={doc.error_message} />
                </div>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-5 text-xs border-t border-border pt-4">
                  <Meta label="Số hiệu" value={doc.document_number} />
                  <Meta label="Loại văn bản" value={doc.document_type} />
                  <Meta label="Cơ quan ban hành" value={doc.issuing_authority} />
                  <Meta label="Ngày có hiệu lực" value={doc.effective_from} />
                </div>
              </div>

              {/* Ingestion Pipeline Stages */}
              <div className="bg-card border border-border rounded-2xl p-5 shadow-xs">
                <h2 className="text-xs font-bold uppercase tracking-wider text-muted-foreground mb-4">
                  Tiến trình nạp & lập chỉ mục
                </h2>

                <div className="space-y-3">
                  {visibleRows.map((row, idx) => {
                    const isDone =
                      doc.status === "READY" ||
                      observedStages.has(row.rawStage) ||
                      (currentIndex >= 0 && idx < currentIndex);
                    const isCurrent = doc.status === "PROCESSING" && idx === currentIndex;
                    const isFailed = doc.status === "FAILED" && (idx === currentIndex || currentIndex === -1);

                    return (
                      <div key={row.key} className="flex items-center gap-3 text-xs">
                        <div className="flex-shrink-0">
                          {isFailed ? (
                            <AlertTriangle className="w-4 h-4 text-rose-500" />
                          ) : isDone ? (
                            <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                          ) : isCurrent ? (
                            <Loader2 className="w-4 h-4 text-primary animate-spin" />
                          ) : (
                            <Circle className="w-4 h-4 text-muted-foreground/30" />
                          )}
                        </div>

                        <div className="flex-1 min-w-0">
                          <span
                            className={
                              isCurrent
                                ? "font-semibold text-foreground"
                                : isDone
                                ? "text-foreground/90"
                                : "text-muted-foreground"
                            }
                          >
                            {stageLabel(row.rawStage)}
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>

                {errorMessage && (
                  <div className="mt-4 p-3 rounded-xl border border-rose-500/20 bg-rose-500/10 text-xs text-rose-600">
                    <span className="font-semibold">Lỗi: </span>
                    {errorMessage}
                  </div>
                )}
              </div>

              {/* Chunks table */}
              <div className="bg-card border border-border rounded-2xl p-5 shadow-xs">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                    Các phân đoạn đã bóc tách (Chunks: {chunks.length})
                  </h2>
                </div>

                {chunksLoading ? (
                  <div className="py-8 text-center text-xs text-muted-foreground">
                    <Loader2 className="w-4 h-4 animate-spin inline mr-2" />
                    Đang tải phân đoạn...
                  </div>
                ) : chunks.length === 0 ? (
                  <div className="py-8 text-center text-xs text-muted-foreground italic">
                    Chưa có phân đoạn nào được lập chỉ mục.
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b border-border text-left text-muted-foreground">
                          <th className="pb-2 font-medium w-16">STT</th>
                          <th className="pb-2 font-medium w-36">Tiêu đề / Điều khoản</th>
                          <th className="pb-2 font-medium">Nội dung trích xuất</th>
                          <th className="pb-2 font-medium w-24 text-right">Trang</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border/60">
                        {chunks.map((c) => (
                          <tr key={c.id} className="hover:bg-muted/40">
                            <td className="py-2.5 font-mono text-muted-foreground">#{c.chunk_index + 1}</td>
                            <td className="py-2.5 font-medium text-foreground pr-3">
                              {chunkHeading(c)}
                            </td>
                            <td className="py-2.5 text-foreground/80 leading-relaxed pr-3 line-clamp-2">
                              {c.content}
                            </td>
                            <td className="py-2.5 text-right font-mono text-muted-foreground">
                              {formatChunkPages(c.page_start, c.page_end) || "—"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </>
          )}
        </main>
      </SidebarInset>
    </SidebarProvider>
  );
}
