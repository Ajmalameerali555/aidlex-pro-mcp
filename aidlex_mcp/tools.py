"""Public, auditable tool registry with precise side-effect annotations."""
from dataclasses import dataclass
from pydantic import BaseModel
from . import models as m
from .prompts import schema

@dataclass(frozen=True)
class Tool:
    name: str
    model: type[BaseModel]
    description: str
    scopes: tuple[str,...]=()
    public: bool=False
    write: bool=False
    destructive: bool=False
    external: bool=False
    idempotent: bool=True

TOOLS=[
    Tool('aidlex_server_status',m.Empty,'Read Aidlex runtime readiness, authentication mode and retrieval capabilities without exposing secrets or private case counts.',public=True),
    Tool('ingest_uae_legal_source',m.IngestSource,'CURATOR ONLY. Persist an explicitly approved source in the shared legal library. official_fetch retrieves the URL itself; other text remains unverified. Does not certify legal applicability.',('aidlex:curate',),write=True,external=True),
    Tool('ingest_case_document',m.IngestDocument,'Persist extracted document text or numbered pages in the authenticated user’s case. Requires confirmed=true after explicit user consent. No attachment IDs, secrets or remote file URLs.',('aidlex:write',),write=True),
    Tool('rag_search',m.SearchInput,'Retrieve cited official/internal source text, case documents and confirmed memory. Public callers can search only the non-private library. verifiedOnly means fresh official-origin retrieval, NOT verified legal applicability.',public=True),
    Tool('get_case_memory',m.CaseInput,'Read the authenticated user’s current case memory and revision before any update. Memory is context, not evidence.',('aidlex:read',)),
    Tool('update_case_memory',m.UpdateMemory,'REPLACE the confirmed case-memory snapshot using expectedRevision for conflict detection. Preserve still-valid items, remove superseded facts, and require explicit user consent. Do not store speculation.',('aidlex:write',),write=True,destructive=True,idempotent=False),
    Tool('build_evidence_timeline',m.TimelineInput,'Build a cited timeline from ingested pages. local extracts explicit date mentions only; server uses the configured paid model for structured extraction, with exact-quote validation. Does not persist the timeline.',('aidlex:read',),external=True),
    Tool('create_source_citation_pack',m.CitationInput,'Build a source pack distinguishing official-origin law text, user-document facts, memory and internal material. Claims are not automatically legally validated.',('aidlex:read',)),
    Tool('create_draft_handoff_pack',m.HandoffInput,'Build a drafting handoff only from the user-approved exact DraftPlan and DiscussionPack with no missing fields or unverified legal sources. This does not generate, sign, file or persist a final court document.',('aidlex:read',)),
    Tool('get_aidlex_prompt_template',m.PromptInput,'Read evidence-grounded Aidlex module instructions: analysis, strategy, Arabic drafting, judge-style review, source checks, timelines and memory. No private data or model calls.',public=True),
    Tool('get_source_registry',m.Empty,'Read the bundled official UAE-source research directory. It is a map, not a verified legal corpus or proof that any source is current.',public=True),
    Tool('analyze_case',m.AnalyzeInput,'Prepare an evidence-grounded work package for ChatGPT (host), or run paid three-pass model analysis, opposing-case review and synthesis (server). Not a licensed advocate or prediction guarantee.',('aidlex:read',),external=True),
    Tool('review_legal_draft',m.ReviewInput,'Compare a supplied draft against private case evidence using host execution or paid server analysis. Check relief, numbers, dates, contradictions, source support and procedural risks; no filing occurs.',('aidlex:read',),external=True),
    Tool('calculate_case_amounts',m.MoneyInput,'Reconcile AED charges, payments and credits using exact Decimal arithmetic. Does not prove payment attribution, calculate legal interest or determine enforceable debt.',('aidlex:read',)),
    Tool('fetch_case_document',m.FetchDocument,'Fetch exact numbered pages from an accessible private case document, with pagination. Never retrieves another user’s documents.',('aidlex:read',)),
    Tool('list_cases',m.ListCases,'List only the authenticated user’s cases, with offset pagination.',('aidlex:read',)),
    Tool('export_case_data',m.CaseInput,'Read an export of the authenticated user’s case documents and memory. Large cases must be fetched document-by-document; no public download links are generated.',('aidlex:read',)),
    Tool('delete_case_data',m.DeleteCase,'PERMANENTLY DELETE the authenticated user’s case documents, chunks, memory and case audit entries. Requires explicit consent and an exact repeated case ID. Backups are subject to operator retention.',('aidlex:delete',),write=True,destructive=True),
]
BY_NAME={tool.name:tool for tool in TOOLS}

def visible_tools(settings):
    return [t for t in TOOLS if settings.auth_mode!='public' or t.public]

def descriptor(tool,settings):
    out={'name':tool.name,'description':tool.description,'inputSchema':tool.model.model_json_schema(),
         'outputSchema':schema('McpToolResult.schema'),
         'annotations':{'title':tool.name.replace('_',' ').title(),'readOnlyHint':not tool.write,'destructiveHint':tool.destructive,'idempotentHint':tool.idempotent,'openWorldHint':tool.external}}
    if tool.public:
        schemes=[{'type':'noauth'}]
        if tool.name=='rag_search' and settings.auth_mode=='oauth': schemes.append({'type':'oauth2','scopes':['aidlex:read']})
    elif settings.auth_mode=='oauth': schemes=[{'type':'oauth2','scopes':list(tool.scopes)}]
    else: schemes=[]
    if schemes:
        out['securitySchemes']=schemes
        out['_meta']={'securitySchemes':schemes}
    return out
