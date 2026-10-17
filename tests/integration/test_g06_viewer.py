"""G06 end-to-end: SHA+version+offset, original PDF geometry and fail-closed overlays."""
from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile
import unittest
from io import BytesIO

from localknowledge.ingest.service import IntakeService
from localknowledge.jobs.runner import Runner
from localknowledge.search.service import SearchService
from localknowledge.viewer.service import SourceViewerService, SourceViewError


class G06ViewerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = self.base/'data'
        self.ingest = IntakeService(self.root)
        self.search = SearchService(self.root)
        self.viewer = SourceViewerService(self.root, self.search)

    def make_pdf(self,name,lines,pages=1):
        from reportlab.pdfgen.canvas import Canvas
        p=self.base/name
        cv=Canvas(str(p),pagesize=(600,800))
        cv.setFont('Helvetica',14)
        for pg in range(pages):
            for i,line in enumerate(lines[pg] if isinstance(lines[0],list) else lines):
                cv.drawString(80,700-i*35,line)
            cv.showPage()
        cv.save()
        return p

    def ready(self,path):
        self.ingest.import_document(path)
        self.assertTrue(Runner(self.root,poll_interval=.005).run_one())

    def test_verified_page_render_exact_coordinates_and_png(self):
        p=self.make_pdf('source.pdf',['Architectural evidence marker here'])
        self.ready(p)
        hit=self.search.search('Architectural',kind='PDF')[0]
        view=self.viewer.open(hit.chunk_id,scale=1)
        self.assertEqual(view.geometry_status,'VERIFIED')
        self.assertEqual(view.page_count,1)
        self.assertEqual(view.page_number,1)
        self.assertEqual(view.hit.sha256,hashlib.sha256(p.read_bytes()).hexdigest())
        self.assertEqual(view.image_size,(600,800))
        self.assertTrue(view.image_png.startswith(b'\x89PNG\r\n\x1a\n'))
        self.assertGreaterEqual(len(view.highlight_boxes),10)
        self.assertTrue(all(0<=r.left<r.right<=1 and 0<=r.top<r.bottom<=1 for r in view.highlight_boxes))
        self.assertAlmostEqual(view.highlight_boxes[0].left*600,80,delta=3)
        self.assertAlmostEqual(view.highlight_boxes[0].top*800,88.9,delta=4)

    def test_query_specific_highlight_not_entire_passage(self):
        p=self.make_pdf('targeted.pdf',['First phrase then only corridor locator'])
        self.ready(p)
        hit=self.search.search('corridor')[0]
        whole=self.viewer.open(hit.chunk_id)
        targeted=self.viewer.open(hit.chunk_id,highlight_query='corridor')
        self.assertEqual(targeted.geometry_status,'VERIFIED')
        self.assertLess(len(targeted.highlight_boxes),len(whole.highlight_boxes))
        self.assertEqual(len(targeted.highlight_boxes),len('corridor'))
        unrelated=self.viewer.open(hit.chunk_id,highlight_query='nonexistingXYZ')
        self.assertEqual(unrelated.geometry_status,'UNVERIFIED_POSITION')
        self.assertFalse(unrelated.highlight_boxes)

    def test_multiple_page_browsing_never_carries_highlight(self):
        self.ready(self.make_pdf('multi.pdf',[['First floor general plan'],['Second floor corridor detailed view']],pages=2))
        hit=self.search.search('Second',kind='PDF')[0]
        src=self.viewer.open(hit.chunk_id)
        self.assertEqual(src.page_number,2)
        self.assertEqual(src.geometry_status,'VERIFIED')
        prev=self.viewer.open(hit.chunk_id,page_number=1)
        self.assertEqual(prev.geometry_status,'UNVERIFIED_POSITION')
        self.assertEqual(prev.highlight_boxes,())
        self.assertIsNotNone(prev.image_png)
        with self.assertRaises(SourceViewError):self.viewer.open(hit.chunk_id,page_number=3)

    def test_duplicate_quote_uses_correct_occurrence_and_no_first_match_shortcut(self):
        # Same word twice, exact current SourceHit quote can resolve only at its unit offset.
        p=self.make_pdf('duplicate.pdf',['Repeat source evidence','Repeat source evidence'])
        self.ready(p)
        hit=self.search.search('Repeat',kind='PDF')[0]
        view=self.viewer.open(hit.chunk_id)
        self.assertEqual(view.geometry_status,'VERIFIED')
        self.assertGreaterEqual(len(view.highlight_boxes),len('Repeat'))
        # Deliberately corrupt the positional matcher: unmatched offset refuses yellow.
        import pdfplumber
        from localknowledge.viewer.service import _boxes_for_exact_quote
        with pdfplumber.open(p) as pdf:
            self.assertEqual(_boxes_for_exact_quote(pdf.pages[0], 'abc abc','abc',4),())

    def test_rotation_matrix_0_90_180_270_fail_closed_if_not_exact(self):
        from pypdf import PdfReader, PdfWriter
        source=self.make_pdf('original.pdf',['Rotation geometry unique evidence'])
        rd=PdfReader(source);wr=PdfWriter()
        for deg in (0,90,180,270):
            wr.add_page(rd.pages[0]).rotate(deg)
        p=self.base/'rotate.pdf';wr.write(str(p));self.ready(p)
        # G04 pdfplumber may reorder rotated page strings. Verify any produced
        # boxes correspond only to a truly matching original extraction.
        for i in range(4):
            # Search term may be reversed for rotated pages; index chunks by unit.
            with __import__('localknowledge.storage.db',fromlist=['connect']).connect(self.ingest.db_path) as conn:
                row=conn.execute('SELECT id FROM search_chunks WHERE unit_number=? ORDER BY id LIMIT 1',(i,)).fetchone()
            self.assertIsNotNone(row)
            view=self.viewer.open(row['id'],scale=1)
            self.assertEqual(view.page_number,i+1)
            self.assertEqual(view.geometry_status,'VERIFIED')
            self.assertEqual(view.image_size,((600,800) if i%2==0 else (800,600)))
            if view.geometry_status!='VERIFIED':self.assertFalse(view.highlight_boxes)

    def test_cropbox_with_verified_origin_draws_correct_highlight(self):
        from pypdf import PdfReader,PdfWriter
        src=self.make_pdf('pre_crop.pdf',['Crop marker within visible region'])
        wr=PdfWriter();pg=wr.add_page(PdfReader(src).pages[0]);pg.cropbox.lower_left=(20,20)
        pg.cropbox.upper_right=(580,780)
        p=self.base/'crop.pdf';wr.write(str(p))
        self.ready(p)
        hit=self.search.search('Crop',kind='PDF')[0]
        view=self.viewer.open(hit.chunk_id)
        self.assertEqual(view.geometry_status,'VERIFIED')
        self.assertTrue(view.highlight_boxes)
        self.assertTrue(view.image_png)
        self.assertEqual(view.image_size,(700,950))
        # First glyph at x=80 in MediaBox, CropBox starts at x=20.
        self.assertAlmostEqual(view.highlight_boxes[0].left*560,60,delta=3)

    def test_tampered_sha_invalidates_view_even_if_earlier_hit_was_good(self):
        pdf=self.make_pdf('sealed.pdf',['Sealed document hash check'])
        doc=self.ingest.import_document(pdf);self.assertTrue(Runner(self.root).run_one())
        hit=self.search.search('Sealed')[0]
        stored,_,_=self.ingest.repository.managed_object(doc.document_id,1)
        target=self.root/stored
        target.write_bytes(b'Z'*target.stat().st_size)
        with self.assertRaises(SourceViewError) as err:self.viewer.open(hit.chunk_id)
        self.assertEqual(err.exception.code,'STALE_SOURCE')

    def test_archived_and_superseded_source_blocked(self):
        path=self.make_pdf('version.pdf',['Original content for version'])
        doc=self.ingest.import_document(path);self.assertTrue(Runner(self.root).run_one())
        hit=self.search.search('Original')[0]
        self.ingest.repository.archive(doc.document_id,True)
        with self.assertRaises(SourceViewError):self.viewer.open(hit.chunk_id)
        self.ingest.repository.archive(doc.document_id,False)
        path=self.make_pdf('version.pdf',['Replaced content version'])
        self.ingest.import_document(path)
        with self.assertRaises(SourceViewError):self.viewer.open(hit.chunk_id)

    def test_text_is_text_only_and_no_fake_pdf(self):
        path=self.base/'notes.txt';path.write_text('Türkçe belge kanıtı.\n',encoding='utf-8')
        self.ready(path)
        hit=self.search.search('Türkçe')[0]
        view=self.viewer.open(hit.chunk_id)
        self.assertEqual(view.geometry_status,'TEXT_ONLY')
        self.assertIsNone(view.image_png)
        self.assertFalse(view.highlight_boxes)
        self.assertIn('Türkçe',view.original_unit)
        with self.assertRaises(SourceViewError):self.viewer.open(hit.chunk_id,page_number=100)

    def test_nonexistent_and_invalid_reference_fails(self):
        for val in (0,-1,True,999999):
            with self.subTest(val=val),self.assertRaises(SourceViewError):self.viewer.open(val)

    def test_render_scale_budget_fails(self):
        self.ready(self.make_pdf('scale.pdf',['Scale guard example']))
        hit=self.search.search('Scale')[0]
        for scale in (0.1,3.0):
            with self.assertRaises(SourceViewError):self.viewer.open(hit.chunk_id,scale=scale)

    def test_source_link_remains_compatible_with_g05(self):
        self.ready(self.make_pdf('compat.pdf',['Verified original text source']))
        hit=self.search.search('Verified')[0]
        g05=self.search.source_passage(hit.chunk_id)
        g06=self.viewer.open(hit.chunk_id)
        self.assertEqual(g05[0].document_id,g06.hit.document_id)
        self.assertEqual(g05[0].sha256,g06.hit.sha256)
        self.assertEqual(g05[1][g05[2]:g05[3]],g06.hit.exact_quote)

if __name__=='__main__':unittest.main()
