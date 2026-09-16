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
  route: "rag" | "general" | string;
  crag_action: "CORRECT" | "AMBIGUOUS" | "INCORRECT" | string;
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
  claims?: ClaimItem[];
  durationMs?: number;
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

export interface AdminDocumentSummary {
  id: string;
  filename: string;
  document_number: string | null;
  title: string;
  document_type: string | null;
  issuing_authority: string | null;
  issued_at: string | null;
  effective_from: string | null;
  effective_to: string | null;
  status: "UPLOADED" | "PROCESSING" | "READY" | "FAILED";
  page_count: number;
  chunk_count: number;
  stage: string | null;
  error_message: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface IngestionJobInfo {
  id: string;
  stage: "PARSING" | "OCR" | "STRUCTURING" | "CHUNKING" | "EMBEDDING" | "INDEXING" | "DONE" | "FAILED";
  progress: number;
  error_message: string | null;
}

export interface AdminDocumentDetail extends AdminDocumentSummary {
  job: IngestionJobInfo | null;
}

export interface ChunkItem {
  id: string;
  chunk_index: number;
  chapter: string | null;
  article: string | null;
  clause: string | null;
  point: string | null;
  heading: string | null;
  page_start: number | null;
  page_end: number | null;
  content: string;
  token_count: number | null;
}

export interface AdminStats {
  total_documents: number;
  ready: number;
  processing: number;
  failed: number;
}

export interface UploadResult {
  document_id: string;
  status: string;
  job_id: string;
}

export interface DeleteResult {
  document_id: string;
  filename: string;
  deleted_chunks: number;
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
