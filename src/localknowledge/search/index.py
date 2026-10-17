"""Authoritative G04 extraction -> G05 FTS5 index transaction bridge.

FTS is external-content, managed by search_chunks triggers. Caller owns the
transaction. Never index an archived/stale/non-COMPLETED source revision.
"""
from __future__ import annotations
import sqlite3

# Each chunk is wholly inside a single original PDF page or DOCX/TXT unit.
CHUNK_LIMIT = 780
OVERLAP = 100


def split_unit(text: str, *, limit: int = CHUNK_LIMIT, overlap: int = OVERLAP):
    if not 0 <= overlap < limit or limit < 30:
        raise ValueError('Invalid chunk parameters')
    # Preserve source bytes/offsets; NEVER normalize the stored quote itself.
    at = 0
    while at < len(text):
        boundary = min(len(text), at + limit)
        if boundary < len(text):
            cut = text.rfind(' ', at + max(1, limit // 2), boundary)
            if cut > at: boundary = cut + 1
        chunk = text[at:boundary]
        if chunk.strip():
            yield at, boundary, chunk
        if boundary == len(text): break
        at = max(at + 1, boundary - overlap)


def index_completed_job(conn: sqlite3.Connection, job_id: int) -> int:
    row = conn.execute('''SELECT j.id,j.document_id,j.revision,j.sha256,j.status,d.current_revision,d.archived
        FROM index_jobs j JOIN documents d ON d.id=j.document_id
        JOIN versions v ON v.document_id=j.document_id AND v.revision=j.revision
        WHERE j.id=? AND v.sha256=j.sha256''', (job_id,)).fetchone()
    if row is None or row['status'] != 'COMPLETED' or row['archived'] or row['current_revision'] != row['revision']:
        raise ValueError('INDEX_SOURCE_NOT_CURRENT')
    spans = conn.execute('''SELECT unit_kind,unit_number,char_start,char_end,original_text
           FROM extracted_spans WHERE job_id=? ORDER BY unit_number''',(job_id,)).fetchall()
    expected=conn.execute('SELECT total_units FROM index_jobs WHERE id=?',(job_id,)).fetchone()[0]
    if len(spans)!=expected or any(v['unit_number']!=i for i,v in enumerate(spans)):
        raise ValueError('EXTRACTED_SPANS_INCOMPLETE')
    conn.execute('DELETE FROM search_chunks WHERE document_id=?',(row['document_id'],))
    count = 0
    for span in spans:
        if span['unit_kind'] not in ('PAGE','PARAGRAPH') or span['char_end']-span['char_start'] != len(span['original_text']):
            raise ValueError('EXTRACTED_SPAN_INVALID')
        for local_start, local_end, original in split_unit(span['original_text']):
            conn.execute('''INSERT INTO search_chunks(
                document_id,revision,sha256,job_id,unit_kind,unit_number,char_start,char_end,original_text)
                VALUES(?,?,?,?,?,?,?,?,?)''',(
                row['document_id'],row['revision'],row['sha256'],job_id,
                span['unit_kind'],span['unit_number'],span['char_start'] + local_start,
                span['char_start'] + local_end,original))
            count += 1
    conn.execute('''INSERT INTO indexed_versions(document_id,revision,sha256,job_id,chunk_count)
                    VALUES(?,?,?,?,?) ON CONFLICT(document_id) DO UPDATE SET
                    revision=excluded.revision,sha256=excluded.sha256,
                    job_id=excluded.job_id,chunk_count=excluded.chunk_count,
                    indexed_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')''',
                 (row['document_id'],row['revision'],row['sha256'],job_id,count))
    return count


def rebuild_completed(conn: sqlite3.Connection) -> dict[str,int]:
    """Reconstruct visible index from G04 completed jobs; runs in one transaction."""
    conn.execute('DELETE FROM search_chunks')
    conn.execute('DELETE FROM indexed_versions')
    rows = conn.execute('''SELECT j.id FROM index_jobs j JOIN documents d ON d.id=j.document_id
          JOIN versions v ON v.document_id=j.document_id AND v.revision=j.revision
          WHERE j.status='COMPLETED' AND d.archived=0
          AND j.revision=d.current_revision AND j.sha256=v.sha256 ORDER BY j.id''').fetchall()
    indexed=0;chunks=0
    for row in rows:
        chunks += index_completed_job(conn,row['id'])
        indexed+=1
    # FTS5 may be rebuilt from canonical content rows if recovery is requested.
    conn.execute("INSERT INTO search_fts(search_fts) VALUES('rebuild')")
    return {'documents':indexed,'chunks':chunks}
