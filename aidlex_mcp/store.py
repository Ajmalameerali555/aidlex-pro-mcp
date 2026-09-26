"""Scoped persistence, portable between SQLite and a private PostgreSQL schema."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import time
import uuid
from sqlalchemy import (create_engine, MetaData, Table, Column, String, Integer, Text, JSON,
                        UniqueConstraint, select, update, delete, text, event)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.schema import CreateSchema
from .text import split_pages


def utcnow():
    return datetime.now(timezone.utc).isoformat()

def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True).encode()).hexdigest()

class Store:
    def __init__(self, url: str, schema: str = 'aidlex_mcp'):
        if url.startswith('postgres://'): url='postgresql+psycopg://'+url[len('postgres://'):]
        if url.startswith('postgresql://'): url='postgresql+psycopg://'+url[len('postgresql://'):]
        is_sqlite=url.startswith('sqlite:')
        if is_sqlite and url.startswith('sqlite:///') and ':memory:' not in url:
            Path(url[len('sqlite:///'):]).expanduser().resolve().parent.mkdir(parents=True,exist_ok=True)
        self.engine=create_engine(url,pool_pre_ping=True,connect_args={'check_same_thread':False,'timeout':20} if is_sqlite else {})
        self.is_sqlite=is_sqlite
        if is_sqlite:
            @event.listens_for(self.engine,'connect')
            def configure(dbapi_connection, connection_record):
                dbapi_connection.execute('PRAGMA journal_mode=WAL')
                dbapi_connection.execute('PRAGMA foreign_keys=ON')
                dbapi_connection.execute('PRAGMA busy_timeout=20000')
        self.meta=MetaData(schema=None if is_sqlite else schema)
        self.cases=Table('cases',self.meta,Column('owner',String(128),primary_key=True),Column('case_id',String(128),primary_key=True),Column('created_at',String(40)),Column('title',Text))
        self.docs=Table('documents',self.meta,Column('id',String(40),primary_key=True),Column('owner',String(128),nullable=False,index=True),Column('case_id',String(128),nullable=False,index=True),Column('title',Text),Column('pages',JSON),Column('metadata',JSON),Column('content_hash',String(64)),Column('created_at',String(40)),UniqueConstraint('owner','case_id','content_hash',name='uq_doc_content'))
        self.sources=Table('legal_sources',self.meta,Column('id',String(40),primary_key=True),Column('title',Text),Column('url',Text),Column('text',Text),Column('metadata',JSON),Column('content_hash',String(64),unique=True),Column('created_at',String(40)))
        self.chunks=Table('chunks',self.meta,Column('id',String(40),primary_key=True),Column('owner',String(128),index=True),Column('case_id',String(128),index=True),Column('kind',String(30),index=True),Column('source_id',String(40),index=True),Column('title',Text),Column('text',Text),Column('page_number',Integer),Column('start',Integer),Column('end',Integer),Column('metadata',JSON),Column('embedding',JSON),Column('embedding_model',String(100)))
        self.memory=Table('case_memory',self.meta,Column('owner',String(128),primary_key=True),Column('case_id',String(128),primary_key=True),Column('revision',Integer,nullable=False),Column('payload',JSON),Column('updated_at',String(40)))
        self.audit=Table('audit_events',self.meta,Column('id',String(40),primary_key=True),Column('owner',String(128),index=True),Column('case_id',String(128),index=True),Column('action',String(80)),Column('metadata',JSON),Column('created_at',String(40)))
        self.limits=Table('rate_limits',self.meta,Column('key',String(200),primary_key=True),Column('window',Integer,primary_key=True),Column('count',Integer,nullable=False))

    def initialize(self):
        if not self.is_sqlite:
            with self.engine.begin() as c:
                c.execute(CreateSchema(self.meta.schema,if_not_exists=True))
                c.execute(text(f'REVOKE ALL ON SCHEMA "{self.meta.schema}" FROM PUBLIC'))
        self.meta.create_all(self.engine)

    def ping(self):
        with self.engine.connect() as c: return c.execute(select(1)).scalar_one()==1

    def _ensure_case(self,c,owner,case_id,title=''):
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        ins=sqlite_insert if self.is_sqlite else pg_insert
        c.execute(ins(self.cases).values(owner=owner,case_id=case_id,title=title,created_at=utcnow()).on_conflict_do_nothing(index_elements=['owner','case_id']))

    def _audit(self,c,owner,case_id,action,metadata):
        c.execute(self.audit.insert().values(id=uuid.uuid4().hex,owner=owner,case_id=case_id,action=action,metadata=metadata,created_at=utcnow()))

    def ingest_document(self,owner,case_id,title,pages,metadata,embeddings=None,embedding_model=''):
        h=digest({'title':title,'pages':pages}); doc_id=uuid.uuid4().hex
        chunks=split_pages(pages)
        try:
            with self.engine.begin() as c:
                previous=c.execute(select(self.docs.c.id).where(self.docs.c.owner==owner,self.docs.c.case_id==case_id,self.docs.c.content_hash==h)).scalar_one_or_none()
                if previous: return {'document_id':previous,'deduplicated':True,'chunks':len(chunks)}
                self._ensure_case(c,owner,case_id,title)
                c.execute(self.docs.insert().values(id=doc_id,owner=owner,case_id=case_id,title=title,pages=pages,metadata=metadata,content_hash=h,created_at=utcnow()))
                for i,ch in enumerate(chunks):
                    c.execute(self.chunks.insert().values(id=uuid.uuid4().hex,owner=owner,case_id=case_id,kind='case_document',source_id=doc_id,title=title,**ch,metadata=metadata,embedding=(embeddings[i] if embeddings else None),embedding_model=embedding_model))
                self._audit(c,owner,case_id,'ingest_document',{'document_id':doc_id,'hash':h,'pages':len(pages),'chunks':len(chunks)})
        except IntegrityError:
            with self.engine.connect() as c:
                found=c.execute(select(self.docs.c.id).where(self.docs.c.owner==owner,self.docs.c.case_id==case_id,self.docs.c.content_hash==h)).scalar_one_or_none()
                if not found: raise
                return {'document_id':found,'deduplicated':True,'chunks':len(chunks)}
        return {'document_id':doc_id,'deduplicated':False,'chunks':len(chunks),'content_hash':h,'pages':len(pages)}

    def get_document(self,owner,document_id):
        with self.engine.connect() as c:
            row=c.execute(select(self.docs).where(self.docs.c.owner==owner,self.docs.c.id==document_id)).mappings().first()
            return dict(row) if row else None

    def case_documents(self,owner,case_id):
        with self.engine.connect() as c:
            return [dict(r) for r in c.execute(select(self.docs).where(self.docs.c.owner==owner,self.docs.c.case_id==case_id).order_by(self.docs.c.created_at,self.docs.c.id)).mappings()]

    def list_cases(self,owner,limit=50,offset=0):
        with self.engine.connect() as c:
            return [dict(r) for r in c.execute(select(self.cases.c.case_id,self.cases.c.title,self.cases.c.created_at).where(self.cases.c.owner==owner).order_by(self.cases.c.created_at.desc(),self.cases.c.case_id).limit(limit).offset(offset)).mappings()]

    def add_source(self,title,url,body,metadata,owner='system'):
        h=digest({'url':url,'body':body,'verification_status':metadata.get('verification_status')}); source_id=uuid.uuid4().hex
        chunks=split_pages([{'page_number':None,'text':body}])
        with self.engine.begin() as c:
            previous=c.execute(select(self.sources.c.id).where(self.sources.c.content_hash==h)).scalar_one_or_none()
            if previous:
                # Re-fetching identical official content refreshes provenance, not legal applicability.
                if metadata.get('verification_status')=='official_retrieved':
                    c.execute(update(self.sources).where(self.sources.c.id==previous).values(metadata=metadata))
                    c.execute(update(self.chunks).where(self.chunks.c.source_id==previous,self.chunks.c.kind=='legal_source').values(metadata=metadata))
                return {'source_id':previous,'deduplicated':True,'chunks':len(chunks)}
            c.execute(self.sources.insert().values(id=source_id,title=title,url=url,text=body,metadata=metadata,content_hash=h,created_at=utcnow()))
            for ch in chunks:
                c.execute(self.chunks.insert().values(id=uuid.uuid4().hex,owner=None,case_id=None,kind='legal_source',source_id=source_id,title=title,**ch,metadata=metadata,embedding=None,embedding_model=''))
            self._audit(c,owner,None,'ingest_legal_source',{'source_id':source_id,'hash':h,'status':metadata.get('verification_status')})
        return {'source_id':source_id,'deduplicated':False,'chunks':len(chunks),'content_hash':h}

    def source_by_id(self,source_id):
        with self.engine.connect() as c:
            r=c.execute(select(self.sources).where(self.sources.c.id==source_id)).mappings().first()
            return dict(r) if r else None

    def candidate_chunks(self,owner,case_id,include_legal=True,include_case=True,limit=10000):
        from sqlalchemy import or_, and_
        conditions=[]
        if include_legal: conditions.append(self.chunks.c.kind=='legal_source')
        if owner and case_id and include_case:
            conditions.append(and_(self.chunks.c.owner==owner,self.chunks.c.case_id==case_id,self.chunks.c.kind=='case_document'))
        if not conditions: return [],False
        with self.engine.connect() as c:
            rows=[dict(r) for r in c.execute(select(self.chunks).where(or_(*conditions)).order_by(self.chunks.c.id).limit(limit+1)).mappings()]
        return rows[:limit],len(rows)>limit

    def get_memory(self,owner,case_id):
        with self.engine.connect() as c:
            row=c.execute(select(self.memory).where(self.memory.c.owner==owner,self.memory.c.case_id==case_id)).mappings().first()
        if row: return {'revision':row['revision'],'memory':row['payload'],'updated_at':row['updated_at']}
        return {'revision':0,'memory':{'memories':[]},'updated_at':None}

    def save_memory(self,owner,case_id,payload,expected_revision):
        try:
            with self.engine.begin() as c:
                self._ensure_case(c,owner,case_id)
                if expected_revision==0:
                    c.execute(self.memory.insert().values(owner=owner,case_id=case_id,revision=1,payload=payload,updated_at=utcnow()))
                else:
                    r=c.execute(update(self.memory).where(self.memory.c.owner==owner,self.memory.c.case_id==case_id,self.memory.c.revision==expected_revision).values(revision=expected_revision+1,payload=payload,updated_at=utcnow()))
                    if r.rowcount!=1: raise ValueError('MEMORY_CONFLICT: read current memory and explicitly merge before retrying.')
                self._audit(c,owner,case_id,'replace_confirmed_memory',{'revision':expected_revision+1,'items':len(payload['memories'])})
        except IntegrityError as e:
            raise ValueError('MEMORY_CONFLICT: read current memory and explicitly merge before retrying.') from e
        return {'revision':expected_revision+1,'memory':payload}

    def delete_case(self,owner,case_id):
        with self.engine.begin() as c:
            c.execute(delete(self.chunks).where(self.chunks.c.owner==owner,self.chunks.c.case_id==case_id))
            n=c.execute(delete(self.docs).where(self.docs.c.owner==owner,self.docs.c.case_id==case_id)).rowcount
            c.execute(delete(self.memory).where(self.memory.c.owner==owner,self.memory.c.case_id==case_id))
            c.execute(delete(self.audit).where(self.audit.c.owner==owner,self.audit.c.case_id==case_id))
            c.execute(delete(self.cases).where(self.cases.c.owner==owner,self.cases.c.case_id==case_id))
        return {'deleted_documents':n,'deleted_case_id':case_id,'backup_warning':'Copies in database backups are governed by the operator retention schedule.'}

    def consume_limit(self,key,limit,now=None):
        now=int(time.time() if now is None else now); window=now//60
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        ins=sqlite_insert if self.is_sqlite else pg_insert
        with self.engine.begin() as c:
            stmt=ins(self.limits).values(key=key,window=window,count=1)
            stmt=stmt.on_conflict_do_update(index_elements=['key','window'],set_={'count':self.limits.c.count+1}).returning(self.limits.c.count)
            count=c.execute(stmt).scalar_one()
            c.execute(delete(self.limits).where(self.limits.c.window<window-2))
        return count<=limit
