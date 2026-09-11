/**
 * API Client communicating with FastAPI Backend Gateway.
 */
import { ChatResponse, ClientMemoryProfile, LegalDocument } from "./types";

export function getApiBase(): string {
  if (typeof window !== "undefined" && (window.location.port === "8000" || window.location.port === "")) {
    return window.location.origin;
  }
  return "http://localhost:8000";
}
export async function sendChatMessage(params: {
  query: string;
  clientId: string;
  sessionId: string;
  asOfDate?: string;
}): Promise<ChatResponse> {
  const apiBase = getApiBase();
  const res = await fetch(`${apiBase}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      query: params.query,
      client_id: params.clientId,
      session_id: params.sessionId,
      as_of_date: params.asOfDate || "2026-01-01",
    }),
  });

  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(`API Error (${res.status}): ${errorText}`);
  }

  return res.json();
}

export async function fetchDocuments(): Promise<LegalDocument[]> {
  const apiBase = getApiBase();
  try {
    const res = await fetch(`${apiBase}/api/documents`);
    if (!res.ok) return [];
    return res.json();
  } catch (e) {
    console.error("Failed to fetch documents", e);
    return [];
  }
}

export async function fetchClientMemory(clientId: string): Promise<ClientMemoryProfile | null> {
  const apiBase = getApiBase();
  try {
    const res = await fetch(`${apiBase}/api/memory/${clientId}`);
    if (!res.ok) return null;
    return res.json();
  } catch (e) {
    console.error("Failed to fetch memory", e);
    return null;
  }
}

export async function clearClientMemory(clientId: string): Promise<boolean> {
  const apiBase = getApiBase();
  try {
    const res = await fetch(`${apiBase}/api/memory/${clientId}`, {
      method: "DELETE",
    });
    return res.ok;
  } catch (e) {
    console.error("Failed to clear memory", e);
    return false;
  }
}
