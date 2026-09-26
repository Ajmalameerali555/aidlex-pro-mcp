# Aidlex Pro MCP deployment design

## Purpose
A runnable ChatGPT-compatible remote MCP service preserving Aidlex’s ten published tool names, its evidence/citation/memory output schemas, and formal UAE drafting workflow. This is software-assisted legal research and drafting, not an advocate, autonomous filing service, or guarantee of legal accuracy.

## Architecture
Python 3.13 + FastAPI, stateless JSON responses over Streamable HTTP at /mcp. Explicit MCP methods and version negotiation follow the official transport specification. SQLite on a persistent volume for single-node installations; SQLAlchemy PostgreSQL support for App Platform. No required MCP SDK download: an independently implemented transport is covered by contract tests and an optional SDK interoperability probe.

## Authentication
Public mode is bounded to non-private templates, registry, and internal guidance retrieval. No private read/write or paid-model calls. OAuth mode validates JWT signature, exact issuer, resource audience, expiry, not-before and tool scopes against a configured established identity provider. Single-owner bearer mode is for local/developer clients only, NOT ChatGPT public submission. User/case ownership derives from verified credentials, never model-supplied user IDs. No default production secrets.

## Evidence and reasoning
Raw page text is preserved. Search uses Arabic-aware BM25, with optional configured embeddings and reciprocal-rank fusion. Every result carries document/page/character provenance and source status. Nothing becomes official law just because it has an official-looking URL. Official retrieval is URL-allowlisted, HTTPS-only, size-limited and redirect-checked, with retrieval date and content hash. Applicability and current legal effect remain separate checks.

Host execution returns a structured evidence-grounded work package for ChatGPT; optional server execution uses the OpenAI Responses API with store=false, configurable model, strict structured output, timeout and three documented synthesis/review stages. It cannot manufacture human professional experience.

## Persistence and privacy
Separate aidlex_mcp database tables, tenant filters on every private query, confirmation gates for writes and erasure, optimistic memory revision checks, content-hash deduplication, scoped audit events without raw case text, bounded input/output and per-principal rate limiting. No private uploaded reports are shipped. PostgreSQL uses a non-public schema; no Supabase service-role key is exposed.

## Scope and limitations
The payload ingests extracted text/pages, not direct ChatGPT attachment IDs. Scan/OCR and DOCX/PDF rendering stay with the host or existing Aidlex client services. The official source registry is a research map, not a complete UAE case-law database. Deployment, live OAuth linking, live database connection and paid model quality require operator configuration and live testing.
