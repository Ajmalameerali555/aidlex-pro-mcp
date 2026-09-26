import time
import json
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from aidlex_mcp.config import Settings
from aidlex_mcp.app import create_app
from aidlex_mcp.auth import TokenVerifier, AuthFailure

@pytest.fixture
def public_client(tmp_path):
    app=create_app(Settings(database_url='sqlite:///'+str(tmp_path/'public.db'),rate_limit_per_minute=500))
    with TestClient(app) as c: yield c

@pytest.fixture
def private_client(tmp_path):
    app=create_app(Settings(auth_mode='bearer',bearer_token='t'*48,database_url='sqlite:///'+str(tmp_path/'private.db'),rate_limit_per_minute=500))
    with TestClient(app,headers={'Authorization':'Bearer '+'t'*48}) as c: yield c

HEADERS={'Accept':'application/json, text/event-stream','MCP-Protocol-Version':'2025-11-25'}

def rpc(c,method,params=None,id=1,headers=None):
    body={'jsonrpc':'2.0','method':method,'params':params or {}}
    if id is not None: body['id']=id
    return c.post('/mcp',json=body,headers={**HEADERS,**(headers or {})})

def test_initialize_and_versions(public_client):
    r=rpc(public_client,'initialize',{'protocolVersion':'2025-11-25','capabilities':{},'clientInfo':{'name':'test','version':'1'}})
    assert r.status_code==200
    assert r.json()['result']['protocolVersion']=='2025-11-25'
    assert 'tools' in r.json()['result']['capabilities']

def test_notification_accepted(public_client):
    r=rpc(public_client,'notifications/initialized',id=None)
    assert r.status_code==202 and r.content==b''

def test_get_can_decline_sse(public_client):
    assert public_client.get('/mcp',headers=HEADERS).status_code==405

def test_public_no_private_tools(public_client):
    tools=rpc(public_client,'tools/list').json()['result']['tools']
    names={t['name'] for t in tools}
    assert 'get_aidlex_prompt_template' in names
    assert 'ingest_case_document' not in names
    r=rpc(public_client,'tools/call',{'name':'get_case_memory','arguments':{'caseId':'c'}})
    assert 'error' in r.json()

def test_missing_accept_rejected(public_client):
    r=public_client.post('/mcp',json={'jsonrpc':'2.0','id':1,'method':'ping'})
    assert r.status_code==406

def test_origin_rejected(public_client):
    r=rpc(public_client,'ping',headers={'Origin':'https://evil.invalid'})
    assert r.status_code==403

def test_unknown_protocol_header_rejected(public_client):
    assert rpc(public_client,'ping',headers={'MCP-Protocol-Version':'1900-01-01'}).status_code==400

def test_unknown_method(public_client):
    assert rpc(public_client,'not-real').json()['error']['code']==-32601

def test_invalid_json(public_client):
    r=public_client.post('/mcp',content=b'{broken',headers={**HEADERS,'content-type':'application/json'})
    assert r.status_code==400

def test_ten_core_tools_present(private_client):
    names={t['name'] for t in rpc(private_client,'tools/list').json()['result']['tools']}
    assert {'aidlex_server_status','rag_search','get_case_memory','ingest_case_document',
       'ingest_uae_legal_source','update_case_memory','build_evidence_timeline',
       'create_source_citation_pack','create_draft_handoff_pack','get_aidlex_prompt_template'} <= names

def test_private_tool_requires_auth(private_client):
    r=rpc(private_client,'tools/call',{'name':'get_case_memory','arguments':{'caseId':'c'}},headers={'Authorization':''})
    assert r.json()['result']['isError'] is True

def test_tool_input_forbids_user_id(private_client):
    r=rpc(private_client,'tools/call',{'name':'get_case_memory','arguments':{'caseId':'c','userId':'victim'}})
    assert r.json()['result']['isError']

def test_ingest_requires_confirmation(private_client):
    args={'caseId':'case-1','title':'Receipt','text':'paid 100 AED','confirmed':False}
    r=rpc(private_client,'tools/call',{'name':'ingest_case_document','arguments':args})
    assert r.json()['result']['isError']

def test_full_document_search_workflow(private_client):
    args={'caseId':'case-1','title':'Receipt','pages':[{'page_number':2,'text':'إثبات السداد بتاريخ 2026-06-17 بقيمة 213,100 درهم.'}],'confirmed':True}
    r=rpc(private_client,'tools/call',{'name':'ingest_case_document','arguments':args})
    assert r.status_code==200, r.text
    result=r.json()['result']; assert not result.get('isError'),result
    doc=result['structuredContent']['data']['document_id']
    r=rpc(private_client,'tools/call',{'name':'rag_search','arguments':{'caseId':'case-1','query':'اثبات السداد','includeLegalSources':False}})
    result=r.json()['result']['structuredContent']; assert result['ok'],result
    hits=result['data']['results']['case_documents']
    assert hits[0]['source_id']==doc and hits[0]['page_number']==2

def test_health_no_secrets(public_client):
    assert public_client.get('/healthz').json()=={'status':'ok'}
    assert public_client.get('/readyz').status_code==200

@pytest.fixture
def signing_key(): return rsa.generate_private_key(public_exponent=65537,key_size=2048)

@pytest.fixture
def verifier(signing_key):
    settings=Settings(auth_mode='oauth',public_base_url='https://mcp.example.test',oauth_issuer='https://auth.example.test/',oauth_jwks_url='https://auth.example.test/jwks',oauth_audience='https://mcp.example.test/mcp')
    v=TokenVerifier(settings)
    v.keys={'key1':jwt.PyJWK.from_json(jwt.algorithms.RSAAlgorithm.to_jwk(signing_key.public_key()))}
    v.cache_expires=time.monotonic()+3600
    return v

def token(key,**overrides):
    claims={'iss':'https://auth.example.test/','aud':'https://mcp.example.test/mcp','sub':'alice','exp':int(time.time())+300,'iat':int(time.time()),'scope':'aidlex:read aidlex:write'}
    claims.update(overrides)
    return jwt.encode(claims,key,algorithm='RS256',headers={'kid':'key1'})

@pytest.mark.asyncio
async def test_valid_jwt(verifier,signing_key):
    principal=await verifier.verify(token(signing_key))
    assert 'aidlex:write' in principal.scopes and principal.owner!='alice'

@pytest.mark.asyncio
@pytest.mark.parametrize('change',[{'aud':'wrong'},{'iss':'https://evil.invalid'},{'exp':1},{'nbf':9999999999},{'sub':''}])
async def test_bad_jwt_rejected(verifier,signing_key,change):
    with pytest.raises(AuthFailure): await verifier.verify(token(signing_key,**change))
