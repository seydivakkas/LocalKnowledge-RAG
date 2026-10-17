"""Local FTS5 + BM25 search, with fail-closed source resolution.

A verified link proves managed-object SHA-256 AND extracted unit/chunk exact
text and offsets. No PDF pixel rectangle is claimed at G05 (G06+).
"""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
import sqlite3

from ..storage.db import connect

_WORDS = re.compile(r'[^\W_]+(?:_[^\W_]+)*', re.UNICODE)


class SearchError(ValueError):
    pass


def safe_query(text: str) -> str:
    if not isinstance(text,str) or not 1 <= len(text.strip()) <= 240:
        raise SearchError('Arama 1–240 karakter olmalıdır.')
    words = _WORDS.findall(text)
    if not words or len(words) > 16:
        raise SearchError('1–16 geçerli arama sözcüğü kullanın.')
    # Escape FTS operators by accepting only word tokens and quoting all terms.
    return ' AND '.join('"' + word.replace('"','""') + '"' for word in words)


@dataclass(frozen=True)
class SourceHit:
    chunk_id:int
    document_id:str
    name:str
    kind:str
    revision:int
    sha256:str
    unit_kind:str
    unit_number:int
    char_start:int
    char_end:int
    exact_quote:str
    bm25_score:float
    rank:int
    verified:bool

    @property
    def source_label(self)->str:
        where=f'sayfa {self.unit_number+1}' if self.kind=='PDF' else f'paragraf {self.unit_number+1}, karakter {self.char_start}–{self.char_end}'
        return f'{self.name} · v{self.revision} · {where}'


class SearchService:
    def __init__(self,root:Path|str):
        self.root=Path(root)
        self.db_path=self.root/'library.sqlite3'

    def stats(self)->dict[str,int]:
        with connect(self.db_path) as conn:
            docs=conn.execute('''SELECT count(*) FROM indexed_versions iv JOIN documents d ON d.id=iv.document_id
                                   WHERE d.archived=0 AND d.current_revision=iv.revision''').fetchone()[0]
            chunks=conn.execute('''SELECT count(*) FROM search_chunks c JOIN indexed_versions iv
                                ON iv.document_id=c.document_id AND iv.revision=c.revision AND iv.sha256=c.sha256
                                JOIN documents d ON d.id=c.document_id
                                WHERE d.archived=0 AND d.current_revision=c.revision''').fetchone()[0]
        return {'indexed_documents':docs,'indexed_chunks':chunks}

    def _managed_hash_ok(self,row, cache:dict[tuple[str,str],bool]):
        key=(row['document_id'],row['sha256'])
        if key in cache:return cache[key]
        rel=f"objects/{row['sha256'][:2]}/{row['sha256']}.bin"
        path=self.root / rel
        try:
            if row['object_relpath']!=rel or path.is_symlink() or not path.is_file() or path.stat().st_size!=row['byte_size']:
                cache[key]=False;return False
            sha=hashlib.sha256()
            with path.open('rb') as f:
                for block in iter(lambda:f.read(1024*1024),b''):sha.update(block)
            cache[key]=sha.hexdigest()==row['sha256']
        except OSError:
            cache[key]=False
        return cache[key]

    def _verify_row(self,row,cache):
        if not self._managed_hash_ok(row,cache):return False
        # Exact offsets must resolve back to the persisted, un-normalized G04 unit.
        start=row['char_start']-row['unit_start'];end=row['char_end']-row['unit_start']
        if start<0 or end<=start or end>len(row['unit_text']) or row['unit_text'][start:end]!=row['original_text']:
            return False
        if row['unit_kind']!=('PAGE' if row['kind']=='PDF' else 'PARAGRAPH'):
            return False
        if row['unit_number']<0 or (row['kind']=='PDF' and row['unit_number']>=row['page_count']):return False
        return True

    _SQL_BASE = '''SELECT c.id,c.document_id,c.revision,c.sha256,c.job_id,c.unit_kind,c.unit_number,
        c.char_start,c.char_end,c.original_text,d.name,d.kind,d.archived,d.current_revision,
        v.object_relpath,v.byte_size,v.page_count,j.status,
        sp.original_text AS unit_text,sp.char_start AS unit_start,
        iv.sha256 AS indexed_sha,iv.job_id AS indexed_job
      FROM search_chunks c JOIN documents d ON d.id=c.document_id
      JOIN versions v ON v.document_id=c.document_id AND v.revision=c.revision AND v.sha256=c.sha256
      JOIN index_jobs j ON j.id=c.job_id
      JOIN indexed_versions iv ON iv.document_id=c.document_id AND iv.revision=c.revision
                              AND iv.sha256=c.sha256 AND iv.job_id=c.job_id
      JOIN extracted_spans sp ON sp.job_id=c.job_id AND sp.unit_number=c.unit_number
           AND sp.unit_kind=c.unit_kind AND sp.document_id=c.document_id AND sp.revision=c.revision
      WHERE d.archived=0 AND d.current_revision=c.revision AND j.status='COMPLETED' '''

    def search(self,text:str,*,kind:str='ALL',limit:int=25,created_from:str|None=None)->tuple[SourceHit,...]:
        query=safe_query(text)
        if kind not in ('ALL','PDF','DOCX','TXT') or not 1<=limit<=50:
            raise SearchError('Geçersiz arama filtresi veya sonuç sınırı.')
        if created_from is not None and not re.fullmatch(r'\d{4}-\d{2}-\d{2}',created_from):
            raise SearchError('Tarih YYYY-AA-GG olmalıdır.')
        sql=self._SQL_BASE.replace('WHERE d.archived=', '''JOIN search_fts ON search_fts.rowid=c.id
      WHERE search_fts MATCH ? AND d.archived=''' ).replace('SELECT c.id,','SELECT bm25(search_fts) AS ranking,c.id,')
        args=[query]
        if kind!='ALL':sql+=' AND d.kind=?';args.append(kind)
        if created_from:sql+=' AND substr(d.created_at,1,10)>=?';args.append(created_from)
        sql+=' ORDER BY bm25(search_fts) ASC, c.id ASC LIMIT ?'
        # Oversample to skip corrupt sources without yielding a "verified" link.
        args.append(min(250, max(limit*4,limit)))
        with connect(self.db_path) as conn:
            rows=conn.execute(sql,args).fetchall()
            cache={}
            hits=[]
            for row in rows:
                if not self._verify_row(row,cache):continue
                # BM25 is read from query instead of fabricated confidence.
                hits.append(SourceHit(row['id'],row['document_id'],row['name'],row['kind'],row['revision'],
                    row['sha256'],row['unit_kind'],row['unit_number'],row['char_start'],row['char_end'],
                    row['original_text'],float(row['ranking']),len(hits)+1,True))
                if len(hits)>=limit:break
        return tuple(hits)

    def source_passage(self,chunk_id:int)->tuple[SourceHit,str,int,int]|None:
        """Verify current SHA + original G04 unit, then expose excerpt offsets."""
        hit=self.resolve(chunk_id)
        if hit is None:return None
        with connect(self.db_path) as conn:
            row=conn.execute('''SELECT s.original_text,s.char_start FROM search_chunks c
                JOIN extracted_spans s ON s.job_id=c.job_id AND s.unit_number=c.unit_number
                WHERE c.id=? AND s.document_id=? AND s.revision=?''',
                (chunk_id,hit.document_id,hit.revision)).fetchone()
        if not row:return None
        st=hit.char_start-row['char_start'];end=hit.char_end-row['char_start']
        if row['original_text'][st:end]!=hit.exact_quote:return None
        return hit,row['original_text'],st,end

    def resolve(self,chunk_id:int)->SourceHit|None:
        if not isinstance(chunk_id,int) or isinstance(chunk_id,bool) or chunk_id<1:return None
        with connect(self.db_path) as conn:
            row=conn.execute(self._SQL_BASE+' AND c.id=?',(chunk_id,)).fetchone()
            if row is None or not self._verify_row(row,{}):return None
        return SourceHit(row['id'],row['document_id'],row['name'],row['kind'],row['revision'],
                         row['sha256'],row['unit_kind'],row['unit_number'],row['char_start'],row['char_end'],
                         row['original_text'],0.0,1,True)
