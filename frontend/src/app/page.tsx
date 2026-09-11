"use client";

import React, { useEffect, useState } from "react";
import {
  clearClientMemory,
  fetchAdminSettings,
  fetchClientMemory,
  fetchDocuments,
  fetchHistory,
  streamChatMessage,
} from "../lib/api";
import { ChatResponse, HistoryItem, LegalDocument, Message, ModelSettings } from "../lib/types";
import { summarizeHistoryBySession } from "../lib/history";
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";
import { AppSidebar } from "../components/chat/app-sidebar";
import { ChatHeader } from "../components/chat/chat-header";
import { WelcomeHero } from "../components/chat/welcome-hero";
import { MessageList } from "../components/chat/message-list";
import { PromptComposer } from "../components/chat/prompt-composer";
import { SettingsModal } from "../components/SettingsModal";

export default function HomePage() {
  const [clientId, setClientId] = useState<string>("");
  const [sessionId, setSessionId] = useState<string>("");
  const [asOfDate, setAsOfDate] = useState<string>("2026-01-01");
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  // Current real pipeline stage (0-3) from SSE `node` events; null once the
  // answer starts streaming (or there is no active turn).
  const [liveStage, setLiveStage] = useState<number | null>(null);
  const [isSettingsOpen, setIsSettingsOpen] = useState<boolean>(false);

  // Data states
  const [documents, setDocuments] = useState<LegalDocument[]>([]);
  const [memories, setMemories] = useState<Record<string, string>>({});
  const [historyItems, setHistoryItems] = useState<HistoryItem[]>([]);
  const [modelLabel, setModelLabel] = useState<string>("Model");

  // Initialize Client ID and Session ID on mount
  useEffect(() => {
    let cid = localStorage.getItem("legal_crag_client_id");
    if (!cid) {
      cid = "client_" + Math.random().toString(36).substring(2, 11);
      localStorage.setItem("legal_crag_client_id", cid);
    }
    setClientId(cid);
    setSessionId("session_" + Math.random().toString(36).substring(2, 11));

    // Load initial data
    loadInitialData(cid);
  }, []);

  const loadInitialData = async (cid: string) => {
    const [docs, memData, hist, settings] = await Promise.all([
      fetchDocuments(),
      fetchClientMemory(cid),
      fetchHistory(cid),
      fetchAdminSettings(),
    ]);
    setDocuments(docs);
    if (memData?.memories) {
      setMemories(memData.memories);
    }
    setHistoryItems(hist);
    if (settings?.current?.model) {
      setModelLabel(settings.current.model);
    }
  };

  const refreshMemoryAndHistory = async () => {
    if (!clientId) return;
    const [memData, hist] = await Promise.all([
      fetchClientMemory(clientId),
      fetchHistory(clientId),
    ]);
    if (memData?.memories) {
      setMemories(memData.memories);
    }
    setHistoryItems(hist);
  };

  const handleSendMessage = async (query: string) => {
    if (!query.trim() || isLoading) return;

    const userMessage: Message = {
      id: "usr_" + Date.now(),
      role: "user",
      content: query,
      timestamp: new Date().toISOString(),
    };

    const assistantId = "ast_" + Date.now();
    let hasToken = false;

    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);
    setLiveStage(0);

    await streamChatMessage(
      { query, clientId, sessionId, asOfDate },
      {
        onNode: (_node, stage) => {
          if (!hasToken) setLiveStage(stage);
        },
        onToken: (text) => {
          if (!hasToken) {
            hasToken = true;
            setLiveStage(null);
            setMessages((prev) => [
              ...prev,
              {
                id: assistantId,
                role: "assistant",
                content: text,
                timestamp: new Date().toISOString(),
                isStreaming: true,
              },
            ]);
          } else {
            setMessages((prev) =>
              prev.map((m) => (m.id === assistantId ? { ...m, content: m.content + text } : m))
            );
          }
        },
        onDone: async (payload: ChatResponse) => {
          setLiveStage(null);
          const finalized: Message = {
            id: assistantId,
            role: "assistant",
            content: payload.generation.answer,
            timestamp: new Date().toISOString(),
            isStreaming: false,
            citationReport: payload.citation_report,
            trace: {
              route: payload.route,
              cragAction: payload.crag_action,
              evidence: payload.evidence || [],
            },
          };
          setMessages((prev) =>
            hasToken
              ? prev.map((m) => (m.id === assistantId ? finalized : m))
              : [...prev, finalized]
          );
          setIsLoading(false);
          await refreshMemoryAndHistory();
        },
        onError: (message) => {
          setLiveStage(null);
          const errorMessage: Message = {
            id: "err_" + Date.now(),
            role: "assistant",
            content: `⚠️ Đã xảy ra lỗi khi xử lý yêu cầu: ${message}`,
            timestamp: new Date().toISOString(),
          };
          setMessages((prev) =>
            hasToken ? [...prev.filter((m) => m.id !== assistantId), errorMessage] : [...prev, errorMessage]
          );
          setIsLoading(false);
        },
      }
    );
  };

  const handleNewChat = () => {
    setSessionId("session_" + Math.random().toString(36).substring(2, 11));
    setMessages([]);
  };

  const handleSelectConversation = async (targetSessionId: string) => {
    if (!clientId || targetSessionId === sessionId) return;
    const turns = await fetchHistory(clientId, { sessionId: targetSessionId, limit: 200 });
    if (turns.length === 0) return;

    const reconstructed: Message[] = [];
    for (const turn of turns) {
      reconstructed.push({
        id: `usr_${turn.id}`,
        role: "user",
        content: turn.question,
        timestamp: turn.created_at,
      });
      reconstructed.push({
        id: `ast_${turn.id}`,
        role: "assistant",
        content: turn.answer,
        timestamp: turn.created_at,
        trace: { route: turn.route, cragAction: turn.crag_action, evidence: [] },
      });
    }

    setSessionId(targetSessionId);
    setMessages(reconstructed);
  };

  const handleClearMemory = async () => {
    if (clientId) {
      await clearClientMemory(clientId);
      setMemories({});
    }
  };

  const conversations = summarizeHistoryBySession(historyItems);
  const memoryCount = Object.keys(memories).length;

  const composerProps = {
    isLoading,
    asOfDate,
    onAsOfDateChange: setAsOfDate,
    modelLabel,
    onOpenModelSettings: () => setIsSettingsOpen(true),
  };

  return (
    <>
      <SidebarProvider>
        <AppSidebar
          clientId={clientId}
          documents={documents}
          conversations={conversations}
          activeSessionId={sessionId}
          memoryCount={memoryCount}
          onNewChat={handleNewChat}
          onSelectConversation={handleSelectConversation}
          onSelectPrompt={handleSendMessage}
          onOpenSettings={() => setIsSettingsOpen(true)}
        />

        <SidebarInset className="flex h-screen flex-col overflow-hidden bg-background">
          <ChatHeader />

          {messages.length === 0 ? (
            <WelcomeHero onSend={handleSendMessage} {...composerProps} />
          ) : (
            <>
              <MessageList messages={messages} isLoading={isLoading} liveStage={liveStage} />
              <div className="mx-auto w-full max-w-3xl flex-shrink-0 px-4 pb-4">
                <PromptComposer onSend={handleSendMessage} {...composerProps} />
                <p className="mt-2 text-center text-[11px] text-muted-foreground">
                  Mọi câu trả lời đều được kiểm định xác thực từ kho văn bản quy phạm pháp luật nội
                  bộ hoặc cổng thông tin chính thống.
                </p>
              </div>
            </>
          )}
        </SidebarInset>
      </SidebarProvider>

      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        onModelChange={(model: ModelSettings) => setModelLabel(model.model)}
        memories={memories}
        onClearMemory={handleClearMemory}
      />
    </>
  );
}
