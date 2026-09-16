"""Admin ingestion pipeline: upload -> parse/OCR -> structure -> chunk -> embed -> index.

Every stage updates an `ingestion_jobs` row so the Admin UI can show live progress,
and every document only becomes visible to the CRAG retrieval tools once its
`documents.status` flips to `READY` (see `ingestion.indexer`).
"""
