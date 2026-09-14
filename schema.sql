-- schema.sql: Legal CRAG Assistant Database Schema
-- Combines Legal Knowledge Base (Ch 3) and Session & Client Memory (Ch 5)

PRAGMA foreign_keys = ON;

-- 1. Legal Documents Catalog
CREATE TABLE IF NOT EXISTS legal_documents (
    id TEXT PRIMARY KEY,
    document_number TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    document_type TEXT,
    issuing_authority TEXT,
    issued_at DATE,
    effective_from DATE,
    effective_to DATE,
    status TEXT, -- 'effective', 'expired', 'partially_expired'
    source_url TEXT NOT NULL,
    retrieved_at TEXT
);

-- 2. Provisions (Hierarchy: Chapter -> Article -> Clause -> Point)
CREATE TABLE IF NOT EXISTS provisions (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    chapter TEXT,
    article TEXT,
    clause TEXT,
    point TEXT,
    heading TEXT,
    text TEXT NOT NULL,
    FOREIGN KEY(document_id) REFERENCES legal_documents(id) ON DELETE CASCADE
);

-- 3. Provision Versions over Time
CREATE TABLE IF NOT EXISTS provision_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provision_id TEXT NOT NULL,
    valid_from DATE,
    valid_to DATE,
    text TEXT NOT NULL,
    source_document_id TEXT,
    FOREIGN KEY(provision_id) REFERENCES provisions(id) ON DELETE CASCADE
);

-- 4. Legal Relations (Amends, Supplements, Replaces, Repeals, Guides)
CREATE TABLE IF NOT EXISTS legal_relations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_document_id TEXT NOT NULL,
    target_document_id TEXT NOT NULL,
    source_provision_id TEXT,
    target_provision_id TEXT,
    relation_type TEXT NOT NULL, -- 'amends', 'supplements', 'replaces', 'repeals', 'guides'
    note TEXT,
    FOREIGN KEY(source_document_id) REFERENCES legal_documents(id) ON DELETE CASCADE,
    FOREIGN KEY(target_document_id) REFERENCES legal_documents(id) ON DELETE CASCADE
);

-- 5. Clients (Anonymous Browser / Organization Identity)
CREATE TABLE IF NOT EXISTS clients (
    id TEXT PRIMARY KEY,
    memory_enabled INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- 6. Chat Sessions
CREATE TABLE IF NOT EXISTS chat_sessions (
    id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    started_at TEXT DEFAULT CURRENT_TIMESTAMP,
    last_active_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE
);

-- 7. Query Logs (Episodic Memory / Audit Trail)
CREATE TABLE IF NOT EXISTS query_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    question TEXT NOT NULL,
    answer TEXT,
    route TEXT,
    crag_action TEXT,
    source_type TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE,
    FOREIGN KEY(session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
);

-- 8. Client Memories (Semantic Memory - Strictly Governed by Allow-list)
CREATE TABLE IF NOT EXISTS client_memories (
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
CREATE INDEX IF NOT EXISTS idx_doc_number ON legal_documents(document_number);
CREATE INDEX IF NOT EXISTS idx_doc_status ON legal_documents(status);
CREATE INDEX IF NOT EXISTS idx_provision_doc ON provisions(document_id);
CREATE INDEX IF NOT EXISTS idx_relation_target ON legal_relations(target_document_id);
CREATE INDEX IF NOT EXISTS idx_query_logs_client ON query_logs(client_id);
CREATE INDEX IF NOT EXISTS idx_query_logs_session ON query_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_client_memories_client ON client_memories(client_id);
