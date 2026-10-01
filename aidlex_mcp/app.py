"""Stateless JSON Streamable HTTP MCP transport.

GET/SSE is intentionally declined with 405, which the transport specification
allows. All server responses are JSON; no MCP session identifiers are issued.
"""
from contextlib import asynccontextmanager
import json
import logging
from urllib.parse import urlsplit
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import ValidationError
from . import __version__
from .auth import TokenVerifier, AuthFailure
from .config import Settings
from .store import Store
from .service import Service, fail
from .prompts import MODULES, get_prompt
from .sources import registry
from .tools import BY_NAME, descriptor, visible_tools

log=logging.getLogger('aidlex')
PROTOCOLS=('2025-11-25','2025-06-18','2025-03-26')


def rpc_error(id,code,message,status=200):
    return JSONResponse({'jsonrpc':'2.0','id':id,'error':{'code':code,'message':message}},status_code=status)

def rpc_result(id,payload):
    return JSONResponse({'jsonrpc':'2.0','id':id,'result':payload})

def tool_result(result,meta=None):
    value={'content':[{'type':'text','text':json.dumps(result,ensure_ascii=False,separators=(',',':'))}],'structuredContent':result,'isError':not result['ok']}
    if meta: value['_meta']=meta
    return value

def unique_object(pairs):
    obj={}
    for key,value in pairs:
        if key in obj: raise ValueError('Duplicate JSON object member.')
        obj[key]=value
    return obj

def invalid_number(_): raise ValueError('JSON numbers must be finite.')


def create_app(settings=None):
    settings=settings or Settings()
    store=Store(settings.database_url.get_secret_value(),settings.database_schema)
    service=Service(settings,store)
    verifier=TokenVerifier(settings)

    @asynccontextmanager
    async def lifespan(app):
        if settings.auto_migrate: store.initialize()
        service.seed_internal_knowledge()
        yield
        store.engine.dispose()

    app=FastAPI(title='Aidlex Pro MCP',version=__version__,docs_url=None,redoc_url=None,openapi_url=None,lifespan=lifespan)
    app.state.settings=settings; app.state.store=store; app.state.service=service; app.state.verifier=verifier
    hosts=list(set([urlsplit(settings.public_base_url).hostname,'localhost','127.0.0.1']+settings.allowed_hosts+(['testserver'] if settings.environment=='development' else [])))
    app.add_middleware(TrustedHostMiddleware,allowed_hosts=hosts)
    origins=list(set(settings.allowed_origins+[settings.public_base_url]))
    app.add_middleware(CORSMiddleware,allow_origins=origins,allow_methods=['GET','POST','OPTIONS'],allow_headers=['Content-Type','Authorization','MCP-Protocol-Version','MCP-Session-Id','Accept','Last-Event-ID'],expose_headers=['WWW-Authenticate','MCP-Protocol-Version'],allow_credentials=False)

    @app.middleware('http')
    async def security_headers(request,call_next):
        if request.url.path=='/mcp' and request.headers.get('origin') and request.headers['origin'] not in origins:
            return JSONResponse({'error':'Origin not allowed.'},status_code=403)
        response=await call_next(request)
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='no-referrer'
        response.headers['Cache-Control']='no-store'
        response.headers['Content-Security-Policy']="default-src 'none'; frame-ancestors 'none'"
        if settings.environment=='production': response.headers['Strict-Transport-Security']='max-age=31536000'
        return response

    @app.get('/')
    async def root():
        return {'service':'Aidlex Pro MCP','version':__version__,'endpoint':'/mcp','health':'/healthz','description':'Evidence-grounded legal/document intelligence; not legal representation.'}


    @app.get('/.well-known/openai-apps-challenge')
    async def openai_apps_challenge():
        return Response(
            content='oytnTnyka-mz1V-wo6am5rSew-E7vHLwQjna0iCbujA',
            media_type='text/plain; charset=utf-8'
        )

    @app.get('/healthz')
    async def health(): return {'status':'ok'}

    @app.get('/readyz')
    async def readiness():
        try:
            healthy=store.ping()
            return JSONResponse({'status':'ready' if healthy else 'not_ready'},status_code=200 if healthy else 503)
        except Exception:
            return JSONResponse({'status':'not_ready'},status_code=503)

    @app.get('/.well-known/oauth-protected-resource')
    @app.get('/.well-known/oauth-protected-resource/mcp')
    async def resource_metadata():
        if settings.auth_mode!='oauth': return JSONResponse({'error':'OAuth is not enabled in this deployment.'},status_code=404)
        return {'resource':settings.public_base_url+'/mcp','authorization_servers':[settings.oauth_issuer],'scopes_supported':['aidlex:read','aidlex:write','aidlex:analyze','aidlex:curate','aidlex:delete'],'bearer_methods_supported':['header']}

    @app.api_route('/mcp',methods=['GET','DELETE'])
    async def unsupported_transport():
        return Response(status_code=405,headers={'Allow':'POST, OPTIONS'})

    @app.post('/mcp')
    async def mcp_endpoint(request:Request):
        origin=request.headers.get('origin')
        if origin and origin not in origins: return JSONResponse({'error':'Origin not allowed.'},status_code=403)
        if request.headers.get('content-type','').split(';')[0].strip().lower()!='application/json':
            return JSONResponse({'error':'Content-Type must be application/json.'},status_code=415)
        accept={part.split(';')[0].strip().lower() for part in request.headers.get('accept','').split(',')}
        if not {'application/json','text/event-stream'}<=accept:
            return JSONResponse({'error':'Accept must include application/json and text/event-stream.'},status_code=406)
        protocol=request.headers.get('mcp-protocol-version','2025-03-26')
        if protocol not in PROTOCOLS: return JSONResponse({'error':'Unsupported MCP protocol version.'},status_code=400)
        # Trust the socket peer, never an arbitrary caller-provided X-Forwarded-For.
        peer=request.client.host if request.client else 'unknown'
        if not store.consume_limit('transport:'+peer,settings.rate_limit_per_minute*5):
            return JSONResponse({'error':'Rate limit exceeded.'},status_code=429,headers={'Retry-After':'60'})
        try: principal=await verifier.authenticate(request.headers.get('authorization'))
        except AuthFailure as e:
            challenge=verifier.challenge(error='invalid_token') if settings.auth_mode=='oauth' else 'Bearer realm="Aidlex"'
            return JSONResponse({'error':str(e)},status_code=401,headers={'WWW-Authenticate':challenge})
        key=principal.owner if principal else 'anonymous:'+peer
        if not store.consume_limit('principal:'+key,settings.rate_limit_per_minute):
            return JSONResponse({'error':'Rate limit exceeded.'},status_code=429,headers={'Retry-After':'60'})
        try:
            length=int(request.headers.get('content-length','0'))
            if length>settings.max_body_bytes or length<0: return JSONResponse({'error':'Request too large.'},status_code=413)
            body=bytearray()
            async for part in request.stream():
                body.extend(part)
                if len(body)>settings.max_body_bytes: return JSONResponse({'error':'Request too large.'},status_code=413)
            message=json.loads(body,object_pairs_hook=unique_object,parse_constant=invalid_number)
        except (ValueError,UnicodeDecodeError,RecursionError): return rpc_error(None,-32700,'Invalid JSON.',400)
        if not isinstance(message,dict) or message.get('jsonrpc')!='2.0': return rpc_error(None,-32600,'Expected a single JSON-RPC 2.0 message.',400)
        id=message.get('id'); method=message.get('method'); params=message.get('params',{})
        if not isinstance(method,str) or not isinstance(params,dict) or isinstance(id,bool) or (id is not None and not isinstance(id,(str,int))):
            return rpc_error(None,-32600,'Invalid request shape.',400)
        if id is None:
            if method.startswith('notifications/') and 'id' not in message: return Response(status_code=202)
            return rpc_error(None,-32600,'A request ID is required for this method.',400)
        if method=='initialize':
            client=params.get('clientInfo'); requested=params.get('protocolVersion')
            if not isinstance(client,dict) or not isinstance(client.get('name'),str) or not isinstance(client.get('version'),str) or not isinstance(requested,str) or not isinstance(params.get('capabilities'),dict):
                return rpc_error(id,-32602,'initialize requires protocolVersion, capabilities and clientInfo.')
            version=requested if requested in PROTOCOLS else PROTOCOLS[0]
            return rpc_result(id,{'protocolVersion':version,'serverInfo':{'name':'aidlex-pro','version':__version__},'capabilities':{'tools':{'listChanged':False},'resources':{'subscribe':False,'listChanged':False},'prompts':{'listChanged':False}},'instructions':'Aidlex Pro provides source-grounded UAE legal and document research tools. Public mode uses only the public Aidlex library and does not access private case data. Retrieved material is reference information and does not itself establish legal applicability.'})
        if method=='ping': return rpc_result(id,{})
        if method=='tools/list': return rpc_result(id,{'tools':[descriptor(t,settings) for t in visible_tools(settings)]})
        if method=='resources/list': return rpc_result(id,{'resources':[{'uri':'aidlex://registry','name':'UAE official-source registry','mimeType':'application/json'},{'uri':'aidlex://core','name':'Aidlex core operating contract','mimeType':'text/markdown'}]})
        if method=='resources/templates/list': return rpc_result(id,{'resourceTemplates':[]})
        if method=='resources/read':
            uri=params.get('uri')
            if uri not in ('aidlex://registry','aidlex://core'): return rpc_error(id,-32602,'Unknown resource URI.')
            text=json.dumps(registry(),ensure_ascii=False) if uri.endswith('registry') else get_prompt('core')
            return rpc_result(id,{'contents':[{'uri':uri,'mimeType':'application/json' if uri.endswith('registry') else 'text/markdown','text':text}]})
        if method=='prompts/list':
            return rpc_result(id,{'prompts':[{'name':key,'description':'Aidlex '+key.replace('_',' '),'arguments':[{'name':'language','description':'en or ar','required':False}]} for key in MODULES]})
        if method=='prompts/get':
            name=params.get('name'); args=params.get('arguments',{})
            if name not in MODULES or not isinstance(args,dict) or set(args)-{'language'} or args.get('language','en') not in ('en','ar'): return rpc_error(id,-32602,'Unknown prompt or invalid arguments.')
            return rpc_result(id,{'description':'Aidlex evidence-grounded module workflow','messages':[{'role':'user','content':{'type':'text','text':get_prompt(name,args.get('language','en'))}}]})
        if method!='tools/call': return rpc_error(id,-32601,'Method not supported.')
        name=params.get('name')
        if not isinstance(name,str) or name not in {t.name for t in visible_tools(settings)}: return rpc_error(id,-32602,'Unknown or unavailable tool.')
        tool=BY_NAME[name]; args=params.get('arguments',{})
        if not isinstance(args,dict): return rpc_error(id,-32602,'Tool arguments must be an object.')
        try: parsed=tool.model.model_validate(args)
        except ValidationError as e:
            # errors(include_input=False) avoids reflecting sensitive request text.
            issues=[{'field':'.'.join(map(str,x['loc'])),'type':x['type']} for x in e.errors(include_input=False,include_context=False)]
            return rpc_result(id,tool_result(fail('INVALID_TOOL_INPUT',{'validation_errors':issues})))
        scopes=set(tool.scopes)
        if name=='rag_search' and parsed.caseId: scopes.add('aidlex:read')
        if getattr(parsed,'execution',None)=='server': scopes.add('aidlex:analyze')
        if scopes and (not principal or not scopes<=principal.scopes):
            meta={'mcp/www_authenticate':[verifier.challenge(' '.join(sorted(scopes)),'insufficient_scope' if principal else None)]} if settings.auth_mode=='oauth' else None
            return rpc_result(id,tool_result(fail('AUTHENTICATION_REQUIRED: link an account with the required Aidlex permissions.'),meta))
        try:
            result=await service.execute(name,parsed,principal.owner if principal else None)
            # Make all tool outputs conform to the original Aidlex envelope.
            from .service import validate
            validate('McpToolResult.schema',result)
            return rpc_result(id,tool_result(result))
        except ValueError as e:
            return rpc_result(id,tool_result(fail(str(e)[:500])))
        except Exception as e:
            from .ai import ModelFailure
            if isinstance(e,ModelFailure): return rpc_result(id,tool_result(fail(str(e))))
            # No exception string, token, parameters, database URL or document content.
            log.error('tool_failed tool=%s exception_type=%s',name,type(e).__name__)
            return rpc_result(id,tool_result(fail('TOOL_FAILED: the operation did not complete. Check sanitized server logs; do not assume persistence or analysis succeeded.')))
    return app
