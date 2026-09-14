/**
 * TypeScript Type Definitions for Legal CRAG Assistant Frontend.
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

export interface StreamNodeEvent {
  type: "node";
  node: string;
  stage: number;
}

export interface StreamTokenEvent {
  type: "token";
  text: string;
}

export interface StreamDoneEvent {
  type: "done";
  payload: ChatResponse;
}

export interface StreamErrorEvent {
  type: "error";
  message: string;
}

export type StreamEvent = StreamNodeEvent | StreamTokenEvent | StreamDoneEvent | StreamErrorEvent;

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  isStreaming?: boolean;
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
  source_url?: string;
}

export interface HistoryItem {
  id: number;
  session_id: string;
  question: string;
  answer: string;
  route: string;
  crag_action: string;
  created_at: string;
}

export interface AdminDocument {
  id: string;
  document_number: string;
  title: string;
  document_type?: string;
  issuing_authority?: string;
  issued_at?: string;
  effective_from?: string;
  effective_to?: string;
  status?: string;
  source_url?: string;
  retrieved_at?: string;
  provisions_count: number;
}

export interface AdminStats {
  total_documents: number;
  total_provisions: number;
  bm25_indexed: number;
  chroma_indexed: number;
}

export interface IngestResult {
  document_id: string;
  document_number: string;
  title: string;
  provisions_count: number;
  strips_count: number;
  corpus_total_provisions: number;
}

export interface DeleteResult {
  document_id: string;
  document_number: string;
  deleted_provisions: number;
  corpus_total_provisions: number;
}

export interface ClientMemoryProfile {
  client_id: string;
  memories: Record<string, string>;
  formatted_context: string;
}

export interface ModelSettings {
  provider: string;
  model: string;
  temperature: number;
}

export interface ProviderOption {
  provider: string;
  label: string;
  default_model: string;
  available_models: string[];
  configured: boolean;
}

export interface AdminSettings {
  version: string;
  architecture: string;
  fastapi_gateway: string;
  embedding_model: string;
  reranker_model: string;
  t_low: number;
  t_high: number;
  current: ModelSettings;
  providers: ProviderOption[];
}
