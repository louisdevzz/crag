/**
 * API Client communicating with FastAPI Backend Gateway.
 */
import {
  AdminDocumentDetail,
  AdminDocumentSummary,
  AdminSettings,
  AdminStats,
  ChatResponse,
  ChunkItem,
  ClientMemoryProfile,
  DeleteResult,
  HistoryItem,
  LegalDocument,
  ModelSettings,
  StreamEvent,
  UploadResult,
} from "./types";

export function getApiBase(): string {
  if (typeof window !== "undefined" && (window.location.port === "8000" || window.location.port === "")) {
    return window.location.origin;
  }
  return "http://localhost:8000";
}
export interface ChatStreamHandlers {
  onNode?: (node: string, stage: number) => void;
  onToken?: (text: string) => void;
  onDone?: (payload: ChatResponse) => void;
  onError?: (message: string) => void;
}

export async function streamChatMessage(
  params: { query: string; clientId: string; sessionId: string; asOfDate?: string },
  handlers: ChatStreamHandlers
): Promise<void> {
  const apiBase = getApiBase();
  let res: Response;
  try {
    res = await fetch(`${apiBase}/api/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query: params.query,
        client_id: params.clientId,
        session_id: params.sessionId,
        as_of_date: params.asOfDate || "2026-01-01",
      }),
    });
  } catch (e: unknown) {
    handlers.onError?.(e instanceof Error ? e.message : String(e));
    return;
  }

  if (!res.ok || !res.body) {
    const errorText = await res.text().catch(() => res.statusText);
    handlers.onError?.(`API Error (${res.status}): ${errorText}`);
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let sepIndex = buffer.indexOf("\n\n");
    while (sepIndex !== -1) {
      const frame = buffer.slice(0, sepIndex);
      buffer = buffer.slice(sepIndex + 2);
      const dataLine = frame.split("\n").find((l) => l.startsWith("data: "));
      sepIndex = buffer.indexOf("\n\n");
      if (!dataLine) continue;

      let event: StreamEvent;
      try {
        event = JSON.parse(dataLine.slice(6));
      } catch {
        continue;
      }

      if (event.type === "node") handlers.onNode?.(event.node, event.stage);
      else if (event.type === "token") handlers.onToken?.(event.text);
      else if (event.type === "done") handlers.onDone?.(event.payload);
      else if (event.type === "error") handlers.onError?.(event.message);
    }
  }
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

export async function fetchHistory(
  clientId: string,
  params?: { sessionId?: string; limit?: number }
): Promise<HistoryItem[]> {
  const apiBase = getApiBase();
  try {
    const query = new URLSearchParams();
    if (params?.sessionId) query.set("session_id", params.sessionId);
    query.set("limit", String(params?.limit ?? 50));
    const res = await fetch(`${apiBase}/api/history/${clientId}?${query.toString()}`);
    if (!res.ok) return [];
    return res.json();
  } catch (e) {
    console.error("Failed to fetch history", e);
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

export async function fetchAdminDocuments(): Promise<AdminDocumentSummary[]> {
  const apiBase = getApiBase();
  try {
    const res = await fetch(`${apiBase}/api/admin/documents`);
    if (!res.ok) return [];
    return res.json();
  } catch (e) {
    console.error("Failed to fetch admin documents", e);
    return [];
  }
}

export async function fetchAdminDocumentDetail(documentId: string): Promise<AdminDocumentDetail | null> {
  const apiBase = getApiBase();
  try {
    const res = await fetch(`${apiBase}/api/admin/documents/${encodeURIComponent(documentId)}`);
    if (!res.ok) return null;
    return res.json();
  } catch (e) {
    console.error("Failed to fetch admin document detail", e);
    return null;
  }
}

export async function fetchAdminDocumentChunks(documentId: string): Promise<ChunkItem[]> {
  const apiBase = getApiBase();
  try {
    const res = await fetch(`${apiBase}/api/admin/documents/${encodeURIComponent(documentId)}/chunks`);
    if (!res.ok) return [];
    return res.json();
  } catch (e) {
    console.error("Failed to fetch admin document chunks", e);
    return [];
  }
}

export async function fetchAdminStats(): Promise<AdminStats | null> {
  const apiBase = getApiBase();
  try {
    const res = await fetch(`${apiBase}/api/admin/stats`);
    if (!res.ok) return null;
    return res.json();
  } catch (e) {
    console.error("Failed to fetch admin stats", e);
    return null;
  }
}

export async function uploadAdminDocument(file: File, replace?: boolean): Promise<UploadResult> {
  const apiBase = getApiBase();
  const formData = new FormData();
  formData.append("file", file);

  const url = `${apiBase}/api/admin/documents/upload${replace ? "?replace=true" : ""}`;
  const res = await fetch(url, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const errorBody = await res.json().catch(() => null);
    throw new Error(errorBody?.detail || `Tải lên thất bại (${res.status})`);
  }

  return res.json();
}

export async function deleteAdminDocument(documentId: string): Promise<DeleteResult> {
  const apiBase = getApiBase();
  const res = await fetch(`${apiBase}/api/admin/documents/${encodeURIComponent(documentId)}`, {
    method: "DELETE",
  });

  if (!res.ok) {
    const errorBody = await res.json().catch(() => null);
    throw new Error(errorBody?.detail || `Xóa thất bại (${res.status})`);
  }

  return res.json();
}

export async function fetchAdminSettings(): Promise<AdminSettings | null> {
  const apiBase = getApiBase();
  try {
    const res = await fetch(`${apiBase}/api/admin/settings`);
    if (!res.ok) return null;
    return res.json();
  } catch (e) {
    console.error("Failed to fetch admin settings", e);
    return null;
  }
}

export async function updateAdminModel(params: {
  provider: string;
  model: string;
  temperature?: number;
}): Promise<ModelSettings> {
  const apiBase = getApiBase();
  const res = await fetch(`${apiBase}/api/admin/settings/model`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });

  if (!res.ok) {
    const errorBody = await res.json().catch(() => null);
    throw new Error(errorBody?.detail || `Cập nhật thất bại (${res.status})`);
  }

  return res.json();
}
