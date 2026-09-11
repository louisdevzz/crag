/**
 * TypeScript Type Definitions for Legal CRAG Assistant V3 Frontend.
 */

export interface ClaimItem {
  text: string;
  source_ids: string[];
}

export interface GenerationOutput {
  answer: string;
  claims: ClaimItem[];
  abstain: boolean;
}

export interface CitationReport {
  ok: boolean;
  errors: string[];
  valid_citations: string[];
  citation_accuracy: number;
  citation_coverage: number;
}

export interface EvidenceItem {
  strip_id?: string;
  locator?: string;
  evidence_id?: string;
  document_id?: string;
  document_number?: string;
  document_title?: string;
  heading?: string;
  text?: string;
  score?: number;
  source_priority?: number;
  retrieval_source?: string;
}

export interface ChatResponse {
  client_id: string;
  session_id: string;
  query: string;
  route: "database" | "rag" | "general" | string;
  crag_action: "CORRECT" | "AMBIGUOUS" | "INCORRECT" | "DATABASE" | string;
  generation: GenerationOutput;
  citation_report: CitationReport;
  evidence_count: number;
  evidence: EvidenceItem[];
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  citationReport?: CitationReport;
  trace?: {
    route: string;
    cragAction: string;
    evidence: EvidenceItem[];
  };
}

export interface LegalDocument {
  id: string;
  document_number: string;
  title: string;
  document_type: string;
  issuing_authority: string;
  effective_from?: string;
  status: string;
}

export interface ClientMemoryProfile {
  client_id: string;
  memories: Record<string, string>;
  formatted_context: string;
}
