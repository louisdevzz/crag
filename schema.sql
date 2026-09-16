-- schema.sql: Legal CRAG Assistant Database Schema (Chat + Admin architecture)
-- Two domains sharing one SQLite file:
--   1. Corpus / Ingestion (Admin):  documents, document_chunks, ingestion_jobs, legal_relations
--   2. Session / Memory   (Chat):   clients, sessions, messages, memories

PRAGMA foreign_keys = ON;

-- 1. Documents: one row per uploaded/ingested legal document.
--    status: UPLOADED | PROCESSING | READY | FAILED (ingestion lifecycle)
--    legal_status: effective | expired | partially_expired (legal effectiveness,
--    independent of ingestion status — extracted from document text, defaults to 'effective')
--    Only documents with status = 'READY' are visible to the CRAG retrieval tools.
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    document_number TEXT,
    title TEXT NOT NULL,
    document_type TEXT,
    issuing_authority TEXT,
    issued_at DATE,
    effective_from DATE,
    effective_to DATE,
    status TEXT NOT NULL DEFAULT 'UPLOADED',
    legal_status TEXT NOT NULL DEFAULT 'effective',
    source_url TEXT,
    file_path TEXT,
    file_type TEXT,
    content_hash TEXT,
    page_count INTEGER DEFAULT 0,
    chunk_count INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- 2. Document Chunks: the indexed retrieval unit (Chương -> Điều -> Khoản), one row
--    per legal-aware chunk produced by the CHUNKING stage of the ingestion pipeline.
CREATE TABLE IF NOT EXISTS document_chunks (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    chapter TEXT,
    article TEXT,
    clause TEXT,
    point TEXT,
    heading TEXT,
    page_start INTEGER,
    page_end INTEGER,
    content TEXT NOT NULL,
    token_count INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
);

-- 3. Legal Relations (Amends, Supplements, Replaces, Repeals, Guides) between documents.
CREATE TABLE IF NOT EXISTS legal_relations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_document_id TEXT NOT NULL,
    target_document_id TEXT NOT NULL,
    source_chunk_id TEXT,
    target_chunk_id TEXT,
    relation_type TEXT NOT NULL, -- 'amends', 'supplements', 'replaces', 'repeals', 'guides'
    note TEXT,
    FOREIGN KEY(source_document_id) REFERENCES documents(id) ON DELETE CASCADE,
    FOREIGN KEY(target_document_id) REFERENCES documents(id) ON DELETE CASCADE
);

-- 4. Ingestion Jobs: one row per upload, tracks the staged async ingestion pipeline.
--    stage: PARSING | OCR | STRUCTURING | CHUNKING | EMBEDDING | INDEXING | DONE
CREATE TABLE IF NOT EXISTS ingestion_jobs (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    stage TEXT NOT NULL DEFAULT 'PARSING',
    progress REAL NOT NULL DEFAULT 0.0,
    error_message TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    finished_at TEXT,
    FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
);

-- 5. Clients: anonymous browser/organization identity, owner of sessions and memories.
CREATE TABLE IF NOT EXISTS clients (
    id TEXT PRIMARY KEY,
    memory_enabled INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- 6. Chat Sessions.
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    title TEXT,
    started_at TEXT DEFAULT CURRENT_TIMESTAMP,
    last_active_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE
);

-- 7. Messages: canonical short-term conversational memory (Context Manager reads this
--    to assemble multi-turn history; replaces the old write-only `query_logs` audit table).
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    client_id TEXT NOT NULL,
    role TEXT NOT NULL, -- 'user' | 'assistant'
    content TEXT NOT NULL,
    route TEXT,
    crag_action TEXT,
    source_type TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE,
    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE
);

-- 8. Memories: long-term semantic profile memory, strictly governed by the allow-list
--    in config.ALLOWED_MEMORY_KEYS. Never used as legal grounding, only entity resolution.
CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id TEXT NOT NULL,
    memory_key TEXT NOT NULL,
    memory_value TEXT NOT NULL,
    confidence REAL DEFAULT 1.0,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(client_id, memory_key),
    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE
);

-- Indexes for Fast Query Execution
CREATE INDEX IF NOT EXISTS idx_doc_number ON documents(document_number);
CREATE INDEX IF NOT EXISTS idx_doc_status ON documents(status);
CREATE INDEX IF NOT EXISTS idx_doc_content_hash ON documents(content_hash);
CREATE INDEX IF NOT EXISTS idx_chunk_document ON document_chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_relation_target ON legal_relations(target_document_id);
CREATE INDEX IF NOT EXISTS idx_job_document ON ingestion_jobs(document_id);
CREATE INDEX IF NOT EXISTS idx_sessions_client ON sessions(client_id);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
CREATE INDEX IF NOT EXISTS idx_messages_client ON messages(client_id);
CREATE INDEX IF NOT EXISTS idx_memories_client ON memories(client_id);
