"""SQLite v3: durable G04 extraction and transactional G05 FTS5 index."""
from __future__ import annotations
from contextlib import contextmanager
from pathlib import Path
import sqlite3

SCHEMA_VERSION = 3
SCHEMA = """
CREATE TABLE documents (
 id TEXT PRIMARY KEY, name TEXT NOT NULL,
 kind TEXT NOT NULL CHECK(kind IN ('PDF','DOCX','TXT')),
 current_revision INTEGER NOT NULL DEFAULT 1 CHECK(current_revision>0),
 archived INTEGER NOT NULL DEFAULT 0 CHECK(archived IN (0,1)),
 created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
 updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE TABLE versions (
 document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE RESTRICT,
 revision INTEGER NOT NULL CHECK(revision>0),
 sha256 TEXT NOT NULL CHECK(length(sha256)=64),
 byte_size INTEGER NOT NULL CHECK(byte_size>=0),
 object_relpath TEXT NOT NULL,
 page_count INTEGER, paragraph_count INTEGER,
 original_name TEXT NOT NULL,
 added_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
 PRIMARY KEY(document_id,revision), UNIQUE(document_id,sha256)
);
CREATE TABLE source_paths (
 canonical_path TEXT PRIMARY KEY,
 document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE RESTRICT,
 last_seen_sha256 TEXT NOT NULL,
 last_seen_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE INDEX idx_paths_document ON source_paths(document_id);
CREATE INDEX idx_versions_sha ON versions(sha256);
CREATE INDEX idx_documents_name ON documents(name);
CREATE TABLE page_metadata (
 document_id TEXT NOT NULL, revision INTEGER NOT NULL,
 page_number INTEGER NOT NULL CHECK(page_number>=1),
 extracted_chars INTEGER NOT NULL CHECK(extracted_chars>=0),
 PRIMARY KEY(document_id,revision,page_number),
 FOREIGN KEY(document_id,revision) REFERENCES versions(document_id,revision) ON DELETE RESTRICT
);
CREATE TABLE paragraph_metadata (
 document_id TEXT NOT NULL, revision INTEGER NOT NULL,
 ordinal INTEGER NOT NULL CHECK(ordinal>=0),
 char_start INTEGER NOT NULL CHECK(char_start>=0),
 char_end INTEGER NOT NULL CHECK(char_end>char_start),
 PRIMARY KEY(document_id,revision,ordinal),
 FOREIGN KEY(document_id,revision) REFERENCES versions(document_id,revision) ON DELETE RESTRICT
);
CREATE TABLE import_events (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE RESTRICT,
 revision INTEGER NOT NULL,
 operation TEXT NOT NULL CHECK(operation IN ('CREATED','NEW_VERSION','DUPLICATE','ALIAS','ARCHIVED','RESTORED')),
 source_sha256 TEXT NOT NULL,
 occurred_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
 FOREIGN KEY(document_id,revision) REFERENCES versions(document_id,revision) ON DELETE RESTRICT
);
"""
V2 = """
CREATE TABLE index_jobs (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 document_id TEXT NOT NULL, revision INTEGER NOT NULL,
 sha256 TEXT NOT NULL CHECK(length(sha256)=64),
 task_type TEXT NOT NULL DEFAULT 'EXTRACT_TEXT' CHECK(task_type='EXTRACT_TEXT'),
 status TEXT NOT NULL DEFAULT 'PENDING' CHECK(status IN ('PENDING','RUNNING','FAILED','COMPLETED','INTERRUPTED','CANCELLED','SUPERSEDED')),
 total_units INTEGER NOT NULL DEFAULT 0 CHECK(total_units>=0),
 processed_units INTEGER NOT NULL DEFAULT 0 CHECK(processed_units>=0 AND processed_units<=total_units),
 attempt INTEGER NOT NULL DEFAULT 0 CHECK(attempt>=0),
 error_code TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
 updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
 UNIQUE(document_id,revision,sha256,task_type),
 FOREIGN KEY(document_id,revision) REFERENCES versions(document_id,revision) ON DELETE RESTRICT
);
CREATE INDEX idx_jobs_status ON index_jobs(status, id);
CREATE TABLE extracted_spans (
 job_id INTEGER NOT NULL REFERENCES index_jobs(id) ON DELETE RESTRICT,
 document_id TEXT NOT NULL, revision INTEGER NOT NULL,
 unit_kind TEXT NOT NULL CHECK(unit_kind IN ('PAGE','PARAGRAPH')),
 unit_number INTEGER NOT NULL CHECK(unit_number>=0),
 char_start INTEGER NOT NULL CHECK(char_start>=0),
 char_end INTEGER NOT NULL CHECK(char_end>=char_start),
 original_text TEXT NOT NULL,
 PRIMARY KEY(job_id,unit_number),
 FOREIGN KEY(document_id,revision) REFERENCES versions(document_id,revision) ON DELETE RESTRICT
);
"""

V3 = """
CREATE TABLE search_chunks (
 id INTEGER PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE RESTRICT,
 revision INTEGER NOT NULL, sha256 TEXT NOT NULL CHECK(length(sha256)=64),
 job_id INTEGER NOT NULL REFERENCES index_jobs(id) ON DELETE RESTRICT,
 unit_kind TEXT NOT NULL CHECK(unit_kind IN ('PAGE','PARAGRAPH')),
 unit_number INTEGER NOT NULL CHECK(unit_number>=0),
 char_start INTEGER NOT NULL CHECK(char_start>=0), char_end INTEGER NOT NULL CHECK(char_end>char_start),
 original_text TEXT NOT NULL CHECK(length(original_text)>0),
 FOREIGN KEY(document_id,revision) REFERENCES versions(document_id,revision) ON DELETE RESTRICT
);
CREATE INDEX idx_search_chunks_doc ON search_chunks(document_id,revision);
CREATE TABLE indexed_versions (
 document_id TEXT PRIMARY KEY REFERENCES documents(id) ON DELETE RESTRICT,
 revision INTEGER NOT NULL, sha256 TEXT NOT NULL CHECK(length(sha256)=64),
 job_id INTEGER NOT NULL REFERENCES index_jobs(id) ON DELETE RESTRICT,
 chunk_count INTEGER NOT NULL CHECK(chunk_count>=0),
 indexed_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
 FOREIGN KEY(document_id,revision) REFERENCES versions(document_id,revision) ON DELETE RESTRICT
);
CREATE VIRTUAL TABLE search_fts USING fts5(original_text, content='search_chunks',content_rowid='id',tokenize='unicode61 remove_diacritics 2');
CREATE TRIGGER chunk_ai AFTER INSERT ON search_chunks BEGIN
 INSERT INTO search_fts(rowid,original_text) VALUES(new.id,new.original_text);
END;
CREATE TRIGGER chunk_ad AFTER DELETE ON search_chunks BEGIN
 INSERT INTO search_fts(search_fts,rowid,original_text) VALUES('delete',old.id,old.original_text);
END;
CREATE TRIGGER chunk_au AFTER UPDATE ON search_chunks BEGIN
 INSERT INTO search_fts(search_fts,rowid,original_text) VALUES('delete',old.id,old.original_text);
 INSERT INTO search_fts(rowid,original_text) VALUES(new.id,new.original_text);
END;
CREATE TRIGGER document_search_invalidation AFTER UPDATE OF current_revision,archived ON documents
WHEN new.current_revision!=old.current_revision OR new.archived!=old.archived
BEGIN
 DELETE FROM search_chunks WHERE document_id=new.id;
 DELETE FROM indexed_versions WHERE document_id=new.id;
END;
"""


def _migrate_v2_to_v3(conn: sqlite3.Connection) -> None:
    try:
        conn.execute('BEGIN IMMEDIATE')
        # sqlite3.complete_statement preserves trigger bodies as one statement.
        buffer = ''
        for line in V3.splitlines(True):
            buffer += line
            if sqlite3.complete_statement(buffer):
                conn.execute(buffer)
                buffer = ''
        if buffer.strip():raise DatabaseError('Eksik SQL migration komutu')
        from ..search.index import rebuild_completed
        rebuild_completed(conn)  # backfill all already-COMPLETED G04 jobs
        conn.execute('PRAGMA user_version=3')
        conn.commit()
    except Exception:
        conn.rollback()
        raise


class DatabaseError(RuntimeError):
    pass


def _migrate_v1_to_v2(conn: sqlite3.Connection) -> None:
    try:
        conn.execute('BEGIN IMMEDIATE')
        for sql in V2.split(';'):
            if sql.strip():
                conn.execute(sql)
        conn.execute('''INSERT INTO index_jobs(document_id,revision,sha256,total_units)
            SELECT d.id,d.current_revision,v.sha256,
                   CASE WHEN d.kind='PDF' THEN COALESCE(v.page_count,0) ELSE COALESCE(v.paragraph_count,0) END
            FROM documents d JOIN versions v ON v.document_id=d.id AND v.revision=d.current_revision
            WHERE d.archived=0''')
        conn.execute('PRAGMA user_version=2')
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def open_db(path: str | Path) -> sqlite3.Connection:
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    conn=sqlite3.connect(str(path),timeout=20)
    conn.row_factory=sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    conn.execute('PRAGMA busy_timeout=20000')
    try:
        version=conn.execute('PRAGMA user_version').fetchone()[0]
        if version==0:
            if conn.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchone()[0]:
                raise DatabaseError('Sürümü bilinmeyen veritabanı değiştirilmedi.')
            conn.executescript('BEGIN IMMEDIATE;\n'+SCHEMA+'\nPRAGMA user_version=1;\nCOMMIT;')
            version=1
        if version==1:
            _migrate_v1_to_v2(conn)
            version=2
        if version==2:
            _migrate_v2_to_v3(conn)
            version=3
        if version!=SCHEMA_VERSION:
            raise DatabaseError(f'Desteklenmeyen veritabanı sürümü: {version}.')
        if conn.execute('PRAGMA quick_check').fetchone()[0]!='ok' or conn.execute('PRAGMA foreign_key_check').fetchall():
            raise DatabaseError('Veritabanı bütünlük kontrolü başarısız.')
        return conn
    except (sqlite3.DatabaseError,DatabaseError) as exc:
        conn.close()
        if isinstance(exc,DatabaseError):raise
        raise DatabaseError('Veritabanı açılamadı; kaynak değiştirilmedi.') from exc


@contextmanager
def connect(path: str | Path):
    conn=open_db(path)
    try:yield conn
    finally:conn.close()


@contextmanager
def transaction(conn: sqlite3.Connection):
    try:
        conn.execute('BEGIN IMMEDIATE')
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
