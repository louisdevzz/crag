"use client";

import React, { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { RefreshCw } from "lucide-react";
import {
  deleteConversation,
  fetchAdminDocuments,
  fetchAdminStats,
  fetchDocuments,
  fetchHistory,
} from "../../lib/api";
import {
  AdminDocumentSummary,
  AdminStats,
  HistoryItem,
  LegalDocument,
} from "../../lib/types";
import { summarizeHistoryBySession } from "../../lib/history";
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";
import { AppSidebar } from "../../components/chat/app-sidebar";
import { ChatHeader } from "../../components/chat/chat-header";
import { StatsCards } from "../../components/admin/StatsCards";
import { DocumentUploadPanel } from "../../components/admin/DocumentUploadPanel";
import { DocumentsTable } from "../../components/admin/DocumentsTable";
import { cn } from "@/lib/utils";

export default function AdminPage() {
  const router = useRouter();

  const [documents, setDocuments] = useState<AdminDocumentSummary[]>([]);
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  // Sidebar shared states
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

  const loadData = useCallback(async () => {
    setIsLoading(true);
    const [docs, statsData, sDocs] = await Promise.all([
      fetchAdminDocuments(),
      fetchAdminStats(),
      fetchDocuments(),
    ]);
    setDocuments(docs);
    setStats(statsData);
    setSidebarDocs(sDocs);
    setIsLoading(false);
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleDeleted = (documentId: string) => {
    setDocuments((prev) => prev.filter((d) => d.id !== documentId));
    loadData();
  };

  const handleDeleteConversation = async (sessionId: string) => {
    if (!clientId) return;
    const ok = await deleteConversation(clientId, sessionId);
    if (ok) setHistoryItems((prev) => prev.filter((item) => item.session_id !== sessionId));
  };

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
        onDeleteConversation={handleDeleteConversation}
        onSelectPrompt={(prompt) => router.push(`/?prompt=${encodeURIComponent(prompt)}`)}
      />

      <SidebarInset className="flex h-screen flex-col overflow-hidden bg-background">
        <ChatHeader
          rightAction={
            <button
              type="button"
              onClick={loadData}
              disabled={isLoading}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border border-border bg-card hover:bg-muted text-foreground transition-colors disabled:opacity-50 cursor-pointer shadow-2xs"
              title="Tải lại danh mục và số liệu thống kê"
            >
              <RefreshCw className={cn("w-3.5 h-3.5", isLoading && "animate-spin")} />
              <span>Làm mới</span>
            </button>
          }
        />

        <main className="flex-1 overflow-y-auto p-6 space-y-6">
          <div>
            <h1 className="text-lg font-bold text-foreground tracking-tight">
              Quản lý Dữ liệu Kho Tri Thức
            </h1>
            <p className="text-xs text-muted-foreground mt-0.5">
              Nạp, theo dõi, và gỡ bỏ văn bản quy phạm pháp luật trong kho tri thức pháp lý.
            </p>
          </div>

          <StatsCards stats={stats} isLoading={isLoading} />

          <DocumentUploadPanel onIngested={loadData} onBatchIngested={loadData} />

          <DocumentsTable
            documents={documents}
            isLoading={isLoading}
            onDeleted={handleDeleted}
          />
        </main>
      </SidebarInset>
    </SidebarProvider>
  );
}
