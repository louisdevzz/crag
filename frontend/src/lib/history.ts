/**
 * Groups the flat episodic query log (`/api/history/{client_id}`) into per-session
 * conversation summaries, then buckets those conversations into day-relative
 * labels ("Hôm nay", "Hôm qua", ...) for the sidebar's chat history list.
 */
import { HistoryItem } from "./types";

export interface ConversationSummary {
  sessionId: string;
  title: string;
  lastRoute: string;
  lastCragAction: string;
  updatedAt: string;
  turnCount: number;
}

export function summarizeHistoryBySession(items: HistoryItem[]): ConversationSummary[] {
  const bySession = new Map<string, HistoryItem[]>();
  for (const item of items) {
    const bucket = bySession.get(item.session_id) || [];
    bucket.push(item);
    bySession.set(item.session_id, bucket);
  }

  const summaries: ConversationSummary[] = [];
  for (const [sessionId, turns] of Array.from(bySession)) {
    const ordered = [...turns].sort((a, b) => a.id - b.id);
    const first = ordered[0];
    const last = ordered[ordered.length - 1];
    summaries.push({
      sessionId,
      title: first.question,
      lastRoute: last.route,
      lastCragAction: last.crag_action,
      updatedAt: last.created_at,
      turnCount: ordered.length,
    });
  }

  return summaries.sort(
    (a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
  );
}

const DAY_MS = 24 * 60 * 60 * 1000;

export interface ConversationDayGroup {
  label: string;
  conversations: ConversationSummary[];
}

export function groupConversationsByDay(conversations: ConversationSummary[]): ConversationDayGroup[] {
  const startOfToday = new Date();
  startOfToday.setHours(0, 0, 0, 0);

  const buckets: Record<string, ConversationSummary[]> = {
    "Hôm nay": [],
    "Hôm qua": [],
    "7 ngày qua": [],
    "Trước đó": [],
  };

  for (const conversation of conversations) {
    const dayDiff = Math.floor(
      (startOfToday.getTime() - new Date(conversation.updatedAt).setHours(0, 0, 0, 0)) / DAY_MS
    );
    if (dayDiff <= 0) buckets["Hôm nay"].push(conversation);
    else if (dayDiff === 1) buckets["Hôm qua"].push(conversation);
    else if (dayDiff <= 7) buckets["7 ngày qua"].push(conversation);
    else buckets["Trước đó"].push(conversation);
  }

  return Object.entries(buckets)
    .filter(([, list]) => list.length > 0)
    .map(([label, list]) => ({ label, conversations: list }));
}
