"""Optional paid inference. Default host mode never calls an external model."""
import asyncio
import copy
import json
import math
import httpx
from jsonschema import Draft202012Validator, ValidationError as SchemaValidationError

class ModelFailure(Exception): pass

def strict_schema(schema):
    result=copy.deepcopy(schema)
    def walk(node):
        if isinstance(node,dict):
            node.pop('$schema',None); node.pop('default',None)
            if node.get('type')=='object' or 'properties' in node:
                node['additionalProperties']=False
                node['required']=list(node.get('properties',{}))
            for value in node.values(): walk(value)
        elif isinstance(node,list):
            for value in node: walk(value)
    walk(result)
    return result

class AIClient:
    def __init__(self,settings):
        self.settings=settings
        self.semaphore=asyncio.Semaphore(2)

    def configured(self):
        return bool(self.settings.openai_api_key.get_secret_value() and self.settings.model)

    async def _post(self,path,payload,timeout=None):
        key=self.settings.openai_api_key.get_secret_value()
        if not key: raise ModelFailure('OPENAI_API_KEY is not configured. Use host execution.')
        async with self.semaphore:
            try:
                async with httpx.AsyncClient(timeout=timeout or self.settings.model_timeout_seconds,trust_env=False) as client:
                    response=await client.post('https://api.openai.com/v1/'+path,headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},json=payload)
                    if response.status_code>=400:
                        raise ModelFailure(f'Model provider returned HTTP {response.status_code}; check model access, billing and configuration. No successful analysis is claimed.')
                    if len(response.content)>4000000: raise ModelFailure('Model response exceeded safety limit.')
                    return response.json()
            except (httpx.HTTPError,ValueError) as e:
                raise ModelFailure('Model request failed or timed out. No result was fabricated.') from e

    async def structured(self,instructions,payload,schema,name='AidlexReport'):
        if not self.configured(): raise ModelFailure('Set OPENAI_API_KEY and AIDLEX_MODEL for server execution, or use execution=host.')
        data={'model':self.settings.model,'store':False,'instructions':instructions,
              'input':json.dumps(payload,ensure_ascii=False),
              'text':{'format':{'type':'json_schema','name':name,'strict':True,'schema':strict_schema(schema)}},
              'max_output_tokens':self.settings.model_max_output_tokens}
        if self.settings.reasoning_effort!='none': data['reasoning']={'effort':self.settings.reasoning_effort}
        response=await self._post('responses',data)
        if response.get('status') not in (None,'completed'): raise ModelFailure('Model output was incomplete; increase the output budget or narrow the case context.')
        texts=[]
        for item in response.get('output',[]):
            for part in item.get('content',[]):
                if part.get('type')=='refusal': raise ModelFailure('Model did not produce the requested legal report.')
                if part.get('type')=='output_text': texts.append(part.get('text',''))
        try:
            report=json.loads(''.join(texts),parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Non-finite model output')))
            Draft202012Validator(schema).validate(report)
        except (ValueError,SchemaValidationError,RecursionError) as e:
            raise ModelFailure('Model returned an invalid structured report; do not rely on it.') from e
        return report

    async def embed(self,texts):
        if not texts: return []
        vectors=[]
        # Character-bounded batches keep individual inputs below model token limits.
        for offset in range(0,len(texts),64):
            batch=texts[offset:offset+64]
            r=await self._post('embeddings',{'model':self.settings.embedding_model,'input':batch,'encoding_format':'float'},timeout=30)
            rows=sorted(r.get('data',[]),key=lambda x:x.get('index',-1))
            if [x.get('index') for x in rows]!=list(range(len(batch))): raise ModelFailure('Embedding response did not match submitted chunks.')
            for item in rows:
                vec=item.get('embedding')
                if not isinstance(vec,list) or not vec or len(vec)>10000 or any(not isinstance(v,(int,float)) or not math.isfinite(v) for v in vec): raise ModelFailure('Invalid embedding vector.')
                vectors.append(vec)
        return vectors
