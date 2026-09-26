# Aidlex Pro MCP — Deployment Package

**Version 1.0.0 · Python 3.13 · Streamable HTTP · 18 tools**

A standalone MCP backend built around the supplied Aidlex workflow, source registry, prompts and JSON contracts. It provides evidence-grounded legal/document intelligence, authenticated case storage and structured strategic analysis. It does not impersonate a licensed advocate, promise outcomes, or bundle a complete/current UAE legal database.

## Start here

For deployment, read **[DEPLOYMENT.md](docs/DEPLOYMENT.md)**. For private cases in ChatGPT, also complete **[AUTHENTICATION.md](docs/AUTHENTICATION.md)**. The server is implemented; your hosting address, identity provider and private database are operator-controlled resources and are not invented or provisioned by this ZIP.

### Local private developer test

Run from the extracted directory containing this README. Use Python 3.13 with network access to the package index:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python scripts/configure.py --local
python -m aidlex_mcp
```

In another terminal, in the same directory:

```bash
source .venv/bin/activate
python scripts/smoke_test.py
```

The wizard writes a randomly generated developer credential to `.env` with owner-only permissions. The checker reads it locally; do not paste it into ChatGPT. This single-owner bearer profile is for developer tests, **not ChatGPT public authentication**. Case identities created in this profile are not automatically reassigned to OAuth users.

For a public, read-only local test instead, use `python scripts/configure.py --public-local` on a fresh configuration. It exposes four public tools and cannot ingest, read or analyze private case records.

### Docker alternative

With Docker Engine and the Compose plugin already installed:

```bash
python3 scripts/configure.py --local
docker compose up --build -d
python3 scripts/smoke_test.py
```

Choose either native Python or Docker for the same port, not both. Existing `.env` files are never silently overwritten. Preserve them and edit deliberately when changing profiles.

## Capabilities

| Area | Implemented behavior |
|---|---|
| MCP | Initialization, tools, resources and prompts over stateless JSON Streamable HTTP at `/mcp`; health/readiness endpoints; input/output schema validation. |
| Case records | Explicit-consent ingestion of extracted text or numbered pages; content hashes; scoped deduplication; source/page preservation; document pagination. |
| Search | Arabic-aware normalization for search only; BM25 over stored chunks; optional embedding/BM25 reciprocal-rank fusion; source/date/jurisdiction filters; truncation warnings. |
| Memory | Confirmed snapshots with optimistic revision checks; evidence remains separate from memory; cross-user isolation. |
| Sources | Official-source directory, constrained HTML retrieval, original/extracted content hashes, origin and freshness labels. Official retrieval is not automatic legal applicability verification. |
| Strategic work | Host work packages, or optional server-side analysis → adversarial review → synthesis; allegations, facts, memory, inferences and unverified law remain separate. |
| Review | Draft comparison against case evidence; opposing arguments, remedy mismatch, causation/materiality, missing proof and procedural checks. |
| Timelines | Local extraction of explicit date mentions; optional model-assisted extraction with exact-quote checks; ambiguity and incomplete coverage surfaced. |
| Drafting | Existing Arabic drafting/review prompts; confirmed-plan handoff with missing-field and verification gates. No signature, court submission or automatic legal approval. |
| Accounting | Exact AED decimal reconciliation of charges, payments and credits. Arithmetic does not establish payment allocation or legal discharge. |
| Privacy | OAuth JWT resource-server support; authenticated ownership; scoped tools; case export and explicit erasure. |

## Two analysis execution modes

**`execution: "host"` is the default.** The server returns an evidence-and-instructions work package, and ChatGPT performs the reasoning. The response explicitly says no server model ran. This is not a completed server-generated opinion. No separate OpenAI API key is needed for this mode; your ChatGPT product access is separate.

**`execution: "server"` is optional and billable.** Configure `OPENAI_API_KEY` and the exact `AIDLEX_MODEL` available in your API account. The user must also have `aidlex:analyze`. Case analysis performs three sequential model calls: initial analysis, adversarial critique and synthesis. These are three passes, not three independent human lawyers. All use the configured model. Responses request `store: false`; this does not replace the provider's retention terms. Missing keys, unsupported models, incomplete outputs, timeouts and validation failures are reported rather than disguised as success. Live provider calls have not been executed in this build environment.

Embeddings are off by default. Enabling `AIDLEX_EMBEDDINGS_ENABLED` sends new ingested document chunks and authenticated search queries to the API. Existing chunks are not silently re-embedded. Public anonymous search does not initiate paid model calls.

## Preserved canonical tools

`aidlex_server_status`, `ingest_uae_legal_source`, `ingest_case_document`, `rag_search`, `get_case_memory`, `update_case_memory`, `build_evidence_timeline`, `create_source_citation_pack`, `create_draft_handoff_pack`, `get_aidlex_prompt_template`.

## Additional tools

`get_source_registry`, `analyze_case`, `review_legal_draft`, `calculate_case_amounts`, `fetch_case_document`, `list_cases`, `export_case_data`, `delete_case_data`.

The complete machine-readable descriptors are in **[docs/MCP_TOOLS.json](docs/MCP_TOOLS.json)**. Runtime `tools/list` is authoritative for the configured profile. There are 18 descriptors in authenticated deployments and four in public-only deployments. Discovery does not grant permission to invoke protected tools.

## What is included

`aidlex_mcp/` contains executable server code. `prompts/`, `schemas/` and `knowledge/` retain the reusable supplied Aidlex materials and add strategic review contracts. `scripts/` contains configuration, deployment generation, diagnostics and live probes. `deploy/` contains HTTPS and PostgreSQL setup. `tests/` contains the automated suite. GitHub Actions runs tests and a container build when the repository is pushed to your account.

Private case-report uploads, App Store images, API credentials, database files and the companion app are not bundled. The original mobile app and Supabase functions have not been modified or automatically synchronized. This backend uses its own `aidlex_mcp` PostgreSQL schema or an isolated SQLite database.

## Verification and limits

Read **[VERIFICATION.md](docs/VERIFICATION.md)** for the precise tested scope and **[LIMITATIONS.md](docs/LIMITATIONS.md)** before processing confidential matters. This package is not a declaration of production certification or ChatGPT listing approval. A public URL exists only after you deploy it.
