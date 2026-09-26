#!/usr/bin/env python3
"""Validate configuration/provider metadata without displaying secrets."""
import asyncio
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from aidlex_mcp.config import Settings
from aidlex_mcp.store import Store
import httpx

async def main():
    s=Settings(); checks={'configuration':'PASS','auth_mode':s.auth_mode,'server_ai_configured':bool(s.model and s.openai_api_key.get_secret_value())}
    try:
        store=Store(s.database_url.get_secret_value(),s.database_schema)
        checks['database_connection']='PASS' if store.ping() else 'FAIL'
        store.engine.dispose()
    except Exception as e: checks['database_connection']='FAIL: '+type(e).__name__
    if s.auth_mode=='oauth':
        issuer=s.oauth_issuer
        parts=urlsplit(issuer)
        urls=[issuer.rstrip('/')+'/.well-known/openid-configuration',f'{parts.scheme}://{parts.netloc}/.well-known/oauth-authorization-server'+parts.path.rstrip('/')]
        metadata=None
        async with httpx.AsyncClient(timeout=15,follow_redirects=False,trust_env=False) as client:
            for url in dict.fromkeys(urls):
                try:
                    r=await client.get(url)
                    if r.status_code==200: metadata=r.json();break
                except (httpx.HTTPError,ValueError): continue
        if not metadata: checks['provider_discovery']='FAIL: no accessible OAuth/OIDC metadata'
        else:
            checks['provider_discovery']='PASS'
            checks['issuer_exact_match']='PASS' if metadata.get('issuer')==issuer else 'FAIL'
            checks['pkce_s256']='PASS' if 'S256' in metadata.get('code_challenge_methods_supported',[]) else 'FAIL'
            checks['authorization_endpoint_https']='PASS' if metadata.get('authorization_endpoint','').startswith('https://') else 'FAIL'
            checks['token_endpoint_https']='PASS' if metadata.get('token_endpoint','').startswith('https://') else 'FAIL'
            checks['jwks_matches_provider']='PASS' if metadata.get('jwks_uri')==s.oauth_jwks_url else 'CHECK_MANUALLY'
            checks['resource_audience']='MUST TEST: issued access token aud must equal '+s.oauth_audience
            checks['callback']='Copy the exact callback URI from ChatGPT into the provider allowlist; do not use a wildcard.'
    print(json.dumps(checks,indent=2))
    if any(str(v).startswith('FAIL') for v in checks.values()): raise SystemExit(1)

if __name__=='__main__': asyncio.run(main())
