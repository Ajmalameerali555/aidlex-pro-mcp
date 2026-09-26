"""Evidence provenance: official-domain origin is NOT a legal applicability finding."""
from datetime import datetime, timezone
import asyncio
import hashlib
import ipaddress
import json
import socket
from urllib.parse import urlsplit, urljoin, urlunsplit
import httpx
from bs4 import BeautifulSoup
from .config import ROOT


def registry():
    return json.loads((ROOT/'knowledge/uae_official_source_registry.json').read_text())

def allowed_source_hosts():
    hosts=set()
    for source in registry()['official_sources']:
        host=urlsplit(source['url']).hostname
        hosts.add(host)
        if host.startswith('www.'): hosts.add(host[4:])
        else: hosts.add('www.'+host)
    return hosts

def validate_source_url(url, allowed_hosts=None):
    if not isinstance(url,str) or len(url)>2048 or any(ord(c)<32 for c in url) or '\\' in url:
        raise ValueError('Invalid source URL.')
    p=urlsplit(url)
    try: port=p.port
    except ValueError as e: raise ValueError('Invalid port.') from e
    allowed=allowed_hosts if allowed_hosts is not None else allowed_source_hosts()
    if p.scheme!='https' or p.hostname not in allowed or port not in (None,443) or p.username or p.password:
        raise ValueError('Source retrieval is restricted to exact HTTPS hosts in the official registry.')
    try: ipaddress.ip_address(p.hostname)
    except ValueError: pass
    else: raise ValueError('IP-literal sources are prohibited.')
    return urlunsplit((p.scheme,p.netloc,p.path or '/',p.query,''))

async def check_public_dns(host):
    addresses=await asyncio.get_running_loop().getaddrinfo(host,443,type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(row[4][0]).is_global for row in addresses):
        raise ValueError('Source host did not resolve exclusively to public IP addresses.')

async def fetch_official(url, max_bytes=2000000, client=None):
    """No caller-controlled headers, cookies, proxy, or arbitrary remote domains."""
    current=validate_source_url(url); own=client is None
    if own: client=httpx.AsyncClient(timeout=20,follow_redirects=False,trust_env=False)
    try:
        for _ in range(4):
            await check_public_dns(urlsplit(current).hostname)
            async with client.stream('GET',current,headers={'Accept':'text/html,text/plain,application/json','User-Agent':'AidlexPro-MCP/1.0 (official-source-retrieval)'}) as response:
                if response.status_code in (301,302,303,307,308):
                    location=response.headers.get('location')
                    if not location: raise ValueError('Official source redirect lacks a location.')
                    current=validate_source_url(urljoin(current,location)); continue
                response.raise_for_status()
                media=response.headers.get('content-type','').split(';')[0].strip()
                if media not in {'text/html','text/plain','application/json','application/xhtml+xml'}:
                    raise ValueError('This tool fetches HTML/text/JSON only. Extract PDFs with page provenance in the document host.')
                data=bytearray()
                async for part in response.aiter_bytes():
                    data.extend(part)
                    if len(data)>max_bytes: raise ValueError('Official source exceeds retrieval size limit.')
            raw=bytes(data)
            body=raw.decode('utf-8-sig',errors='replace')
            if body.count('\ufffd') > max(3,len(body)//1000):
                raise ValueError('Source encoding is unreliable; use a verified extracted text version.')
            title=''
            if 'html' in media:
                soup=BeautifulSoup(body,'html.parser')
                if soup.title: title=soup.title.get_text(' ',strip=True)
                for tag in soup(['script','style','nav','footer','header','form','noscript']): tag.decompose()
                content=soup.find('main') or soup.find('article') or soup
                body=content.get_text('\n',strip=True)
            if len(body.strip())<100: raise ValueError('Official page returned insufficient text; may require JavaScript or login.')
            return {'title':title,'text':body,'url':current,'retrieved_at':datetime.now(timezone.utc).isoformat(),'raw_sha256':hashlib.sha256(raw).hexdigest(),'text_sha256':hashlib.sha256(body.encode()).hexdigest(),'verification_status':'official_retrieved','legal_effect_verified':False}
        raise ValueError('Too many source redirects.')
    finally:
        if own: await client.aclose()
