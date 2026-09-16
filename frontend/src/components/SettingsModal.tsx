"use client";

import React, { useEffect, useState } from "react";
import { Check, Database, Settings as SettingsIcon } from "lucide-react";
import { fetchAdminSettings, updateAdminModel } from "../lib/api";
import { AdminSettings, ModelSettings, ProviderOption } from "../lib/types";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { cn } from "@/lib/utils";

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  onModelChange?: (model: ModelSettings) => void;
  memories?: Record<string, string>;
  onClearMemory?: () => void;
  onClearHistory?: () => void;
  hasHistory?: boolean;
}

type Tab = "general" | "models";

export const SettingsModal: React.FC<SettingsModalProps> = ({
  isOpen,
  onClose,
  onModelChange,
  memories = {},
  onClearMemory,
  onClearHistory,
  hasHistory = false,
}) => {
  const [tab, setTab] = useState<Tab>("general");
  const [settings, setSettings] = useState<AdminSettings | null>(null);
  const [selectedProvider, setSelectedProvider] = useState<string>("");
  const [selectedModel, setSelectedModel] = useState<string>("");
  const [isSaving, setIsSaving] = useState(false);
  const [savedNotice, setSavedNotice] = useState(false);

  useEffect(() => {
    if (!isOpen) return;
    (async () => {
      const data = await fetchAdminSettings();
      if (data) {
        setSettings(data);
        setSelectedProvider(data.current.provider);
        setSelectedModel(data.current.model);
      }
    })();
  }, [isOpen]);

  const activeProvider: ProviderOption | undefined = settings?.providers.find(
    (p) => p.provider === selectedProvider
  );

  const handleProviderSwitch = (provider: string) => {
    setSelectedProvider(provider);
    const opt = settings?.providers.find((p) => p.provider === provider);
    setSelectedModel(opt?.default_model || opt?.available_models[0] || "");
    setSavedNotice(false);
  };

  const handleApply = async () => {
    if (!selectedProvider || !selectedModel) return;
    setIsSaving(true);
    try {
      const updated = await updateAdminModel({ provider: selectedProvider, model: selectedModel });
      setSettings((prev) => (prev ? { ...prev, current: updated } : prev));
      setSavedNotice(true);
      onModelChange?.(updated);
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : String(e));
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="flex max-h-[85vh] max-w-2xl flex-col gap-0 overflow-hidden rounded-3xl p-0">
        <DialogHeader className="px-6 py-5 text-left">
          <DialogTitle className="text-xl font-bold">Cài đặt</DialogTitle>
        </DialogHeader>

        <div className="flex min-h-0 flex-1 gap-6 px-6 pb-6">
          <div className="w-40 flex-shrink-0 space-y-1">
            <button
              onClick={() => setTab("general")}
              className={cn(
                "flex w-full items-center gap-2 rounded-xl px-3 py-2 text-sm font-medium transition-colors",
                tab === "general" ? "bg-secondary text-foreground" : "text-muted-foreground hover:text-foreground"
              )}
            >
              <SettingsIcon className="h-4 w-4" />
              <span>Chung</span>
            </button>
            <button
              onClick={() => setTab("models")}
              className={cn(
                "flex w-full items-center gap-2 rounded-xl px-3 py-2 text-sm font-medium transition-colors",
                tab === "models" ? "bg-secondary text-foreground" : "text-muted-foreground hover:text-foreground"
              )}
            >
              <Database className="h-4 w-4" />
              <span>Mô hình</span>
            </button>
          </div>

          <div className="min-w-0 flex-1 overflow-y-auto">
            {!settings ? (
              <div className="py-8 text-center text-sm italic text-muted-foreground">
                Đang tải cấu hình...
              </div>
            ) : tab === "general" ? (
              <GeneralTab
                settings={settings}
                memories={memories}
                onClearMemory={onClearMemory}
                onClearHistory={onClearHistory}
                hasHistory={hasHistory}
              />
            ) : (
              <div>
                <h3 className="mb-1 text-lg font-bold text-foreground">Mô hình</h3>
                <p className="mb-4 text-sm text-muted-foreground">
                  Chọn nhà cung cấp và mô hình LLM đang hoạt động. Thay đổi có hiệu lực ngay cho lượt hỏi tiếp theo.
                </p>

                <div className="mb-4 flex flex-wrap gap-1.5">
                  {settings.providers.map((p) => (
                    <button
                      key={p.provider}
                      onClick={() => handleProviderSwitch(p.provider)}
                      className={cn(
                        "flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-semibold transition-colors",
                        selectedProvider === p.provider
                          ? "border-primary bg-primary text-primary-foreground"
                          : "border-border bg-card text-foreground hover:bg-accent"
                      )}
                    >
                      <span
                        className={cn(
                          "h-1.5 w-1.5 rounded-full",
                          p.configured ? "bg-emerald-400" : "bg-zinc-300"
                        )}
                      />
                      {p.label}
                    </button>
                  ))}
                </div>

                {activeProvider && (
                  <div className="rounded-2xl bg-secondary p-4">
                    <div className="mb-4 flex items-center gap-2">
                      <span className="text-base font-bold text-foreground">{activeProvider.label}</span>
                      <span className="font-mono text-xs text-muted-foreground">{activeProvider.provider}</span>
                      {!activeProvider.configured && (
                        <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-bold text-amber-700">
                          Chưa cấu hình API key
                        </span>
                      )}
                    </div>

                    <label className="mb-2 block text-sm font-semibold text-foreground">
                      Model đang dùng
                    </label>
                    <select
                      value={selectedModel}
                      onChange={(e) => {
                        setSelectedModel(e.target.value);
                        setSavedNotice(false);
                      }}
                      className="w-full rounded-xl border border-input bg-background px-3.5 py-2.5 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
                    >
                      {activeProvider.available_models.map((m) => (
                        <option key={m} value={m}>
                          {m}
                        </option>
                      ))}
                    </select>

                    <div className="my-4 border-t border-border" />

                    <div className="flex items-center justify-end gap-2">
                      {savedNotice && (
                        <span className="mr-auto flex items-center gap-1 text-xs font-semibold text-emerald-700">
                          <Check className="h-3.5 w-3.5" />
                          Đã áp dụng
                        </span>
                      )}
                      <Button variant="outline" size="sm" className="rounded-full" onClick={onClose}>
                        Hủy
                      </Button>
                      <Button size="sm" className="rounded-full" onClick={handleApply} disabled={isSaving}>
                        {isSaving ? "Đang áp dụng..." : "Áp dụng"}
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};

const MEMORY_LABELS: Record<string, string> = {
  business_type: "Loại hình:",
  province: "Địa bàn:",
  industry: "Ngành nghề:",
  frequent_topic: "Chủ đề:",
  preferred_answer: "Phong cách:",
};

const GeneralTab: React.FC<{
  settings: AdminSettings;
  memories: Record<string, string>;
  onClearMemory?: () => void;
  onClearHistory?: () => void;
  hasHistory?: boolean;
}> = ({ settings, memories, onClearMemory, onClearHistory, hasHistory = false }) => {
  const memoryEntries = Object.entries(memories);
  const [confirmClearHistory, setConfirmClearHistory] = useState(false);
  return (
    <div>
      <h3 className="mb-1 text-lg font-bold text-foreground">Chung</h3>
      <p className="mb-4 text-sm text-muted-foreground">Thông tin hệ thống và tham số truy hồi hiện hành.</p>

      <div className="divide-y divide-border rounded-2xl bg-secondary">
        <InfoRow label="Phiên bản" value={settings.version} />
        <InfoRow label="Kiến trúc" value={settings.architecture} />
        <InfoRow label="FastAPI Gateway" value={settings.fastapi_gateway} />
        <InfoRow label="Embedding Model" value={settings.embedding_model} />
        <InfoRow label="Reranker Model" value={settings.reranker_model} />
        <InfoRow label="Ngưỡng T_low / T_high (CRAG)" value={`${settings.t_low} / ${settings.t_high}`} />
      </div>

      <div className="mt-5 flex items-center justify-between">
        <h4 className="text-sm font-bold text-foreground">Dữ liệu của bạn</h4>
      </div>
      <div className="mt-2 divide-y divide-border rounded-2xl bg-secondary text-xs">
        <div className="flex items-center justify-between px-4 py-3">
          <span className="font-medium text-muted-foreground">Lịch sử trò chuyện</span>
          {hasHistory && onClearHistory ? (
            <button
              onClick={() => setConfirmClearHistory(true)}
              className="text-xs font-semibold text-destructive hover:underline"
            >
              Xóa tất cả
            </button>
          ) : (
            <span className="text-muted-foreground/60">Trống</span>
          )}
        </div>
        <div className="flex items-center justify-between px-4 py-3">
          <span className="font-medium text-muted-foreground">Hồ sơ doanh nghiệp</span>
          {memoryEntries.length > 0 && onClearMemory ? (
            <button
              onClick={onClearMemory}
              className="text-xs font-semibold text-destructive hover:underline"
            >
              Xóa hồ sơ
            </button>
          ) : (
            <span className="text-muted-foreground/60">Trống</span>
          )}
        </div>
      </div>

      <div className="mt-3 rounded-2xl bg-secondary p-3 text-xs">
        {memoryEntries.length === 0 ? (
          <p className="italic leading-relaxed text-muted-foreground">
            Chưa ghi nhận bối cảnh doanh nghiệp. Hãy nêu thông tin công ty trong câu hỏi để AI ghi nhớ.
          </p>
        ) : (
          <div className="space-y-1.5">
            {memoryEntries.map(([k, v]) => (
              <div key={k} className="flex items-start text-foreground">
                <span className="w-20 flex-shrink-0 font-semibold text-muted-foreground">
                  {MEMORY_LABELS[k] || k}
                </span>
                <span className="font-medium text-foreground">{v}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      <ConfirmDialog
        open={confirmClearHistory}
        onOpenChange={setConfirmClearHistory}
        title="Xóa toàn bộ lịch sử trò chuyện?"
        description="Tất cả cuộc trò chuyện và tin nhắn sẽ bị xóa vĩnh viễn khỏi máy chủ. Hành động này không thể hoàn tác."
        confirmLabel="Xóa tất cả"
        onConfirm={async () => {
          if (onClearHistory) await onClearHistory();
        }}
      />
    </div>
  );
};

const InfoRow: React.FC<{ label: string; value: string }> = ({ label, value }) => (
  <div className="flex items-center justify-between px-4 py-3 text-sm">
    <span className="font-medium text-muted-foreground">{label}</span>
    <span className="text-right font-mono text-xs font-semibold text-foreground">{value}</span>
  </div>
);
