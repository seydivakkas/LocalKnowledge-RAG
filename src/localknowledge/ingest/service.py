"""Content-addressed immutable intake: preflight -> staged SHA -> parse -> atomic object -> DB."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import os
import tempfile
import uuid
import stat

from ..config import data_dir
from ..domain.models import SourceKind
from ..documents.repository import DocumentRepository
from ..storage.db import connect, transaction
from .parsers import inspect, IntakeError, InspectedSource, MAX_SOURCE_BYTES

CHUNK_BYTES = 1024 * 1024


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(CHUNK_BYTES), b''):
            h.update(block)
    return h.hexdigest()


@dataclass(frozen=True, slots=True)
class ImportResult:
    document_id: str
    revision: int
    sha256: str
    kind: SourceKind
    operation: str
    warning: str = ''


class IntakeService:
    def __init__(self, root: Path | str | None = None):
        self.root = Path(root) if root is not None else data_dir()
        self.db_path = self.root / 'library.sqlite3'
        self.repository = DocumentRepository(self.db_path)

    @staticmethod
    def _source_path(value: Path | str) -> Path:
        path = Path(value).expanduser().resolve(strict=True)
        if not path.is_file():
            raise IntakeError('NOT_A_FILE', 'Belge bir dosya olmalıdır.')
        if path.suffix.lower() not in ('.pdf', '.txt', '.docx'):
            raise IntakeError('UNSUPPORTED_FORMAT', 'Yalnız PDF, DOCX ve TXT belgeleri desteklenir.')
        if path.stat().st_size == 0 or path.stat().st_size > MAX_SOURCE_BYTES:
            raise IntakeError('SIZE_LIMIT', 'Belge boş veya 50 MiB sınırını aşıyor.')
        return path

    def import_document(self, value: Path | str) -> ImportResult:
        try:
            source = self._source_path(value)
        except (OSError, RuntimeError) as exc:
            raise IntakeError('SOURCE_UNAVAILABLE', 'Kaynak belge bulunamadı veya okunamıyor.') from exc
        source_stat = source.stat()
        original_path = str(source)
        bucket = self.root / 'objects' / 'staging'
        bucket.mkdir(parents=True, exist_ok=True)
        # Stage a private copy, never modify or move the source file.
        temp = None
        try:
            with tempfile.NamedTemporaryFile(dir=bucket, prefix='.incoming-', suffix='.part', delete=False) as stream:
                temp = Path(stream.name)
                h = hashlib.sha256()
                total = 0
                with source.open('rb') as input_file:
                    while block := input_file.read(CHUNK_BYTES):
                        total += len(block)
                        if total > MAX_SOURCE_BYTES:
                            raise IntakeError('SIZE_LIMIT', 'Belge güvenli boyut sınırını aştı.')
                        stream.write(block)
                        h.update(block)
                stream.flush()
                os.fsync(stream.fileno())
            digest = h.hexdigest()
            after = source.stat()
            if (source_stat.st_size, source_stat.st_mtime_ns, source_stat.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino) or _hash_file(source) != digest:
                raise IntakeError('SOURCE_CHANGED', 'Kaynak dosya içe alma sırasında değişti; işlem durduruldu.')
            inspected = inspect(temp, source.suffix)
            kind = inspected.kind
            # Object key never includes untrusted filename.
            rel = f'objects/{digest[:2]}/{digest}.bin'
            object_path = self.root / rel
            object_path.parent.mkdir(parents=True, exist_ok=True)
            created_object = False
            if object_path.exists():
                if object_path.is_symlink() or not object_path.is_file() or object_path.stat().st_size != total or _hash_file(object_path) != digest:
                    raise IntakeError('OBJECT_CORRUPT', 'Kayıtlı özgün nesne ile SHA-256 eşleşmiyor; içe alma durduruldu.')
            else:
                try:
                    os.link(temp, object_path)  # Atomic create-without-overwrite, same filesystem.
                    created_object = True
                except FileExistsError:
                    if _hash_file(object_path) != digest:
                        raise IntakeError('OBJECT_CORRUPT', 'Nesne deposunda hash uyuşmazlığı.') from None
                except OSError as exc:
                    raise IntakeError('STORAGE_ERROR', 'Dosya sistemi güvenli atomik kayıt sunmuyor.') from exc
            try:
                result = self._commit(original_path, source.name, kind, digest, total, rel, inspected)
            except Exception:
                # Unreferenced object is removed only if this operation created it.
                if created_object:
                    object_path.unlink(missing_ok=True)
                raise
            return result
        finally:
            if temp is not None:
                temp.unlink(missing_ok=True)

    def _commit(self, original_path: str, name: str, kind: SourceKind, digest: str,
                total: int, rel: str, inspected: InspectedSource) -> ImportResult:
        with connect(self.db_path) as conn, transaction(conn):
            # Same canonical path = version of existing document.
            found = conn.execute('SELECT document_id FROM source_paths WHERE canonical_path=?', (original_path,)).fetchone()
            doc_id = found['document_id'] if found else None
            if not doc_id:
                # Same bytes, different path = a new alias, not a duplicated document.
                known = conn.execute('SELECT document_id FROM versions WHERE sha256=? ORDER BY rowid LIMIT 1', (digest,)).fetchone()
                if known:
                    doc_id = known['document_id']
                    operation = 'ALIAS'
                else:
                    doc_id = uuid.uuid4().hex
                    conn.execute('INSERT INTO documents(id,name,kind) VALUES(?,?,?)', (doc_id, name, kind.value))
                    operation = 'CREATED'
            else:
                operation = 'NEW_VERSION'
            current = conn.execute('SELECT current_revision,kind FROM documents WHERE id=?', (doc_id,)).fetchone()
            # A path may legitimately change PDF→TXT: retain it as separate document? Refuse unsafe conversion.
            if current['kind'] != kind.value:
                raise IntakeError('KIND_CHANGED', 'Dosya türü değişti. Farklı adla yeni belge olarak ekleyin.')
            existing = conn.execute('SELECT revision FROM versions WHERE document_id=? AND sha256=?', (doc_id, digest)).fetchone()
            if existing:
                revision = existing['revision']
                operation = 'ALIAS' if operation == 'ALIAS' else 'DUPLICATE'
            else:
                revision = current['current_revision'] + 1 if operation == 'NEW_VERSION' else 1
                conn.execute('''INSERT INTO versions(document_id,revision,sha256,byte_size,object_relpath,page_count,paragraph_count,original_name)
                                VALUES(?,?,?,?,?,?,?,?)''', (doc_id,revision,digest,total,rel,inspected.page_count,inspected.paragraph_count,name))
                if kind is SourceKind.PDF:
                    conn.executemany('INSERT INTO page_metadata(document_id,revision,page_number,extracted_chars) VALUES(?,?,?,?)',
                                     ((doc_id,revision,i,count) for i,count in enumerate(inspected.page_chars,1)))
                else:
                    conn.executemany('INSERT INTO paragraph_metadata(document_id,revision,ordinal,char_start,char_end) VALUES(?,?,?,?,?)',
                                     ((doc_id,revision,i,start,end) for i,(start,end) in enumerate(inspected.paragraph_offsets)))
                conn.execute("UPDATE documents SET current_revision=?,archived=0,name=?,updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?",(revision,name,doc_id))
            conn.execute('UPDATE documents SET archived=0 WHERE id=?', (doc_id,))
            conn.execute('''INSERT INTO source_paths(canonical_path,document_id,last_seen_sha256) VALUES(?,?,?)
                            ON CONFLICT(canonical_path) DO UPDATE SET last_seen_sha256=excluded.last_seen_sha256,last_seen_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')''',
                         (original_path,doc_id,digest))
            from ..jobs.queue import JobQueue
            JobQueue.enqueue_in_transaction(conn,doc_id,revision,digest,
                    inspected.page_count if kind is SourceKind.PDF else inspected.paragraph_count)
            conn.execute('INSERT INTO import_events(document_id,revision,operation,source_sha256) VALUES(?,?,?,?)',
                         (doc_id,revision,operation,digest))
            # Reindex a restored/aliased already-COMPLETED extraction if its FTS rows were invalidated.
            completed=conn.execute("SELECT id FROM index_jobs WHERE document_id=? AND revision=? AND sha256=? AND status='COMPLETED'",(doc_id,revision,digest)).fetchone()
            if completed and not conn.execute('SELECT 1 FROM indexed_versions WHERE document_id=?',(doc_id,)).fetchone():
                from ..search.index import index_completed_job
                index_completed_job(conn,completed['id'])
        return ImportResult(doc_id,revision,digest,kind,operation,inspected.warning)

    def verify(self, document_id: str, revision: int) -> bool:
        rel, digest, size = self.repository.managed_object(document_id,revision)
        # Only previously created, content-addressed managed paths are followed.
        expected = f'objects/{digest[:2]}/{digest}.bin'
        if rel != expected:
            return False
        path = self.root / rel
        if path.is_symlink() or not path.is_file() or path.stat().st_size != size:
            return False
        return _hash_file(path) == digest
