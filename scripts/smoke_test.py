#!/usr/bin/env python3
"""Read-only live MCP handshake and tool discovery probe. No write actions."""
import argparse
import json
import os
from pathlib import Path
import urllib.request
import urllib.error

ROOT=Path(__file__).resolve().parent.parent

def config():
    values={}
    path=ROOT/'.env'
    if path.exists():
        for line in path.read_text().splitlines():
            if '=' not in line or line.lstrip().startswith('#'): continue
            k,v=line.split('=',1);v=v.strip()
            try: values[k]=json.loads(v)
            except ValueError: values[k]=v.strip("'\"")
    return values

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--url',default='http://127.0.0.1:8000/mcp');a=p.parse_args()
    values=config()
    token=os.environ.get('AIDLEX_TEST_ACCESS_TOKEN','')
    if not token and values.get('AIDLEX_AUTH_MODE')=='bearer': token=values.get('AIDLEX_BEARER_TOKEN','')
    headers={'Content-Type':'application/json','Accept':'application/json, text/event-stream','MCP-Protocol-Version':'2025-11-25'}
    if token: headers['Authorization']='Bearer '+token
    def rpc(method,params=None,id=1):
        req=urllib.request.Request(a.url,data=json.dumps({'jsonrpc':'2.0','id':id,'method':method,'params':params or {}}).encode(),headers=headers,method='POST')
        with urllib.request.urlopen(req,timeout=30) as response: data=json.load(response)
        if 'error' in data: raise RuntimeError(json.dumps(data['error']))
        return data['result']
    init=rpc('initialize',{'protocolVersion':'2025-11-25','clientInfo':{'name':'AidlexSmoke','version':'1.0'},'capabilities':{}})
    tools=rpc('tools/list')['tools']
    status=rpc('tools/call',{'name':'aidlex_server_status','arguments':{}})['structuredContent']
    if not status['ok']: raise SystemExit('Status tool failed.')
    print(json.dumps({'initialize':'PASS','protocol':init['protocolVersion'],'tools':len(tools),'tool_names':[t['name'] for t in tools],'server_status':status['data'],'writes_performed':False},indent=2))

if __name__=='__main__':
    try: main()
    except (urllib.error.URLError,RuntimeError) as e: raise SystemExit('SMOKE TEST FAILED: '+str(e))
