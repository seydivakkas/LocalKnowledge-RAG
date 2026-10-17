"""Non-network CLI with durable extraction and verifiable G05 FTS5 search."""
from __future__ import annotations

import argparse
import json
import sqlite3
from .config import data_dir
from .ingest.service import IntakeService
from .jobs.queue import JobQueue
from .jobs.runner import Runner
from .search.service import SearchService,SearchError
from .search.index import rebuild_completed
from .storage.db import connect,transaction
from .storage.backup import BackupService, BackupError

from . import __version__


def _fts5_capable() -> bool:
    """Capability probe, not proof an index has been constructed."""
    conn = sqlite3.connect(":memory:")
    try:
        try:
            conn.execute("CREATE VIRTUAL TABLE probe USING fts5(content)")
        except sqlite3.OperationalError:
            return False
        return True
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="localknowledge", description="LocalKnowledge yerel bilgi arama")
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--version", action="store_true", help="Sürümü yazdır")
    actions.add_argument("--smoke", action="store_true", help="Paket ve SQLite yetenek kontrolü; indeks/arama testi DEĞİL")
    actions.add_argument("--gui", action="store_true", help="Tkinter masaüstü uygulamasını aç")
    actions.add_argument("--import-file", metavar="PATH", help="Dosyayı yerel kütüphaneye içe al")
    actions.add_argument("--list-documents", action="store_true", help="Kütüphane kayıtlarını JSON yazdır")
    actions.add_argument("--library-stats", action="store_true", help="Gerçek belge sayılarını JSON yazdır")
    actions.add_argument("--list-jobs", action="store_true", help="SQLite kalıcı çıkarma işlerini JSON yazdır")
    actions.add_argument("--process-next", action="store_true", help="Bekleyen bir metin çıkarma işini işle")
    actions.add_argument("--retry-job", type=int, metavar="ID", help="Başarısız/kesilmiş işi yeniden sıraya al")
    actions.add_argument("--cancel-job", type=int, metavar="ID", help="Bekleyen işi iptal et")
    actions.add_argument("--search", metavar="QUERY", help="FTS5 / BM25 doğrulanmış kaynak araması")
    actions.add_argument("--rebuild-search", action="store_true", help="FTS5 indeksini tamamlanmış çıkarma işlerinden yeniden oluştur")
    actions.add_argument("--backup-dir", metavar="NEW_DIRECTORY", help="Yeni klasöre hash-manifestolu eksiksiz yedek oluştur")
    actions.add_argument("--verify-backup", metavar="DIRECTORY", help="Yedekteki nesneleri, SQLite ve FTS5 yapısını doğrula")
    actions.add_argument("--restore-backup", metavar="DIRECTORY", help="Yedeği yalnız yeni ve boş veri klasörüne geri yükle")
    parser.add_argument("--restore-to", metavar="NEW_DIRECTORY", help="--restore-backup ile zorunlu yeni hedef klasör")
    parser.add_argument("--kind", choices=["ALL","PDF","DOCX","TXT"], default="ALL", help="Arama tür filtresi")
    parser.add_argument("--limit", type=int, default=25, help="Arama sonuç sayısı (1–50)")
    parser.add_argument("--data-dir", metavar="PATH", help="Test veya taşınabilir yerel depo yolu")
    args = parser.parse_args(argv)
    if args.restore_to and not args.restore_backup:
        parser.error('--restore-to yalnız --restore-backup ile kullanılır')
    if args.restore_backup and not args.restore_to:
        parser.error('--restore-backup için --restore-to zorunludur')
    if args.backup_dir or args.verify_backup or args.restore_backup:
        svc = BackupService(args.data_dir or data_dir())
        try:
            if args.backup_dir: value = svc.create(args.backup_dir)
            elif args.verify_backup: value = svc.inspect(args.verify_backup)
            else: value = svc.restore(args.restore_backup,args.restore_to)
            print(json.dumps({'destination':str(value.destination),'documents':value.document_count,
                'versions':value.version_count,'objects':value.object_count,
                'total_bytes':value.total_bytes,'source_sha256':value.source_digest,
                'status':'VERIFIED'},ensure_ascii=True,sort_keys=True))
            return 0
        except (BackupError,OSError) as exc:
            print(json.dumps({'error':getattr(exc,'code','IO_ERROR'),'message':str(exc)},ensure_ascii=True))
            return 1
    if args.version:
        print(__version__)
        return 0
    if args.smoke:
        print(json.dumps({"version": __version__, "phase": "G09", "status": "sqlite-library-extraction-fts5-and-source-viewer", "extraction_ready": True, "fts5_capable": _fts5_capable(), "index_ready": False, "data_connected": False, "commercial_release": "HOLD"}, ensure_ascii=True, sort_keys=True))
        return 0
    if args.import_file or args.list_documents or args.library_stats or args.list_jobs or args.process_next or args.retry_job is not None or args.cancel_job is not None or args.search is not None or args.rebuild_search:
        service = IntakeService(args.data_dir)
        try:
            if args.import_file:
                item = service.import_document(args.import_file)
                result = {"operation": item.operation, "document_id": item.document_id, "revision": item.revision, "sha256": item.sha256, "kind": item.kind.value, "warning": item.warning}
            elif args.list_jobs:
                queue=JobQueue(service.db_path)
                result=[{"id":j.id,"document_id":j.document_id,"revision":j.revision,"status":j.status,"progress":f"{j.processed_units}/{j.total_units}","attempt":j.attempt,"error":j.error_code} for j in queue.list()]
            elif args.process_next:
                runner=Runner(service.root)
                queue=runner.queue
                # CLI process is a distinct worker owner; recover interrupted records before claiming.
                queue.recover()
                result={"processed":runner.run_one()}
            elif args.retry_job is not None:
                result={"requeued":JobQueue(service.db_path).retry(args.retry_job)}
            elif args.cancel_job is not None:
                result={"cancelled":JobQueue(service.db_path).cancel_pending(args.cancel_job)}
            elif args.search is not None:
                hits=SearchService(service.root).search(args.search,kind=args.kind,limit=args.limit)
                result=[{'rank':h.rank,'document_id':h.document_id,'name':h.name,'kind':h.kind,
                    'revision':h.revision,'sha256':h.sha256,'unit_kind':h.unit_kind,
                    'unit_number':h.unit_number,'char_start':h.char_start,'char_end':h.char_end,
                    'excerpt':h.exact_quote,'bm25_score':h.bm25_score,'verified':h.verified} for h in hits]
            elif args.rebuild_search:
                with connect(service.db_path) as conn,transaction(conn):result=rebuild_completed(conn)
            elif args.list_documents:
                result = [{"id":r.document_id,"name":r.name,"kind":r.kind,"revision":r.revision,"sha256":r.sha256,"archived":r.archived} for r in service.repository.list_documents(limit=200)]
            else:
                s = service.repository.stats()
                result = {"registered_documents": s.registered_documents,"stored_versions": s.stored_versions,"pending_index": s.pending_index,"indexed_documents": SearchService(service.root).stats()["indexed_documents"],"indexed_chunks": SearchService(service.root).stats()["indexed_chunks"]}
            print(json.dumps(result,ensure_ascii=True,sort_keys=True))
            return 0
        except Exception as exc:
            from .ingest.parsers import IntakeError
            if isinstance(exc, (IntakeError, SearchError, OSError, ValueError)):
                print(json.dumps({"error":getattr(exc,'code','IO_ERROR'),"message":str(exc)},ensure_ascii=True))
                return 1
            raise
    from .ui.app import run
    return run()
