"""Search normalization is NEVER written back over original evidence."""
from collections import Counter
import math
import re
import unicodedata

AR_MAP = str.maketrans('أإآٱى', 'ااااي')
DIGITS = str.maketrans('٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹','01234567890123456789')
LEXICON = {
    'cheque':['شيك','الشيك','شيكات','الشيكات'],
    'payment':['سداد','السداد','دفع','الدفع'],
    'rent':['ايجار','الايجار','اجرة','الاجرة'],
    'appeal':['استئناف','الاستئناف','طعن','الطعن'],
    'execution':['تنفيذ','التنفيذ'],
    'evidence':['اثبات','الاثبات','دليل','الدليل'],
    'contract':['عقد','العقد'],
    'labour':['عمل','العمل','عمال','العمال'],
}

def normalize(text: str) -> str:
    text = unicodedata.normalize('NFKC', text).translate(AR_MAP).translate(DIGITS).lower()
    text = re.sub(r'[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed\u0640]', '', text)
    return ' '.join(text.split())

def tokens(text: str, expand: bool = False) -> list[str]:
    result=re.findall(r'[^\W_]+', normalize(text), re.UNICODE)
    if expand:
        additions=[]
        for word in result:
            for en, ar in LEXICON.items():
                if word==en or word in ar: additions.extend([en]+ar)
        result+=additions
    return result

def split_pages(pages: list[dict], size: int = 1200, overlap: int = 160) -> list[dict]:
    if size <= overlap or overlap < 0: raise ValueError('Require size > overlap >= 0.')
    result=[]
    for page in pages:
        raw=page['text']; start=0
        while start < len(raw):
            end=min(len(raw),start+size)
            if raw[start:end].strip():
                result.append({'page_number':page['page_number'], 'text':raw[start:end], 'start':start, 'end':end})
            if end==len(raw): break
            start=end-overlap
    return result

def bm25_search(query: str, items: list[dict], limit: int = 20) -> list[dict]:
    if not items: return []
    q=set(tokens(query,expand=True)); docs=[Counter(tokens(i['text'])) for i in items]
    if not q: return []
    n=len(docs); avg=sum(sum(d.values()) for d in docs)/n or 1
    df={t:sum(1 for d in docs if t in d) for t in q}
    ranked=[]
    for item,d in zip(items,docs):
        length=sum(d.values()); score=0.0
        for t in q:
            freq=d.get(t,0)
            if freq:
                idf=math.log(1+(n-df[t]+0.5)/(df[t]+0.5))
                score+=idf*freq*2.5/(freq+1.5*(0.25+0.75*length/avg))
        if score>0: ranked.append({**item,'retrieval_score':round(score,8)})
    return sorted(ranked,key=lambda i:(-i['retrieval_score'],i['id']))[:limit]

def cosine(a: list[float], b: list[float]) -> float:
    if len(a)!=len(b) or not a: return 0.0
    den=math.sqrt(sum(x*x for x in a)*sum(x*x for x in b))
    return sum(x*y for x,y in zip(a,b))/den if den else 0.0

def fuse(lexical: list[dict], semantic: list[dict], limit: int) -> list[dict]:
    scores={}; by_id={}
    for ranking in [lexical,semantic]:
        for rank,item in enumerate(ranking,1):
            scores[item['id']]=scores.get(item['id'],0)+1/(60+rank)
            by_id[item['id']]=item
    return [{**by_id[k],'retrieval_score':round(v,8)} for k,v in sorted(scores.items(), key=lambda p:(-p[1],p[0]))[:limit]]
