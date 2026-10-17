"""Connection-per-operation repository; leases are interrupted at application restart."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from ..storage.db import connect, transaction

STATES=('PENDING','RUNNING','FAILED','COMPLETED','INTERRUPTED','CANCELLED','SUPERSEDED')

@dataclass(frozen=True)
class Job:
    id:int;document_id:str;revision:int;sha256:str;status:str
    total_units:int;processed_units:int;attempt:int;error_code:str;name:str

class JobQueue:
    def __init__(self,db_path:Path|str):self.db_path=Path(db_path)

    @staticmethod
    def enqueue_in_transaction(conn,document_id:str,revision:int,sha256:str,total:int):
        conn.execute('''UPDATE index_jobs SET status='SUPERSEDED',updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')
                        WHERE document_id=? AND revision!=? AND status IN ('PENDING','FAILED','INTERRUPTED','CANCELLED')''',(document_id,revision))
        conn.execute('''INSERT OR IGNORE INTO index_jobs(document_id,revision,sha256,total_units)
                        VALUES(?,?,?,?)''',(document_id,revision,sha256,total))

    def list(self,limit:int=150)->tuple[Job,...]:
        with connect(self.db_path) as conn:
            rows=conn.execute('''SELECT j.*, d.name FROM index_jobs j JOIN documents d ON j.document_id=d.id
                                 ORDER BY CASE j.status WHEN 'RUNNING' THEN 0 WHEN 'PENDING' THEN 1 ELSE 2 END, j.id DESC LIMIT ?''',(limit,)).fetchall()
        return tuple(Job(*(r[k] for k in ('id','document_id','revision','sha256','status','total_units','processed_units','attempt','error_code','name'))) for r in rows)

    def recover(self)->int:
        with connect(self.db_path) as conn,transaction(conn):
            result=conn.execute("UPDATE index_jobs SET status='INTERRUPTED',error_code='PROCESS_TERMINATED',updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE status='RUNNING'")
            return result.rowcount

    def claim(self)->Job|None:
        with connect(self.db_path) as conn,transaction(conn):
            row=conn.execute('''SELECT j.id FROM index_jobs j JOIN documents d ON d.id=j.document_id
                JOIN versions v ON v.document_id=j.document_id AND v.revision=j.revision
                WHERE j.status='PENDING' AND d.archived=0 AND d.current_revision=j.revision AND v.sha256=j.sha256
                ORDER BY j.id ASC LIMIT 1''').fetchone()
            if row is None:return None
            conn.execute('''UPDATE index_jobs SET status='RUNNING',attempt=attempt+1,processed_units=0,error_code='',
                           updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?''',(row['id'],))
            r=conn.execute('SELECT j.*, d.name FROM index_jobs j JOIN documents d ON d.id=j.document_id WHERE j.id=?',(row['id'],)).fetchone()
        return Job(*(r[k] for k in ('id','document_id','revision','sha256','status','total_units','processed_units','attempt','error_code','name')))

    def progress(self,id:int,units:int):
        with connect(self.db_path) as conn,transaction(conn):
            conn.execute('''UPDATE index_jobs SET processed_units=?,updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')
                            WHERE id=? AND status='RUNNING' AND ? BETWEEN processed_units AND total_units''',(units,id,units))

    def state(self,id:int,status:str,error_code:str=''):
        if status not in ('FAILED','CANCELLED','INTERRUPTED'):
            raise ValueError('Geçersiz sonuç durumu.')
        with connect(self.db_path) as conn,transaction(conn):
            conn.execute('''UPDATE index_jobs SET status=?,error_code=?,updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')
                            WHERE id=? AND status='RUNNING' ''',(status,error_code[:80],id))

    def cancel_pending(self,id:int)->bool:
        with connect(self.db_path) as conn,transaction(conn):
            return conn.execute("UPDATE index_jobs SET status='CANCELLED',error_code='USER_CANCELLED' WHERE id=? AND status='PENDING'",(id,)).rowcount==1

    def retry(self,id:int)->bool:
        with connect(self.db_path) as conn,transaction(conn):
            return conn.execute('''UPDATE index_jobs SET status='PENDING',processed_units=0,error_code='',
                                  updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')
                                  WHERE id=? AND status IN ('FAILED','INTERRUPTED','CANCELLED')
                                  AND EXISTS(SELECT 1 FROM documents d WHERE d.id=index_jobs.document_id AND d.archived=0 AND d.current_revision=index_jobs.revision)''',(id,)).rowcount==1

    def complete(self,job:Job,spans:list[dict]):
        # Commit only entire extraction of still-current, unmodified object, never partial spans.
        with connect(self.db_path) as conn,transaction(conn):
            row=conn.execute('''SELECT j.status,d.current_revision,d.archived,v.sha256
                                FROM index_jobs j JOIN documents d ON j.document_id=d.id
                                JOIN versions v ON v.document_id=j.document_id AND v.revision=j.revision WHERE j.id=?''',(job.id,)).fetchone()
            if row is None or row['status']!='RUNNING' or row['current_revision']!=job.revision or row['archived'] or row['sha256']!=job.sha256:
                raise RuntimeError('JOB_STALE')
            if len(spans)!=job.total_units:raise RuntimeError('UNIT_COUNT_MISMATCH')
            for i,s in enumerate(spans):
                if s['number']!=i or s['kind'] not in ('PAGE','PARAGRAPH') or not isinstance(s['text'],str) or len(s['text'])>5_000_000:
                    raise RuntimeError('INVALID_EXTRACTION')
            conn.execute('DELETE FROM extracted_spans WHERE job_id=?',(job.id,))
            conn.executemany('''INSERT INTO extracted_spans(job_id,document_id,revision,unit_kind,unit_number,char_start,char_end,original_text)
                                VALUES(?,?,?,?,?,?,?,?)''',((job.id,job.document_id,job.revision,s['kind'],s['number'],s['start'],s['end'],s['text']) for s in spans))
            conn.execute('''UPDATE index_jobs SET status='COMPLETED',processed_units=total_units,error_code='',
                            updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?''',(job.id,))
            from ..search.index import index_completed_job
            index_completed_job(conn,job.id)  # atomic publication: extraction + index + metadata
