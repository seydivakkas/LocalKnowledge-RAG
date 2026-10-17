"""G08 offline, source-preserving backup and non-overwriting restore tests."""
from __future__ import annotations
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from localknowledge.ingest.service import IntakeService
from localknowledge.jobs.runner import Runner
from localknowledge.search.service import SearchService
from localknowledge.storage.backup import BackupError, BackupService, create_backup, restore_backup, inspect_backup
from localknowledge.storage.db import connect


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name)
        self.root=self.base/'library'
        self.intake=IntakeService(self.root)
        self.source=self.base/'şartname.txt'
        self.source.write_text('Koridor güvenlik testi.\nÇatı penceresi bilgisi.\n',encoding='utf-8')
        self.first=self.intake.import_document(self.source)

    def _index(self):
        self.assertTrue(Runner(self.root,poll_interval=.01).run_one())
        self.assertTrue(SearchService(self.root).search('koridor') or SearchService(self.root).search('pencere'))

    def test_backup_restore_with_rebuilt_search_index(self):
        self._index()
        before=self.source.read_bytes()
        backup=create_backup(self.root,self.base/'transport')
        self.assertEqual((backup.document_count,backup.version_count,backup.object_count),(1,1,1))
        self.assertEqual(inspect_backup(backup.destination).source_digest,backup.source_digest)
        restored=restore_backup(backup.destination,self.base/'fresh')
        hits=SearchService(restored.destination).search('koridor')
        self.assertEqual(len(hits),1)
        self.assertTrue(hits[0].verified)
        self.assertEqual(self.source.read_bytes(),before)
        with connect(restored.destination/'library.sqlite3') as db:
            self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(),[])
            self.assertEqual(db.execute('SELECT count(*) FROM search_chunks').fetchone()[0],2)

    def test_historic_document_revisions_and_objects_preserved(self):
        self.source.write_text('Dış cephe ve temel.\n',encoding='utf-8')
        new=self.intake.import_document(self.source)
        self.assertEqual(new.revision,2)
        result=create_backup(self.root,self.base/'snapshot')
        self.assertEqual((result.version_count,result.object_count),(2,2))
        restore_backup(self.base/'snapshot',self.base/'another')
        self.assertTrue((self.base/'another'/'objects'/self.first.sha256[:2]/(self.first.sha256+'.bin')).exists())
        self.assertTrue((self.base/'another'/'objects'/new.sha256[:2]/(new.sha256+'.bin')).exists())

    def test_same_backup_path_refused_without_changes(self):
        create_backup(self.root,self.base/'snapshot')
        marker=(self.base/'snapshot'/'manifest.json').read_bytes()
        with self.assertRaises(BackupError) as ctx:create_backup(self.root,self.base/'snapshot')
        self.assertEqual(ctx.exception.code,'DESTINATION_EXISTS')
        self.assertEqual(marker,(self.base/'snapshot'/'manifest.json').read_bytes())

    def test_restore_existing_target_even_empty_refused(self):
        create_backup(self.root,self.base/'snapshot')
        dest=self.base/'existing';dest.mkdir()
        with self.assertRaises(BackupError) as ctx:restore_backup(self.base/'snapshot',dest)
        self.assertEqual(ctx.exception.code,'DESTINATION_EXISTS')
        self.assertEqual(list(dest.iterdir()),[])

    def test_tampered_object_detected_before_target_created(self):
        b=create_backup(self.root,self.base/'snapshot')
        obj=self.base/'snapshot'/'objects'/self.first.sha256[:2]/(self.first.sha256+'.bin')
        obj.write_bytes(b'X' * obj.stat().st_size)
        with self.assertRaises(BackupError) as e:restore_backup(b.destination,self.base/'restored')
        self.assertEqual(e.exception.code,'HASH_MISMATCH')
        self.assertFalse((self.base/'restored').exists())

    def test_extra_file_or_symlink_rejected(self):
        create_backup(self.root,self.base/'snapshot')
        extraneous=self.base/'snapshot'/'bad.txt';extraneous.write_text('tamper')
        with self.assertRaises(BackupError) as e:inspect_backup(self.base/'snapshot')
        self.assertEqual(e.exception.code,'BACKUP_FILE_SET')
        extraneous.unlink()
        try:extraneous.symlink_to(self.base/'snapshot'/'library.sqlite3')
        except (NotImplementedError,OSError):self.skipTest('symlink unavailable')
        with self.assertRaises(BackupError) as ctx:inspect_backup(self.base/'snapshot')
        self.assertEqual(ctx.exception.code,'UNSAFE_BACKUP_ENTRY')

    def test_missing_manifest_makes_incomplete_backup_invalid(self):
        create_backup(self.root,self.base/'snapshot')
        (self.base/'snapshot'/'manifest.json').unlink()
        with self.assertRaises(BackupError):inspect_backup(self.base/'snapshot')

    def test_manifest_path_traversal_rejected(self):
        create_backup(self.root,self.base/'snapshot')
        m=self.base/'snapshot'/'manifest.json'
        doc=json.loads(m.read_text(encoding='utf-8'))
        doc['entries']['../forbidden']={'sha256':'0'*64,'bytes':1}
        m.write_text(json.dumps(doc),encoding='utf-8')
        with self.assertRaises(BackupError):inspect_backup(self.base/'snapshot')

    def test_intentionally_corrupt_live_object_does_not_produce_backup(self):
        obj=self.root/'objects'/self.first.sha256[:2]/(self.first.sha256+'.bin')
        obj.write_bytes(b'corruption')
        with self.assertRaises(BackupError) as e:create_backup(self.root,self.base/'snapshot')
        self.assertIn(e.exception.code,('OBJECT_CHANGED','UNSAFE_BACKUP_ENTRY'))
        self.assertFalse((self.base/'snapshot').exists())

    def test_restore_protects_live_data(self):
        create_backup(self.root,self.base/'snapshot')
        with self.assertRaises(BackupError) as e:BackupService(self.root).restore(self.base/'snapshot',self.root)
        self.assertEqual(e.exception.code,'LIVE_DATA_PROTECTED')

    def test_running_job_recovered_as_interrupted(self):
        with connect(self.intake.db_path) as db:
            db.execute("UPDATE index_jobs SET status='RUNNING'")
            db.commit()
        create_backup(self.root,self.base/'snapshot')
        restore_backup(self.base/'snapshot',self.base/'fresh')
        with connect(self.base/'fresh'/'library.sqlite3') as db:
            row=db.execute('SELECT status,error_code FROM index_jobs').fetchone()
            self.assertEqual(tuple(row),('INTERRUPTED','RESTORED_SNAPSHOT'))

    def test_unexpected_db_schema_rejected(self):
        with connect(self.intake.db_path) as db:
            db.execute('PRAGMA user_version=99')
            db.commit()
        with self.assertRaises(BackupError) as e:create_backup(self.root,self.base/'snapshot')
        self.assertEqual(e.exception.code,'UNSUPPORTED_SCHEMA')


if __name__=='__main__':unittest.main()
