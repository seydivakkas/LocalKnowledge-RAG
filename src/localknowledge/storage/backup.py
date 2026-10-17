"""G08: complete offline SQLite + immutable-object backups; never overwrite data.

Directory transport format v1. `manifest.json` is the *last* published file.
An interrupted directory is intentionally invalid. Sources are never modified.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import uuid

FORMAT = 'localknowledge.offline.backup/1'
MAX_OBJECTS = 100_000
MAX_TOTAL_BYTES = 5 * 1024**3  # engineering guard; configurable in later revision


class BackupError(RuntimeError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class BackupSummary:
    destination: Path
    document_count: int
    version_count: int
    object_count: int
    total_bytes: int
    source_digest: str


def _sha_file(path: Path) -> tuple[str, int]:
    sha = hashlib.sha256()
    size = 0
    with path.open('rb') as stream:
        while block := stream.read(1024 * 1024):
            size += len(block)
            if size > MAX_TOTAL_BYTES:
                raise BackupError('BACKUP_SIZE_LIMIT', 'Yedek boyut limiti aşıldı.')
            sha.update(block)
    return sha.hexdigest(), size


def _root_path(value: Path | str) -> Path:
    return Path(value).expanduser().absolute()


def _check_simple_file(path: Path) -> None:
    if path.is_symlink() or not path.is_file() or path.stat().st_nlink > 1:
        raise BackupError('UNSAFE_BACKUP_ENTRY', 'Yedek girdisi güvenli düzenli dosya değil.')


def _rel_object(digest: str) -> str:
    if not isinstance(digest, str) or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
        raise BackupError('INVALID_DIGEST', 'Geçersiz belge SHA-256 kaydı.')
    return f'objects/{digest[:2]}/{digest}.bin'


def _verify_database(path: Path) -> tuple[int, int, dict[str, str]]:
    """Inspect a *temporary SQLite snapshot*; never write to a backup being verified."""
    _check_simple_file(path)
    source_digest = _sha_file(path)
    with tempfile.TemporaryDirectory(prefix='lk-g08-db-check-') as temp:
        copy_path = Path(temp) / 'check.sqlite3'
        try:
            with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as live:
                with closing(sqlite3.connect(str(copy_path))) as copy:
                    live.backup(copy)
        except (sqlite3.DatabaseError,OSError) as exc:
            raise BackupError('DATABASE_INVALID','SQLite salt-okunur doğrulama kopyası alınamadı.') from exc
        if source_digest != _sha_file(path):
            raise BackupError('DATABASE_CHANGED','SQLite doğrulama sırasında kaynağı değişti.')
        return _verify_database_snapshot(copy_path)


def _verify_database_snapshot(path: Path) -> tuple[int, int, dict[str, str]]:
    _check_simple_file(path)
    try:
        with closing(sqlite3.connect(str(path))) as conn:
            conn.row_factory = sqlite3.Row
            if conn.execute('PRAGMA user_version').fetchone()[0] != 3:
                raise BackupError('UNSUPPORTED_SCHEMA', 'Yedek SQLite şema sürümü 3 olmalı.')
            if conn.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise BackupError('DATABASE_INTEGRITY', 'SQLite bütünlüğü bozuk.')
            if conn.execute('PRAGMA foreign_key_check').fetchall():
                raise BackupError('DATABASE_FOREIGN_KEYS', 'SQLite ilişkileri bozuk.')
            # FTS5 integrity-check validates index invariants; roll it back to leave the snapshot intact.
            try:
                conn.execute('BEGIN')
                conn.execute("INSERT INTO search_fts(search_fts) VALUES ('integrity-check')")
            finally:
                conn.rollback()
            docs = conn.execute('SELECT count(*) FROM documents').fetchone()[0]
            versions = conn.execute('SELECT sha256,object_relpath FROM versions').fetchall()
            if len(versions) > MAX_OBJECTS:
                raise BackupError('TOO_MANY_OBJECTS', 'Çok sayıda belge sürümü var.')
            objects: dict[str, str] = {}
            for row in versions:
                digest = row['sha256']
                rel = _rel_object(digest)
                if row['object_relpath'] != rel:
                    raise BackupError('UNSAFE_OBJECT_PATH', 'Kaynak nesne yolu içerik adresiyle eşleşmiyor.')
                objects[digest] = rel
            indexed = conn.execute('SELECT COALESCE(sum(chunk_count),0) FROM indexed_versions').fetchone()[0]
            chunks = conn.execute('SELECT count(*) FROM search_chunks').fetchone()[0]
            if indexed != chunks:
                raise BackupError('INDEX_INTEGRITY', 'Arama bölümleri sayısı indeksle uyuşmuyor.')
            mismatch = conn.execute('''SELECT count(*) FROM indexed_versions i JOIN documents d ON d.id=i.document_id
                JOIN versions v ON v.document_id=i.document_id AND v.revision=i.revision
                WHERE d.archived!=0 OR d.current_revision!=i.revision OR v.sha256!=i.sha256''').fetchone()[0]
            if mismatch:
                raise BackupError('INDEX_IDENTITY', 'Kaynak indeksleri güncel sürümle uyuşmuyor.')
            return docs, len(versions), objects
    except (sqlite3.DatabaseError, OSError) as exc:
        raise BackupError('DATABASE_INVALID', 'SQLite yedek bütünlüğü doğrulanamadı.') from exc


def _validate_entries(directory: Path, expected: set[str]) -> None:
    seen: set[str] = set()
    for item in directory.rglob('*'):
        rel = item.relative_to(directory).as_posix()
        if item.is_symlink():
            raise BackupError('UNSAFE_BACKUP_ENTRY', 'Sembolik bağlantılı yedek reddedildi.')
        if item.is_file():
            _check_simple_file(item)
            seen.add(rel)
        elif not item.is_dir():
            raise BackupError('UNSAFE_BACKUP_ENTRY', 'Özel dosya türü reddedildi.')
    if seen != expected:
        raise BackupError('BACKUP_FILE_SET', 'Yedek eksik veya beklenmeyen dosya içeriyor.')


def _copy_verified(source: Path, target: Path, digest: str, limit: int) -> int:
    _check_simple_file(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    sha = hashlib.sha256(); total = 0
    # x mode: refuse overwriting another file even under a naming race.
    with source.open('rb') as incoming, target.open('xb') as outgoing:
        while block := incoming.read(1024 * 1024):
            total += len(block)
            if total > limit:
                raise BackupError('BACKUP_SIZE_LIMIT', 'Yedek nesnesi güvenlik sınırını aştı.')
            outgoing.write(block)
            sha.update(block)
        outgoing.flush(); os.fsync(outgoing.fileno())
    if sha.hexdigest() != digest or _sha_file(source) != (digest, total):
        raise BackupError('OBJECT_CHANGED', 'Özgün belge SHA-256 kaynağı değişmiş veya bozuk.')
    return total


def inspect_backup(folder: Path | str) -> BackupSummary:
    folder = _root_path(folder)
    if not folder.is_dir() or folder.is_symlink():
        raise BackupError('BACKUP_NOT_FOUND', 'Yedek dizini bulunamadı.')
    manifest_file = folder / 'manifest.json'
    _check_simple_file(manifest_file)
    if manifest_file.stat().st_size > 2_000_000:
        raise BackupError('MANIFEST_SIZE', 'Yedek manifestosu çok büyük.')
    try:
        manifest = json.loads(manifest_file.read_text(encoding='utf-8'))
    except (UnicodeError, ValueError) as exc:
        raise BackupError('MANIFEST_INVALID', 'Manifest JSON okunamıyor.') from exc
    if not isinstance(manifest, dict) or manifest.get('format') != FORMAT:
        raise BackupError('BACKUP_VERSION', 'Desteklenmeyen yedek formatı.')
    entries = manifest.get('entries')
    if not isinstance(entries, dict) or len(entries) < 1 or len(entries) > MAX_OBJECTS + 1:
        raise BackupError('MANIFEST_INVALID', 'Yedek dosya listesi geçersiz.')
    if 'library.sqlite3' not in entries:
        raise BackupError('DATABASE_MISSING', 'Yedekte SQLite bulunamadı.')
    expected = {'manifest.json', *entries.keys()}
    _validate_entries(folder, expected)
    total_bytes = 0
    for relative, metadata in entries.items():
        if not isinstance(relative, str) or (relative != 'library.sqlite3' and not relative.startswith('objects/')):
            raise BackupError('BACKUP_PATH', 'İzin verilmeyen yedek yolu.')
        p = Path(relative)
        if p.is_absolute() or '..' in p.parts or '\\' in relative or relative != p.as_posix():
            raise BackupError('BACKUP_PATH', 'Geçersiz yedek iç yolu.')
        if not isinstance(metadata, dict) or type(metadata.get('bytes')) != int or metadata['bytes'] < 1:
            raise BackupError('MANIFEST_INVALID', 'Dosya manifest alanları hatalı.')
        digest = metadata.get('sha256')
        if not isinstance(digest, str) or len(digest) != 64:
            raise BackupError('MANIFEST_INVALID', 'SHA-256 alanı hatalı.')
        actual, size = _sha_file(folder / relative)
        if (actual, size) != (digest, metadata['bytes']):
            raise BackupError('HASH_MISMATCH', 'Yedek dosya içeriği SHA-256 ile eşleşmedi.')
        total_bytes += size
        if total_bytes > MAX_TOTAL_BYTES:
            raise BackupError('BACKUP_SIZE_LIMIT', 'Toplam yedek boyutu limiti aşıldı.')
    db_digest = entries['library.sqlite3']['sha256']
    doc_count, version_count, objects = _verify_database(folder / 'library.sqlite3')
    if set(entries) != {'library.sqlite3', *objects.values()}:
        raise BackupError('REFERENCED_OBJECT_MISMATCH', 'Yedek nesneleri SQLite kayıtlarına karşılık gelmiyor.')
    if any(entries[relative]['sha256'] != digest for digest, relative in objects.items()):
        raise BackupError('OBJECT_SHA_MISMATCH', 'Nesne yolu ve hash eşleşmesi bozuk.')
    if (doc_count, version_count, len(objects)) != (manifest.get('documents'),manifest.get('versions'),manifest.get('objects')):
        raise BackupError('MANIFEST_COUNT', 'Yedek nesne ve belge sayıları uyuşmuyor.')
    return BackupSummary(folder,doc_count,version_count,len(objects),total_bytes,db_digest)


def _write_manifest_last(folder: Path, record: dict) -> None:
    payload = json.dumps(record,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')
    temp = folder / ('.manifest-' + uuid.uuid4().hex)
    try:
        with temp.open('xb') as stream:
            stream.write(payload);stream.flush();os.fsync(stream.fileno())
        os.link(temp, folder / 'manifest.json')
    finally:
        temp.unlink(missing_ok=True)


def create_backup(root: Path | str, destination: Path | str) -> BackupSummary:
    root = _root_path(root).resolve()
    dest = _root_path(destination).resolve()
    if root == dest or root in dest.parents or dest in root.parents:
        raise BackupError('UNSAFE_DESTINATION', 'Yedek kaynak veri klasörünün içinde veya üstünde olamaz.')
    if not (root / 'library.sqlite3').is_file():
        raise BackupError('SOURCE_MISSING', 'Yerel belge veritabanı bulunamadı.')
    try:
        dest.mkdir(mode=0o700)  # exclusive: no overwrite, even of an empty preexisting folder
    except FileExistsError as exc:
        raise BackupError('DESTINATION_EXISTS', 'Mevcut yedeğin üzerine yazma yasak.') from exc
    try:
        staging_db = dest / 'library.sqlite3'
        with closing(sqlite3.connect((root / 'library.sqlite3').as_uri()+'?mode=ro',uri=True)) as live:
            with closing(sqlite3.connect(str(staging_db))) as copy:
                live.backup(copy)
        doc_count, version_count, objects = _verify_database(staging_db)
        entries: dict[str, dict] = {}
        db_sha, db_size = _sha_file(staging_db)
        entries['library.sqlite3'] = {'sha256':db_sha, 'bytes':db_size}
        running = db_size
        for digest, rel in sorted(objects.items()):
            source = root / rel
            if (root/'objects').is_symlink() or (root/'objects'/digest[:2]).is_symlink():
                raise BackupError('UNSAFE_OBJECT_PATH','Özgün nesne dizininde sembolik bağlantı reddedildi.')
            target = dest / rel
            length = _copy_verified(source,target,digest,MAX_TOTAL_BYTES-running)
            running += length
            entries[rel] = {'sha256':digest,'bytes':length}
        _write_manifest_last(dest, {'format':FORMAT,'documents':doc_count,'versions':version_count,
                                    'objects':len(objects),'entries':entries})
        summary = inspect_backup(dest)
        return summary
    except Exception:
        shutil.rmtree(dest)  # only directory that THIS call exclusively created
        raise


def restore_backup(source: Path | str, target: Path | str) -> BackupSummary:
    source = _root_path(source).resolve()
    target = _root_path(target).resolve()
    if target == source or source in target.parents or target in source.parents:
        raise BackupError('UNSAFE_DESTINATION', 'Geri yükleme konumu yedek diziniyle örtüşemez.')
    original = inspect_backup(source)  # do not mutate anything on validation failure
    try:
        target.mkdir(mode=0o700)
    except FileExistsError as exc:
        raise BackupError('DESTINATION_EXISTS', 'Geri yükleme yalnız yeni boş klasöre yapılır.') from exc
    try:
        manifest = json.loads((source / 'manifest.json').read_text(encoding='utf-8'))
        for rel, metadata in sorted(manifest['entries'].items()):
            if rel == 'library.sqlite3':continue
            _copy_verified(source / rel,target / rel,metadata['sha256'],MAX_TOTAL_BYTES)
        # Keep DB inaccessible until every immutable content object is present.
        db_tmp = target / '.restoring.sqlite3'
        _copy_verified(source / 'library.sqlite3',db_tmp,manifest['entries']['library.sqlite3']['sha256'],MAX_TOTAL_BYTES)
        with closing(sqlite3.connect(str(db_tmp))) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute("UPDATE index_jobs SET status='INTERRUPTED',error_code='RESTORED_SNAPSHOT' WHERE status='RUNNING'")
            # FTS5 index must be reconstructible from original committed G04 spans.
            from ..search.index import rebuild_completed
            rebuild_completed(conn)
            conn.commit()
        _verify_database(db_tmp)
        os.link(db_tmp,target / 'library.sqlite3')
        db_tmp.unlink()
        # Record restore provenance separately; it is not a signed claim.
        provenance = {'format':FORMAT,'source_database_sha256':original.source_digest,
                      'restored_database_sha256':_sha_file(target/'library.sqlite3')[0],
                      'documents':original.document_count,'versions':original.version_count}
        (target/'restore_provenance.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2),encoding='utf-8')
        from .db import connect
        with connect(target/'library.sqlite3') as check:
            check.execute('SELECT count(*) FROM search_fts').fetchone()
        return BackupSummary(target,original.document_count,original.version_count,original.object_count,
                             original.total_bytes,original.source_digest)
    except Exception:
        shutil.rmtree(target)
        raise


class BackupService:
    """UI/CLI facade; no GUI dependencies or implicit data replacement."""
    def __init__(self, root: Path | str):
        self.root = _root_path(root)

    def create(self, destination: Path | str) -> BackupSummary:
        return create_backup(self.root,destination)

    def inspect(self, backup_path: Path | str) -> BackupSummary:
        return inspect_backup(backup_path)

    def restore(self, backup_path: Path | str, empty_new_target: Path | str) -> BackupSummary:
        if self.root.resolve() == _root_path(empty_new_target).resolve():
            raise BackupError('LIVE_DATA_PROTECTED', 'Çalışan veritabanı üzerine geri yükleme yasak.')
        return restore_backup(backup_path,empty_new_target)
