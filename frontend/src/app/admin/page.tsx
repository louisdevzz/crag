"use client";

import React, { useCallback, useEffect, useState } from "react";
import { fetchAdminDocuments, fetchAdminStats } from "../../lib/api";
import { AdminDocument, AdminStats } from "../../lib/types";
import { AdminNavbar } from "../../components/admin/AdminNavbar";
import { StatsCards } from "../../components/admin/StatsCards";
import { DocumentUploadPanel } from "../../components/admin/DocumentUploadPanel";
import { DocumentsTable } from "../../components/admin/DocumentsTable";
import { SettingsModal } from "../../components/SettingsModal";

export default function AdminPage() {
  const [documents, setDocuments] = useState<AdminDocument[]>([]);
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isSettingsOpen, setIsSettingsOpen] = useState<boolean>(false);

  const loadData = useCallback(async () => {
    setIsLoading(true);
    const [docs, statsData] = await Promise.all([fetchAdminDocuments(), fetchAdminStats()]);
    setDocuments(docs);
    setStats(statsData);
    setIsLoading(false);
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleDeleted = (documentId: string) => {
    setDocuments((prev) => prev.filter((d) => d.id !== documentId));
    loadData();
  };

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-white">
      <AdminNavbar onRefresh={loadData} isRefreshing={isLoading} onOpenSettings={() => setIsSettingsOpen(true)} />

      <main className="flex-1 overflow-y-auto p-6 space-y-5 bg-dsh-bg">
        <div>
          <h1 className="text-lg font-bold text-dsh-ink tracking-tight">Quản lý Dữ liệu Kho Tri Thức</h1>
          <p className="text-xs text-dsh-muted mt-0.5">
            Nạp, theo dõi, và gỡ bỏ văn bản quy phạm pháp luật trong cơ sở dữ liệu vector (SQLite + BM25 + Chroma).
          </p>
        </div>

        <StatsCards stats={stats} isLoading={isLoading} />

        <DocumentUploadPanel onIngested={loadData} />

        <DocumentsTable documents={documents} isLoading={isLoading} onDeleted={handleDeleted} />
      </main>

      <SettingsModal isOpen={isSettingsOpen} onClose={() => setIsSettingsOpen(false)} />
    </div>
  );
}
