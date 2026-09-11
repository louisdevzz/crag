/**
 * Derives a topical corpus category (matching the on-disk `data/<category>/` layout)
 * from a document's `source_url`, and groups documents by that category for the
 * sidebar's knowledge-base catalog.
 */
import { LegalDocument } from "./types";

const FALLBACK_CATEGORY = "Khác";

export function deriveCategory(sourceUrl?: string): string {
  if (!sourceUrl) return FALLBACK_CATEGORY;
  const match = sourceUrl.match(/\/data\/([^/]+)\//);
  if (match?.[1]) {
    try {
      return decodeURIComponent(match[1]);
    } catch {
      return match[1];
    }
  }
  return FALLBACK_CATEGORY;
}

export interface DocumentCategoryGroup {
  category: string;
  documents: LegalDocument[];
}

export function groupDocumentsByCategory(documents: LegalDocument[]): DocumentCategoryGroup[] {
  const groups = new Map<string, LegalDocument[]>();
  for (const doc of documents) {
    const category = deriveCategory(doc.source_url);
    const bucket = groups.get(category) || [];
    bucket.push(doc);
    groups.set(category, bucket);
  }
  return Array.from(groups.entries())
    .map(([category, docs]) => ({ category, documents: docs }))
    .sort((a, b) => b.documents.length - a.documents.length);
}
