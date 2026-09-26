from datetime import datetime, timezone
import pytest
from aidlex_mcp.config import Settings
from aidlex_mcp.store import Store
from aidlex_mcp.text import normalize, split_pages, bm25_search
from aidlex_mcp.sources import validate_source_url


def test_arabic_normalization_is_search_only():
    assert normalize('إثبـاتُ السَّداد') == normalize('اثبات السداد')


def test_chunk_boundaries_preserve_original():
    raw = 'السداد بتاريخ 2026-06-17 مبلغ 213,100 درهم.\n' * 100
    chunks = split_pages([{'page_number': 4, 'text': raw}], size=500, overlap=60)
    assert len(chunks) > 1
    assert all(x['text'] == raw[x['start']:x['end']] for x in chunks)
    assert all(x['page_number'] == 4 for x in chunks)
    assert chunks[0]['start'] == 0 and chunks[-1]['end'] == len(raw)


def test_chunk_coverage_no_dropped_text():
    raw = 'A' * 5000
    chunks = split_pages([{'page_number': 1, 'text': raw}],size=400,overlap=50)
    assert set(range(len(raw))) == set(i for c in chunks for i in range(c['start'],c['end']))


def test_search_arabic_and_no_irrelevant_hits():
    items = [{'id':'a','text':'إثبات السداد في عقد الإيجار'}, {'id':'b','text':'عقد العمل والأجر'}]
    assert bm25_search('اثبات السداد',items)[0]['id'] == 'a'
    assert bm25_search('volcano',items) == []


@pytest.mark.parametrize('url',[
    'http://uaelegislation.gov.ae/law','https://uaelegislation.gov.ae.evil.com',
    'https://uaelegislation.gov.ae@evil.com/a','https://127.0.0.1/a',
    'https://169.254.169.254/latest/meta-data','file:///etc/passwd',
    'https://uaelegislation.gov.ae:444/a','https://uaelegislation.gov.ae./a'])
def test_url_rejects_ssrf_and_lookalikes(url):
    with pytest.raises(ValueError): validate_source_url(url,{'uaelegislation.gov.ae'})


def test_url_accepts_only_registry_host():
    assert validate_source_url('https://uaelegislation.gov.ae/en/legislations/1', {'uaelegislation.gov.ae'})


def test_production_config_rejects_insecure_bearer():
    with pytest.raises(ValueError): Settings(auth_mode='bearer', bearer_token='short')


@pytest.fixture
def store(tmp_path):
    s=Store('sqlite:///'+str(tmp_path/'test.db'))
    s.initialize()
    return s


def test_user_case_isolation(store):
    doc=store.ingest_document('alice','case-1','Contract',[{'page_number':1,'text':'private data'}],{})
    assert store.get_document('alice',doc['document_id'])
    assert store.get_document('bob',doc['document_id']) is None
    assert store.case_documents('bob','case-1') == []


def test_dedup_scoped_to_user_case(store):
    pages=[{'page_number':1,'text':'paid'}]
    one=store.ingest_document('alice','c','Receipt',pages,{})
    two=store.ingest_document('alice','c','Receipt',pages,{})
    three=store.ingest_document('bob','c','Receipt',pages,{})
    assert one['document_id']==two['document_id']
    assert three['document_id']!=one['document_id']


def test_memory_revision_prevents_lost_updates(store):
    assert store.get_memory('alice','c')['revision']==0
    assert store.save_memory('alice','c',{'memories':[]},0)['revision']==1
    with pytest.raises(ValueError): store.save_memory('alice','c',{'memories':[]},0)
    assert store.get_memory('bob','c')['revision']==0


def test_delete_scoped(store):
    p=[{'page_number':1,'text':'evidence'}]
    store.ingest_document('alice','c','A',p,{})
    store.ingest_document('bob','c','B',p,{})
    store.delete_case('alice','c')
    assert store.case_documents('alice','c')==[]
    assert len(store.case_documents('bob','c'))==1


def test_rate_limit_window(store):
    assert store.consume_limit('u',2,now=120)
    assert store.consume_limit('u',2,now=120)
    assert not store.consume_limit('u',2,now=120)
    assert store.consume_limit('u',2,now=180)
