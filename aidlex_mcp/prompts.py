from pathlib import Path
from .config import ROOT

MODULES={
    'core':'00_core_system.md','legal_analysis':'10_legal_analysis.md','case_discussion':'20_case_discussion.md',
    'instant_chat':'15_instant_chat.md','legal_drafting':'30_legal_drafting_uae_arabic.md',
    'final_review':'40_final_review.md','judge_review':'45_final_review_judge_mode.md',
    'evidence_timeline':'55_evidence_timeline_engine.md','case_memory':'60_case_memory.md',
    'source_citation':'65_source_citation_engine.md','rag':'50_rag_retrieval.md','strategic_engine':'70_strategic_engine.md',
}

def get_prompt(module,language='en'):
    if module not in MODULES: raise ValueError('Unknown Aidlex module.')
    files=['00_core_system.md','05_language_contract.md','70_strategic_engine.md',MODULES[module]]
    parts=[(ROOT/'prompts'/f).read_text() for f in dict.fromkeys(files)]
    return '\n\n'.join(parts)+f'\n\nRequested communication/output language: {language}. Evidence language does not override this preference.'

def schema(name):
    import json
    if name not in {p.stem for p in (ROOT/'schemas').glob('*.json')}: raise ValueError('Unknown schema.')
    return json.loads((ROOT/'schemas'/f'{name}.json').read_text())
