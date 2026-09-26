-- Default standalone schema. Generated from the actual runtime table definitions.

-- This SQL was generated, not executed against PostgreSQL in this build.

CREATE SCHEMA IF NOT EXISTS aidlex_mcp;

REVOKE ALL ON SCHEMA aidlex_mcp FROM PUBLIC;

CREATE TABLE IF NOT EXISTS aidlex_mcp.audit_events (
	id VARCHAR(40) NOT NULL, 
	owner VARCHAR(128), 
	case_id VARCHAR(128), 
	action VARCHAR(80), 
	metadata JSON, 
	created_at VARCHAR(40), 
	PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS ix_aidlex_mcp_audit_events_owner ON aidlex_mcp.audit_events (owner);

CREATE INDEX IF NOT EXISTS ix_aidlex_mcp_audit_events_case_id ON aidlex_mcp.audit_events (case_id);

CREATE TABLE IF NOT EXISTS aidlex_mcp.case_memory (
	owner VARCHAR(128) NOT NULL, 
	case_id VARCHAR(128) NOT NULL, 
	revision INTEGER NOT NULL, 
	payload JSON, 
	updated_at VARCHAR(40), 
	PRIMARY KEY (owner, case_id)
);

CREATE TABLE IF NOT EXISTS aidlex_mcp.cases (
	owner VARCHAR(128) NOT NULL, 
	case_id VARCHAR(128) NOT NULL, 
	created_at VARCHAR(40), 
	title TEXT, 
	PRIMARY KEY (owner, case_id)
);

CREATE TABLE IF NOT EXISTS aidlex_mcp.chunks (
	id VARCHAR(40) NOT NULL, 
	owner VARCHAR(128), 
	case_id VARCHAR(128), 
	kind VARCHAR(30), 
	source_id VARCHAR(40), 
	title TEXT, 
	text TEXT, 
	page_number INTEGER, 
	start INTEGER, 
	"end" INTEGER, 
	metadata JSON, 
	embedding JSON, 
	embedding_model VARCHAR(100), 
	PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS ix_aidlex_mcp_chunks_case_id ON aidlex_mcp.chunks (case_id);

CREATE INDEX IF NOT EXISTS ix_aidlex_mcp_chunks_owner ON aidlex_mcp.chunks (owner);

CREATE INDEX IF NOT EXISTS ix_aidlex_mcp_chunks_source_id ON aidlex_mcp.chunks (source_id);

CREATE INDEX IF NOT EXISTS ix_aidlex_mcp_chunks_kind ON aidlex_mcp.chunks (kind);

CREATE TABLE IF NOT EXISTS aidlex_mcp.documents (
	id VARCHAR(40) NOT NULL, 
	owner VARCHAR(128) NOT NULL, 
	case_id VARCHAR(128) NOT NULL, 
	title TEXT, 
	pages JSON, 
	metadata JSON, 
	content_hash VARCHAR(64), 
	created_at VARCHAR(40), 
	PRIMARY KEY (id), 
	CONSTRAINT uq_doc_content UNIQUE (owner, case_id, content_hash)
);

CREATE INDEX IF NOT EXISTS ix_aidlex_mcp_documents_owner ON aidlex_mcp.documents (owner);

CREATE INDEX IF NOT EXISTS ix_aidlex_mcp_documents_case_id ON aidlex_mcp.documents (case_id);

CREATE TABLE IF NOT EXISTS aidlex_mcp.legal_sources (
	id VARCHAR(40) NOT NULL, 
	title TEXT, 
	url TEXT, 
	text TEXT, 
	metadata JSON, 
	content_hash VARCHAR(64), 
	created_at VARCHAR(40), 
	PRIMARY KEY (id), 
	UNIQUE (content_hash)
);

CREATE TABLE IF NOT EXISTS aidlex_mcp.rate_limits (
	key VARCHAR(200) NOT NULL, 
	"window" INTEGER NOT NULL, 
	count INTEGER NOT NULL, 
	PRIMARY KEY (key, "window")
);
