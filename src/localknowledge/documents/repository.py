"""Simple per-operation SQLite repository. No shared connections across Tk workers."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import sqlite3

from ..storage.db import connect, transaction


@dataclass(frozen=True, slots=True)
class LibraryDocument:
    document_id: str
    name: str
    kind: str
    sha256: str
    revision: int
    size_bytes: int
    page_count: int | None
    paragraph_count: int | None
    updated_at: str
    archived: bool


@dataclass(frozen=True, slots=True)
class LibraryStats:
    registered_documents: int
    stored_versions: int
    pending_index: int
    indexed_documents: int | None = None
    indexed_chunks: int | None = None


@dataclass(frozen=True, slots=True)
class DocumentVersion:
    revision: int
    sha256: str
    byte_size: int
    added_at: str
    page_count: int | None
    paragraph_count: int | None


class DocumentRepository:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    def list_documents(self, query: str = '', kind: str = 'ALL', include_archived: bool = False,
                       limit: int = 100, offset: int = 0) -> tuple[LibraryDocument, ...]:
        if not isinstance(limit, int) or not 1 <= limit <= 200 or not isinstance(offset, int) or offset < 0:
            raise ValueError('Geçersiz sayfa sınırı.')
        if kind not in ('ALL', 'PDF', 'DOCX', 'TXT'):
            raise ValueError('Geçersiz belge türü.')
        if not isinstance(query, str) or len(query) > 200:
            raise ValueError('Arama metni çok uzun.')
        pattern = '%' + query.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
        with connect(self.db_path) as conn:
            rows = conn.execute('''
                SELECT d.id, d.name, d.kind, d.current_revision, d.archived, d.updated_at,
                       v.sha256, v.byte_size, v.page_count, v.paragraph_count
                FROM documents d JOIN versions v ON d.id=v.document_id AND d.current_revision=v.revision
                WHERE d.name LIKE ? ESCAPE '\\' COLLATE NOCASE
                  AND (?='ALL' OR d.kind=?) AND (?=1 OR d.archived=0)
                ORDER BY d.updated_at DESC, d.id ASC LIMIT ? OFFSET ?
            ''', (pattern, kind, kind, int(include_archived), limit, offset)).fetchall()
        return tuple(LibraryDocument(r['id'], r['name'], r['kind'], r['sha256'], r['current_revision'],
                r['byte_size'], r['page_count'], r['paragraph_count'], r['updated_at'], bool(r['archived'])) for r in rows)

    def count_documents(self, query: str = '', kind: str = 'ALL', include_archived: bool = False) -> int:
        if kind not in ('ALL', 'PDF', 'DOCX', 'TXT'):
            raise ValueError('Geçersiz tür.')
        pattern = '%' + query.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
        with connect(self.db_path) as conn:
            return conn.execute("SELECT count(*) FROM documents WHERE name LIKE ? ESCAPE '\\' COLLATE NOCASE AND (?='ALL' OR kind=?) AND (?=1 OR archived=0)",
                                (pattern, kind, kind, int(include_archived))).fetchone()[0]

    def stats(self) -> LibraryStats:
        with connect(self.db_path) as conn:
            documents = conn.execute('SELECT count(*) FROM documents WHERE archived=0').fetchone()[0]
            versions = conn.execute('SELECT count(*) FROM versions').fetchone()[0]
            pending = conn.execute("""SELECT count(*) FROM documents d JOIN versions v ON d.id=v.document_id AND v.revision=d.current_revision
                 LEFT JOIN index_jobs j ON j.document_id=d.id AND j.revision=v.revision AND j.sha256=v.sha256
                 WHERE d.archived=0 AND (j.id IS NULL OR j.status!='COMPLETED')""").fetchone()[0]
            indexed=conn.execute('''SELECT count(*) FROM indexed_versions iv JOIN documents d ON d.id=iv.document_id
                                      WHERE d.archived=0 AND d.current_revision=iv.revision''').fetchone()[0]
            chunks=conn.execute('''SELECT count(*) FROM search_chunks c JOIN indexed_versions iv
                    ON iv.document_id=c.document_id AND iv.revision=c.revision AND iv.sha256=c.sha256
                    JOIN documents d ON d.id=c.document_id WHERE d.archived=0 AND d.current_revision=c.revision''').fetchone()[0]
        return LibraryStats(documents, versions, pending, indexed, chunks)

    def extraction_statuses(self, document_ids: tuple[str,...]) -> dict[str,str]:
        if not document_ids:return {}
        if len(document_ids)>200:raise ValueError('Çok sayıda belge.')
        params=','.join('?' for _ in document_ids)
        with connect(self.db_path) as conn:
            rows=conn.execute(f"""SELECT d.id, CASE WHEN iv.document_id IS NOT NULL AND d.archived=0 THEN 'INDEXED'
                    ELSE COALESCE(j.status,'PENDING') END AS status FROM documents d
                LEFT JOIN index_jobs j ON j.document_id=d.id AND j.revision=d.current_revision
                LEFT JOIN indexed_versions iv ON iv.document_id=d.id AND iv.revision=d.current_revision
                WHERE d.id IN ({params})""",document_ids).fetchall()
        return {r['id']:r['status'] for r in rows}

    def versions(self, document_id: str) -> tuple[DocumentVersion, ...]:
        with connect(self.db_path) as conn:
            rows = conn.execute('SELECT * FROM versions WHERE document_id=? ORDER BY revision DESC', (document_id,)).fetchall()
        return tuple(DocumentVersion(r['revision'], r['sha256'], r['byte_size'], r['added_at'], r['page_count'],r['paragraph_count']) for r in rows)

    def archive(self, document_id: str, archived: bool = True) -> None:
        with connect(self.db_path) as conn, transaction(conn):
            row = conn.execute('SELECT current_revision FROM documents WHERE id=?', (document_id,)).fetchone()
            if not row:
                raise ValueError('Belge bulunamadı.')
            conn.execute("UPDATE documents SET archived=?,updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?", (int(archived), document_id))
            sha = conn.execute('SELECT sha256 FROM versions WHERE document_id=? AND revision=?',(document_id,row['current_revision'])).fetchone()[0]
            conn.execute('INSERT INTO import_events(document_id,revision,operation,source_sha256) VALUES(?,?,?,?)',
                         (document_id,row['current_revision'],'RESTORED' if not archived else 'ARCHIVED',sha))
            if not archived:
                completed=conn.execute("SELECT id FROM index_jobs WHERE document_id=? AND revision=? AND sha256=? AND status='COMPLETED'",
                    (document_id,row['current_revision'],sha)).fetchone()
                if completed:
                    from ..search.index import index_completed_job
                    index_completed_job(conn,completed['id'])

    def managed_object(self, document_id: str, revision: int) -> tuple[str,str,int]:
        with connect(self.db_path) as conn:
            row = conn.execute('SELECT object_relpath,sha256,byte_size FROM versions WHERE document_id=? AND revision=?', (document_id,revision)).fetchone()
        if not row:
            raise ValueError('Belge sürümü bulunamadı.')
        return row['object_relpath'], row['sha256'], row['byte_size']
