# Security and data handling

## Implemented controls

Private case ownership comes exclusively from a verified OAuth identity, never a `userId` tool argument. Every private record query is scoped. Developer bearer mode is deliberately a single local account. Case ingestion, memory replacement and deletion require confirmation flags, which the host must set only after actual user authorization.

Tool inputs reject unknown fields, restrict sizes and validate types. JSON transport rejects duplicate object members, non-finite constants and oversized bodies. Origin/Host controls, security headers, rate limits and sanitized operational errors are present. Writes/destructive actions are annotated for the MCP client.

Official-source retrieval uses an exact approved-host registry, HTTPS, public-address checks, validated redirects, bounded responses and media-type restrictions. The source directory is curated, not an unrestricted crawler. Source text and case evidence are treated as untrusted data in analysis instructions.

The runtime image runs as a non-root user. Compose drops Linux capabilities, disables privilege escalation and uses a read-only root filesystem with explicit writable storage. Actual container execution has not been validated in this build environment.

## Operator responsibilities before private use

Use TLS end-to-end where supported, encrypted hosting volumes and encrypted managed-database storage. The application does **not** implement field-level encryption or an HSM. Its own database and backups must be treated as confidential.

PostgreSQL tables live in the private `aidlex_mcp` schema. Access is controlled by database credentials and application ownership filters, **not PostgreSQL row-level security policies**. Do not expose this schema through Supabase/PostgREST, anonymous database roles, browser clients or a shared public API. Review schema/table/default grants and isolate the database role. Source curation affects public material; only trusted curators may use it.

Secrets belong in the local protected `.env` or hosting secret settings. Never place OpenAI keys, database URLs, service-role credentials or access tokens into tool arguments, the companion mobile app or logs. The generated DigitalOcean spec can contain secrets and is gitignored; delete or retain it securely after deployment.

Set retention, backup, recovery, incident handling, user consent and data-processing arrangements before real legal cases. Deletion removes active case records and their case audit entries; it does not remotely remove copies from provider systems, client chats or pre-existing backups. Backup expiry is the operator's responsibility.

## External disclosures

Host analysis returns selected case material to the authorized MCP client. Optional server inference sends the selected evidence context/draft to OpenAI. Optional embeddings send document chunks/search queries to OpenAI. The API request uses `store: false`, but no zero-retention guarantee is made. Check your organization's provider terms and requirements.

Official HTML source fetches contact approved source hosts. Disable this with `AIDLEX_RESEARCH_NETWORK_ENABLED=false` when outbound research is not permitted. The source fetcher checks DNS before the HTTP client resolves/connects; connection-level DNS pinning is not implemented. Use an egress firewall/proxy policy blocking private, link-local and cloud-metadata addresses as defense in depth.

## Operational constraints

HTTP requests are async, but SQLAlchemy operations and BM25 ranking execute synchronously. This is a bounded small-deployment design, not a high-throughput distributed service. Behind a reverse proxy, transport-level rate limiting sees that proxy peer; user-level limits remain keyed by authenticated identity. Configure edge/WAF limits appropriate to your host instead of trusting arbitrary `X-Forwarded-For` headers.

No background scheduler, malware scanner, antivirus, document OCR, signing service, court integration, payment processor or legal compliance certification is provided. Prompt-injection mitigations and citation validation reduce risks; they cannot prove a model's legal reasoning is correct.
