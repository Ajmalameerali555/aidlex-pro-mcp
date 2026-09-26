#!/usr/bin/env python3
"""Create a real local configuration without putting secrets into shell history."""
import argparse
import getpass
import json
import os
from pathlib import Path
import secrets
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parent.parent

def required(prompt):
    value=input(prompt).strip()
    if not value: raise SystemExit('A value is required. No configuration was written.')
    return value

def write_env(path,values):
    # JSON strings are a supported quoted form for dotenv values used here.
    body='\n'.join(k+'='+json.dumps(str(v),ensure_ascii=False) for k,v in values.items())+'\n'
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as stream: stream.write(body)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--local',action='store_true',help='Generate a local developer-bearer setup automatically.')
    parser.add_argument('--public-local',action='store_true',help='Generate a local public read-only setup automatically.')
    args=parser.parse_args()
    path=ROOT/'.env'
    if path.exists(): raise SystemExit('.env already exists. Preserve it; edit intentionally or rename it before configuring.')
    values={'AIDLEX_ENVIRONMENT':'development','AIDLEX_AUTH_MODE':'public','AIDLEX_PUBLIC_BASE_URL':'http://localhost:8000',
            'AIDLEX_DATABASE_URL':'sqlite:///./data/aidlex.db','AIDLEX_DATABASE_SCHEMA':'aidlex_mcp','AIDLEX_AUTO_MIGRATE':'true',
            'AIDLEX_RATE_LIMIT_PER_MINUTE':'120','AIDLEX_ANALYSIS_LIMIT_PER_MINUTE':'3','AIDLEX_MAX_CONTEXT_CHARS':'50000',
            'AIDLEX_EMBEDDINGS_ENABLED':'false','AIDLEX_EMBEDDING_MODEL':'text-embedding-3-small',
            'AIDLEX_REASONING_EFFORT':'high','AIDLEX_MODEL_TIMEOUT_SECONDS':'35','AIDLEX_MODEL_MAX_OUTPUT_TOKENS':'7000'}
    if args.local:
        values['AIDLEX_AUTH_MODE']='bearer'; values['AIDLEX_BEARER_TOKEN']=secrets.token_urlsafe(48)
    elif not args.public_local:
        mode=required('Remote mode [public / oauth]: ')
        if mode not in {'public','oauth'}: raise SystemExit('Use public or oauth for ChatGPT. Static bearer is only a developer profile.')
        base=required('Public HTTPS origin, without /mcp: ').rstrip('/')
        p=urlsplit(base)
        if p.scheme!='https' or not p.hostname or p.path or p.query or p.fragment or p.username or p.password:
            raise SystemExit('A valid HTTPS origin is required.')
        values.update(AIDLEX_ENVIRONMENT='production',AIDLEX_AUTH_MODE=mode,AIDLEX_PUBLIC_BASE_URL=base,AIDLEX_DOMAIN=p.hostname)
        if mode=='oauth':
            values['AIDLEX_OAUTH_ISSUER']=required('Authorization-provider issuer (exactly as in its discovery document): ')
            values['AIDLEX_OAUTH_JWKS_URL']=required('Authorization-provider JWKS HTTPS URL: ')
            values['AIDLEX_OAUTH_AUDIENCE']=base+'/mcp'
        platform=required('Hosting [droplet / appplatform]: ')
        if platform not in {'droplet','appplatform'}: raise SystemExit('Unknown hosting choice.')
        if platform=='appplatform' and mode=='oauth':
            db=getpass.getpass('Private PostgreSQL connection URL (hidden): ').strip()
            if not db.startswith(('postgres://','postgresql://','postgresql+psycopg://')): raise SystemExit('App Platform private mode requires PostgreSQL, not an ephemeral SQLite file.')
            values['AIDLEX_DATABASE_URL']=db
        elif platform=='droplet':
            values['AIDLEX_ACME_EMAIL']=required('Certificate renewal email: ')
        if mode=='oauth' and input('Enable optional paid server-side model execution? [y/N]: ').lower()=='y':
            values['OPENAI_API_KEY']=getpass.getpass('OpenAI API key (hidden, stored only in local .env): ').strip()
            if not values['OPENAI_API_KEY']: raise SystemExit('No API key supplied. Run again without server inference.')
            values['AIDLEX_MODEL']=required('Exact Responses API model ID enabled in your account: ')
            if input('Also enable embeddings for new document ingestion? [y/N]: ').lower()=='y': values['AIDLEX_EMBEDDINGS_ENABLED']='true'
    write_env(path,values)
    print('Created .env with owner-only permissions. Never commit or paste it into chat.')
    print('MCP endpoint after the server is running:',values['AIDLEX_PUBLIC_BASE_URL']+'/mcp')
    if values['AIDLEX_AUTH_MODE']=='bearer': print('Developer token saved in .env. smoke_test.py loads it locally. This auth mode is not for ChatGPT public submission.')

if __name__=='__main__': main()
