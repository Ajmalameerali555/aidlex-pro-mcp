"""Versioned tool contracts. No caller-controlled owner/user identifiers."""
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

Short = Annotated[str, Field(min_length=1, max_length=500)]
CaseID = Annotated[str, Field(min_length=1, max_length=128, pattern=r'^[A-Za-z0-9_:/.-]+$')]

class Input(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=False)

class Empty(Input): pass

class CaseInput(Input):
    caseId: CaseID

class Page(Input):
    page_number: int = Field(ge=1,le=100000)
    text: str = Field(min_length=1,max_length=200000)

class IngestDocument(CaseInput):
    title: Short
    text: str | None = Field(default=None,min_length=1,max_length=200000)
    pages: list[Page] | None = Field(default=None,min_length=1,max_length=500)
    documentType: str = Field(default='user_document',max_length=100)
    confirmed: bool = False
    @model_validator(mode='after')
    def check_content(self):
        if bool(self.text) == bool(self.pages): raise ValueError('Supply exactly one of text or pages.')
        if self.pages:
            if len({p.page_number for p in self.pages})!=len(self.pages): raise ValueError('Page numbers must be unique.')
            if sum(len(p.text) for p in self.pages)>200000: raise ValueError('Document exceeds 200000 characters. Split into named volumes.')
        if self.text and not self.text.strip(): raise ValueError('Document text cannot be blank.')
        if self.pages and any(not p.text.strip() for p in self.pages): raise ValueError('Blank pages are not searchable. Mark unreadable/blank pages in the title or use a descriptive extraction note.')
        return self

class IngestSource(Input):
    title: Short
    url: str | None = Field(default=None,max_length=2048)
    text: str | None = Field(default=None,min_length=1,max_length=200000)
    jurisdiction: str = Field(default='Unspecified',max_length=100)
    materialType: Literal['official_fetch','internal_guidance','user_supplied_legal_text']='official_fetch'
    confirmed: bool = False
    @model_validator(mode='after')
    def check_source(self):
        if self.materialType=='official_fetch':
            if not self.url or self.text is not None: raise ValueError('official_fetch requires a URL and fetches the original text itself; do not supply text.')
        elif not self.text or not self.text.strip(): raise ValueError('Text is required for non-fetched material.')
        return self

class SearchInput(Input):
    query: str = Field(min_length=1,max_length=2000)
    caseId: CaseID | None = None
    includeLegalSources: bool = True
    includeCaseDocs: bool = True
    includeMemory: bool = True
    jurisdiction: str | None = Field(default=None,max_length=100)
    verifiedOnly: bool = False
    topK: int = Field(default=12,ge=1,le=40)

class MemoryItem(Input):
    scope: Literal['case','user','module']
    memory_type: str = Field(min_length=1,max_length=100)
    memory_text: str = Field(min_length=1,max_length=5000)
    memory_json: dict | None = None
    importance: int = Field(ge=1,le=5)
    confidence_score: float = Field(ge=0,le=1)

class MemoryPayload(Input):
    memories: list[MemoryItem] = Field(max_length=200)

class UpdateMemory(CaseInput):
    memory: MemoryPayload
    expectedRevision: int = Field(ge=0)
    confirmed: bool = False

class TimelineInput(CaseInput):
    execution: Literal['local','server']='local'
    language: Literal['en','ar']='en'

class CitationInput(SearchInput):
    claimsToCheck: list[str] = Field(default_factory=list,max_length=50)

class HandoffInput(CaseInput):
    plan: dict
    discussion: dict
    confirmed: bool = False

class PromptInput(Input):
    module: Literal['core','legal_analysis','case_discussion','instant_chat','legal_drafting','final_review','judge_review','evidence_timeline','case_memory','source_citation','rag','strategic_engine']='strategic_engine'
    language: Literal['en','ar']='en'

class AnalyzeInput(CaseInput):
    question: str = Field(min_length=1,max_length=4000)
    mode: Literal['analysis','strategy','judge_review']='strategy'
    language: Literal['en','ar']='en'
    execution: Literal['host','server']='host'

class ReviewInput(CaseInput):
    draft: str = Field(min_length=1,max_length=40000)
    language: Literal['en','ar']='en'
    execution: Literal['host','server']='host'

class MoneyItem(Input):
    description: Short
    amount: str = Field(pattern=r'^\d{1,15}(\.\d{1,2})?$')
    kind: Literal['charge','payment','credit']
    source_ref: str | None = Field(default=None,max_length=100)

class MoneyInput(Input):
    entries: list[MoneyItem] = Field(min_length=1,max_length=1000)
    currency: Literal['AED']='AED'

class FetchDocument(Input):
    documentId: str = Field(min_length=1,max_length=40,pattern=r'^[a-f0-9]+$')
    startPage: int = Field(default=1,ge=1)
    pageCount: int = Field(default=10,ge=1,le=30)

class ListCases(Input):
    limit: int = Field(default=50,ge=1,le=100)
    offset: int = Field(default=0,ge=0,le=100000)

class DeleteCase(CaseInput):
    confirmCaseId: CaseID
    confirmed: bool = False

class Finding(Input):
    statement: str
    classification: Literal['document_fact','user_claim','memory','inference','verified_source_text','unconfirmed_legal_point']
    source_refs: list[str]
    verification_needed: str | None = None

class Issue(Input):
    issue: str
    user_position: str
    opposing_position: str
    evidence_assessment: str
    source_refs: list[str]
    verification_needed: list[str]

class Route(Input):
    route: str
    benefit: str
    downside: str
    required_evidence: list[str]
    procedural_checks: list[str]
    source_refs: list[str]

class AnalysisReport(Input):
    summary: str
    jurisdiction_assessment: str
    material_findings: list[Finding]
    issues: list[Issue]
    strategic_options: list[Route]
    recommended_route: str
    fallback_route: str
    adverse_scenario: str
    missing_information: list[str]
    immediate_actions: list[str]
    unverified_legal_points: list[str]
    limitations: list[str]
