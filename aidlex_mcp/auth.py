"""OAuth resource server only; login/PKCE/token issuance belong to a real IdP."""
import asyncio
from dataclasses import dataclass
import hashlib
import secrets
import time
import jwt
import httpx

class AuthFailure(Exception): pass

@dataclass(frozen=True)
class Principal:
    owner: str
    scopes: frozenset[str]

ALL_SCOPES=frozenset({'aidlex:read','aidlex:write','aidlex:curate','aidlex:analyze','aidlex:delete'})

class TokenVerifier:
    def __init__(self,settings):
        self.settings=settings
        self.keys={}
        self.cache_expires=0.0
        self.last_refresh=0.0
        self.lock=asyncio.Lock()

    async def _refresh(self):
        async with self.lock:
            if time.monotonic()-self.last_refresh<30: return
            self.last_refresh=time.monotonic()
            try:
                async with httpx.AsyncClient(timeout=10,follow_redirects=False,trust_env=False) as c:
                    r=await c.get(self.settings.oauth_jwks_url)
                    r.raise_for_status()
                    if len(r.content)>200000: raise AuthFailure('Invalid signing-key response.')
                    jwks=r.json()
                keys={}
                for item in jwks.get('keys',[])[:30]:
                    if item.get('use','sig')!='sig' or item.get('kty') not in {'RSA','EC'}: continue
                    if item.get('alg') and item['alg'] not in self.settings.oauth_algorithms: continue
                    if isinstance(item.get('kid'),str): keys[item['kid']]=jwt.PyJWK.from_dict(item)
                if not keys: raise AuthFailure('No usable issuer signing keys.')
                self.keys=keys; self.cache_expires=time.monotonic()+900
            except (httpx.HTTPError,ValueError,jwt.PyJWTError) as e:
                raise AuthFailure('Unable to validate authentication at this time.') from e

    async def verify(self,token):
        if len(token)>16000: raise AuthFailure('Access token too large.')
        try:
            header=jwt.get_unverified_header(token)
            if header.get('alg') not in self.settings.oauth_algorithms or not isinstance(header.get('kid'),str):
                raise AuthFailure('Unsupported access-token signature.')
            if self.cache_expires<time.monotonic() or header['kid'] not in self.keys: await self._refresh()
            if self.cache_expires<time.monotonic() or header['kid'] not in self.keys: raise AuthFailure('Unknown or stale signing key.')
            key=self.keys[header['kid']]
            # Pin key type to algorithm; never accept HS* or alg=none.
            claims=jwt.decode(token,key.key,algorithms=self.settings.oauth_algorithms,audience=self.settings.oauth_audience,issuer=self.settings.oauth_issuer,options={'require':['exp','iss','aud','sub','iat']},leeway=5)
            subject=claims['sub']
            if not isinstance(subject,str) or not subject.strip() or len(subject)>512: raise AuthFailure('Missing authenticated user identity.')
            if self.settings.allowed_subjects and subject not in self.settings.allowed_subjects: raise AuthFailure('This account is not enabled for Aidlex.')
            scope=claims.get('scope','')
            if not isinstance(scope,str): raise AuthFailure('Malformed scopes.')
            scopes=set(scope.split())
            scp=claims.get('scp',[])
            if isinstance(scp,list) and all(isinstance(v,str) for v in scp): scopes.update(scp)
            owner=hashlib.sha256((claims['iss']+'\0'+subject).encode()).hexdigest()
            return Principal(owner,frozenset(scopes)&ALL_SCOPES)
        except (jwt.PyJWTError,ValueError,KeyError,TypeError) as e:
            raise AuthFailure('Access token is invalid, expired, or issued for another resource.') from e

    async def authenticate(self,header):
        if not header: return None
        prefix,sep,token=header.partition(' ')
        if prefix.lower()!='bearer' or not sep or not token.strip(): raise AuthFailure('Expected a Bearer access token.')
        if self.settings.auth_mode=='public': raise AuthFailure('This deployment has no private account access.')
        if self.settings.auth_mode=='bearer':
            if not secrets.compare_digest(token,self.settings.bearer_token.get_secret_value()): raise AuthFailure('Invalid developer credential.')
            return Principal('single-owner-developer',ALL_SCOPES)
        return await self.verify(token)

    def challenge(self,scope='aidlex:read',error=None):
        value=f'Bearer resource_metadata="{self.settings.public_base_url}/.well-known/oauth-protected-resource", scope="{scope}"'
        if error: value+=f', error="{error}"'
        return value
