"""G04: durable extraction, staging, source invariants, migration and recoverability."""
import hashlib
import json
import sqlite3
import tempfile
import threading
import time
import unittest
from pathlib import Path
from localknowledge.ingest.service import IntakeService
from localknowledge.jobs.queue import JobQueue
from localknowledge.jobs.runner import Runner
from localknowledge.storage.db import connect,SCHEMA

class G04Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)/'app'
        self.svc=IntakeService(self.root)
        self.jobs=JobQueue(self.svc.db_path)
    def tearDown(self):self.tmp.cleanup()
    def sample(self,name='ornek.txt',text='Merhaba Türkiye\nİkinci paragraf\n'):
        p=Path(self.tmp.name)/name;p.write_text(text,encoding='utf-8');return p
    def getjob(self):return self.jobs.list()[0]
    def extract(self,workers=1,timeout=15):
        runner=Runner(self.root,timeout_seconds=timeout,poll_interval=.01)
        runner.start(workers=workers)
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            js=self.jobs.list()
            if js and all(j.status not in ('PENDING','RUNNING') for j in js):break
            time.sleep(.03)
        runner.stop()
        return self.jobs.list()

    def test_import_atomic_job_and_completed_text(self):
        p=self.sample();original=hashlib.sha256(p.read_bytes()).hexdigest()
        r=self.svc.import_document(p)
        j=self.getjob()
        self.assertEqual((j.sha256,j.total_units,j.status),(original,2,'PENDING'))
        jobs=self.extract()
        self.assertEqual(jobs[0].status,'COMPLETED')
        self.assertEqual(jobs[0].processed_units,2)
        with connect(self.svc.db_path) as conn:
            spans=conn.execute('SELECT * FROM extracted_spans ORDER BY unit_number').fetchall()
            self.assertEqual([s['original_text'] for s in spans],['Merhaba Türkiye','İkinci paragraf'])
            self.assertEqual([s['char_start'] for s in spans],[0,16])
            self.assertEqual(conn.execute("SELECT count(*) FROM sqlite_master WHERE name='chunks_fts'").fetchone()[0],0)
        self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),original)
        self.assertTrue(self.svc.verify(r.document_id,r.revision))
        self.assertEqual(self.svc.repository.stats().pending_index,0) # G04 completed and G05 indexed
        from localknowledge.search.service import SearchService
        self.assertEqual(SearchService(self.root).stats()['indexed_documents'],1)

    def test_idempotence_new_revision_and_old_source_never_current(self):
        p=self.sample()
        first=self.svc.import_document(p)
        self.svc.import_document(p)
        self.assertEqual(len(self.jobs.list()),1)
        p.write_text('Yeni sürüm\n',encoding='utf-8')
        second=self.svc.import_document(p)
        self.assertEqual(second.revision,2)
        self.assertEqual(len(self.jobs.list()),2)
        old=next(j for j in self.jobs.list() if j.revision==1)
        self.assertEqual(old.status,'SUPERSEDED')
        self.assertFalse(self.jobs.retry(old.id))
        self.assertEqual(self.extract()[0].status,'COMPLETED')
        self.assertTrue(self.svc.verify(first.document_id,1))

    def test_v1_to_v2_migration_preserves_rows(self):
        path=self.root/'library.sqlite3';path.parent.mkdir(parents=True,exist_ok=True)
        db=sqlite3.connect(path)
        db.executescript(SCHEMA)
        db.execute('PRAGMA user_version=1')
        db.execute("INSERT INTO documents(id,name,kind,current_revision) VALUES('demo','doc.txt','TXT',1)")
        db.execute("INSERT INTO versions(document_id,revision,sha256,byte_size,object_relpath,paragraph_count,original_name) VALUES('demo',1,?,10,?,1,'doc.txt')",('a'*64,'objects/aa/'+('a'*64)+'.bin'))
        db.commit();db.close()
        with connect(path) as conn:
            self.assertEqual(conn.execute('PRAGMA user_version').fetchone()[0],3)
            self.assertEqual(conn.execute('SELECT count(*) FROM documents').fetchone()[0],1)
            row=conn.execute('SELECT * FROM index_jobs').fetchone()
            self.assertEqual((row['document_id'],row['status'],row['total_units']),('demo','PENDING',1))
        with connect(path) as conn:self.assertEqual(conn.execute('SELECT count(*) FROM index_jobs').fetchone()[0],1)

    def test_pending_cancel_then_retry(self):
        self.svc.import_document(self.sample());job=self.getjob()
        self.assertTrue(self.jobs.cancel_pending(job.id))
        self.assertFalse(self.jobs.claim())
        self.assertTrue(self.jobs.retry(job.id))
        self.assertEqual(self.extract()[0].status,'COMPLETED')

    def test_running_crash_recovery_and_retry(self):
        self.svc.import_document(self.sample());job=self.jobs.claim()
        self.assertEqual(job.status,'RUNNING')
        self.assertEqual(self.jobs.recover(),1)
        self.assertEqual(self.getjob().status,'INTERRUPTED')
        self.assertTrue(self.jobs.retry(job.id))
        self.assertEqual(self.extract()[0].status,'COMPLETED')

    def test_corrupted_managed_object_fails_closed(self):
        r=self.svc.import_document(self.sample());rel,_,_=self.svc.repository.managed_object(r.document_id,r.revision)
        path=self.root/rel;path.write_bytes(b'not original')
        self.assertEqual(self.extract()[0].status,'FAILED')
        with connect(self.svc.db_path) as conn:self.assertEqual(conn.execute('SELECT count(*) FROM extracted_spans').fetchone()[0],0)

    def test_two_workers_no_double_claim(self):
        for n in range(12):self.svc.import_document(self.sample(f'doc{n}.txt',f'Kayıt {n} içerik.\n'))
        jobs=self.extract(workers=2)
        self.assertEqual(len(jobs),12)
        self.assertEqual({j.status for j in jobs},{'COMPLETED'})
        self.assertEqual({j.attempt for j in jobs},{1})
        with connect(self.svc.db_path) as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM extracted_spans').fetchone()[0],12)

    def test_archived_document_not_claimed(self):
        r=self.svc.import_document(self.sample())
        self.svc.repository.archive(r.document_id,True)
        self.assertIsNone(self.jobs.claim())
        self.assertEqual(self.svc.repository.stats().pending_index,0)

    def test_old_revision_completes_cannot_publish(self):
        p=self.sample();first=self.svc.import_document(p)
        job=self.jobs.claim();p.write_text('Yeni\n',encoding='utf-8');self.svc.import_document(p)
        with self.assertRaises(RuntimeError):self.jobs.complete(job,[{'kind':'PARAGRAPH','number':0,'start':0,'end':3,'text':'abc'}, {'kind':'PARAGRAPH','number':1,'start':4,'end':7,'text':'def'}])
        with connect(self.svc.db_path) as conn:self.assertEqual(conn.execute('SELECT count(*) FROM extracted_spans').fetchone()[0],0)

if __name__=='__main__':unittest.main()

# Multi-format extraction tests are independently executed in the same test runner.
class G04Formats(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name)
        self.svc=IntakeService(self.base/'app')
    def tearDown(self):self.tmp.cleanup()

    def assert_extraction(self,path,expected_unit,expected_text):
        imported=self.svc.import_document(path)
        worker=Runner(self.svc.root,timeout_seconds=25,poll_interval=.01)
        self.assertTrue(worker.run_one())
        with connect(self.svc.db_path) as conn:
            j=conn.execute('SELECT * FROM index_jobs').fetchone()
            self.assertEqual(j['status'],'COMPLETED')
            units=conn.execute('SELECT * FROM extracted_spans ORDER BY unit_number').fetchall()
            self.assertEqual(units[0]['unit_kind'],expected_unit)
            self.assertIn(expected_text,units[0]['original_text'])
        self.assertTrue(self.svc.verify(imported.document_id,imported.revision))

    def test_pdf_two_physical_pages(self):
        from reportlab.pdfgen.canvas import Canvas
        file=self.base/'sentetik.pdf'
        pdf=Canvas(str(file));pdf.drawString(85,730,'LocalKnowledge Sentetik PDF Page One')
        pdf.showPage();pdf.drawString(85,730,'Second page');pdf.save()
        self.assert_extraction(file,'PAGE','LocalKnowledge')
        with connect(self.svc.db_path) as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM extracted_spans').fetchone()[0],2)

    def test_docx_true_paragraphs_not_fake_pages(self):
        from docx import Document
        file=self.base/'sentetik.docx';doc=Document();doc.add_paragraph('Birinci sentetik paragraf')
        doc.add_paragraph('');doc.add_paragraph('İkinci paragraf');doc.save(file)
        self.assert_extraction(file,'PARAGRAPH','Birinci')
        with connect(self.svc.db_path) as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM extracted_spans').fetchone()[0],2)
            self.assertEqual(conn.execute('SELECT page_count FROM versions').fetchone()[0],None)
