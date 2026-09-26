#!/usr/bin/env python3
"""Generate a valid DigitalOcean app spec from actual repository/config values.

The generated file may include secrets. It is mode 0600 and gitignored.
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from dotenv import dotenv_values

def make_spec(repo,region,branch='main',size='apps-s-1vcpu-1gb-fixed',values=None):
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repo): raise ValueError('Use the actual GitHub owner/repository name.')
    if not re.fullmatch(r'[a-z0-9-]{2,30}',region): raise ValueError('Supply a valid DigitalOcean region slug.')
    values=dict(values or {})
    mode=values.get('AIDLEX_AUTH_MODE','public')
    if mode not in ('public','oauth'): raise ValueError('Public ChatGPT hosting supports public or OAuth profiles, not static bearer.')
    if mode=='oauth':
        for key in ('AIDLEX_OAUTH_ISSUER','AIDLEX_OAUTH_JWKS_URL','AIDLEX_DATABASE_URL'):
            if not values.get(key): raise ValueError(key+' must be configured before generating a private deployment.')
        if not values['AIDLEX_DATABASE_URL'].startswith(('postgres://','postgresql://','postgresql+psycopg://')): raise ValueError('Private App Platform deployments require PostgreSQL.')
    values['AIDLEX_ENVIRONMENT']='production'
    values['AIDLEX_AUTH_MODE']=mode
    # DO supplies the app URL at runtime, avoiding a guessed deployment address.
    base=values.get('AIDLEX_PUBLIC_BASE_URL','')
    if not base.startswith('https://'): values['AIDLEX_PUBLIC_BASE_URL']='${APP_URL}'
    if mode=='oauth': values['AIDLEX_OAUTH_AUDIENCE']=values['AIDLEX_PUBLIC_BASE_URL'].rstrip('/')+'/mcp'
    secret_keys={'AIDLEX_DATABASE_URL','OPENAI_API_KEY'}
    ignored={'AIDLEX_BEARER_TOKEN','AIDLEX_DOMAIN','AIDLEX_ACME_EMAIL'}
    envs=[]
    for key,value in sorted(values.items()):
        if key in ignored or value is None or not (key.startswith('AIDLEX_') or key=='OPENAI_API_KEY'): continue
        envs.append({'key':key,'scope':'RUN_TIME','type':'SECRET' if key in secret_keys else 'GENERAL','value':str(value)})
    envs.append({'key':'PORT','scope':'RUN_TIME','type':'GENERAL','value':'8000'})
    return {'name':'aidlex-pro-mcp','region':region,'ingress':{'rules':[{'match':{'path':{'prefix':'/'}},'component':{'name':'mcp','preserve_path_prefix':True}}]},'services':[{'name':'mcp','github':{'repo':repo,'branch':branch,'deploy_on_push':False},'source_dir':'.','dockerfile_path':'Dockerfile','http_port':8000,'instance_count':1,'instance_size_slug':size,'envs':envs,'health_check':{'http_path':'/readyz','initial_delay_seconds':30,'period_seconds':30,'timeout_seconds':5,'success_threshold':1,'failure_threshold':3}}]}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',required=True);p.add_argument('--region',required=True)
    p.add_argument('--branch',default='main');p.add_argument('--size',default='apps-s-1vcpu-1gb-fixed')
    p.add_argument('--out',default=str(ROOT/'.do/app.generated.yaml'))
    a=p.parse_args();values=dotenv_values(ROOT/'.env') if (ROOT/'.env').exists() else {}
    spec=make_spec(a.repo,a.region,a.branch,a.size,values)
    target=Path(a.out);target.parent.mkdir(parents=True,exist_ok=True)
    # JSON is a valid YAML representation accepted by the app-spec schema.
    fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    os.chmod(target,0o600)
    with os.fdopen(fd,'w') as f: json.dump(spec,f,ensure_ascii=False,indent=2)
    print('Created:',target)
    print('This generated spec may contain secrets. Do not commit it.')
    print('Review it locally, then run: doctl apps create --spec '+str(target))

if __name__=='__main__': main()
