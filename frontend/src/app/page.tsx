"use client";

import React, { useEffect, useState } from "react";
import {
  clearClientMemory,
  fetchClientMemory,
  fetchDocuments,
  sendChatMessage,
} from "../lib/api";
import { CitationReport, EvidenceItem, LegalDocument, Message } from "../lib/types";
import { ChatInput } from "../components/ChatInput";
import { ChatStream } from "../components/ChatStream";
import { Navbar } from "../components/Navbar";
import { Sidebar } from "../components/Sidebar";
import { TraceDrawer } from "../components/TraceDrawer";

export default function HomePage() {
  const [clientId, setClientId] = useState<string>("");
  const [sessionId, setSessionId] = useState<string>("");
  const [asOfDate, setAsOfDate] = useState<string>("2026-01-01");
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isTraceOpen, setIsTraceOpen] = useState<boolean>(true);

  // Data states
  const [documents, setDocuments] = useState<LegalDocument[]>([]);
  const [memories, setMemories] = useState<Record<string, string>>({});
  const [currentCitationReport, setCurrentCitationReport] = useState<CitationReport | null>(null);
  // Current Turn Trace info
  const [currentRoute, setCurrentRoute] = useState<string>("rag");
  const [currentAction, setCurrentAction] = useState<string>("CORRECT");
  const [currentEvidence, setCurrentEvidence] = useState<EvidenceItem[]>([]);

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
    const [docs, memData] = await Promise.all([
      fetchDocuments(),
      fetchClientMemory(cid),
    ]);
    setDocuments(docs);
    if (memData?.memories) {
      setMemories(memData.memories);
    }
  };

  const handleSendMessage = async (query: string) => {
    if (!query.trim() || isLoading) return;

    const userMessage: Message = {
      id: "usr_" + Date.now(),
      role: "user",
      content: query,
      timestamp: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);

    try {
      const response = await sendChatMessage({
        query,
        clientId,
        sessionId,
        asOfDate,
      });

      // Update Trace States
      setCurrentRoute(response.route);
      setCurrentAction(response.crag_action);
      setCurrentEvidence(response.evidence || []);
      setCurrentCitationReport(response.citation_report);

      const assistantMessage: Message = {
        id: "ast_" + Date.now(),
        role: "assistant",
        content: response.generation.answer,
        timestamp: new Date().toISOString(),
        citationReport: response.citation_report,
        trace: {
          route: response.route,
          cragAction: response.crag_action,
          evidence: response.evidence || [],
        },
      };

      setMessages((prev) => [...prev, assistantMessage]);

      // Refresh memory profile after turn
      if (clientId) {
        const memData = await fetchClientMemory(clientId);
        if (memData?.memories) {
          setMemories(memData.memories);
        }
      }
    } catch (err: unknown) {
      const errorMsg = err instanceof Error ? err.message : String(err);
      const errorMessage: Message = {
        id: "err_" + Date.now(),
        role: "assistant",
        content: `⚠️ Đã xảy ra lỗi khi xử lý yêu cầu: ${errorMsg}`,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleNewChat = () => {
    setSessionId("session_" + Math.random().toString(36).substring(2, 11));
    setMessages([]);
    setCurrentEvidence([]);
    setCurrentCitationReport(null);
  };

  const handleClearMemory = async () => {
    if (clientId) {
      await clearClientMemory(clientId);
      setMemories({});
    }
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-slate-50">
      {/* LEFT SIDEBAR */}
      <Sidebar
        documents={documents}
        memories={memories}
        onNewChat={handleNewChat}
        onClearMemory={handleClearMemory}
      />

      {/* CENTER CHAT WORKSPACE */}
      <main className="flex-1 flex flex-col h-screen min-w-0 overflow-hidden relative">
        <Navbar
          asOfDate={asOfDate}
          onDateChange={setAsOfDate}
          isTraceOpen={isTraceOpen}
          onToggleTrace={() => setIsTraceOpen(!isTraceOpen)}
        />

        <ChatStream
          messages={messages}
          isLoading={isLoading}
          onSelectPrompt={handleSendMessage}
        />

        <ChatInput onSendMessage={handleSendMessage} isLoading={isLoading} />
      </main>

      {/* RIGHT EXECUTION TRACE DRAWER (Hermes / DeepSeek Style) */}
      <TraceDrawer
        isOpen={isTraceOpen}
        onClose={() => setIsTraceOpen(false)}
        route={currentRoute}
        cragAction={currentAction}
        citationReport={currentCitationReport}
        evidence={currentEvidence}
      />
    </div>
  );
}
