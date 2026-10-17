"""G07: independent renderer geometry, language offsets and crash isolation."""
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from localknowledge.viewer.worker import _viewport,_term_positions
from localknowledge.viewer.sandbox import bounded_worker
from localknowledge.viewer.service import SourceViewerService, SourceViewError
from localknowledge.ingest.service import IntakeService
from localknowledge.jobs.runner import Runner
from localknowledge.search.service import SearchService


class G07UnitTests(unittest.TestCase):
    def test_turkish_casefold_has_no_offset_drift(self):
        self.assertEqual(_term_positions('İstanbul Izmir ızgara içerik','istanbul'),[(0,8)])
        self.assertEqual(_term_positions('İstanbul Izmir ızgara içerik','ızgara'),[(15,21)])
        self.assertEqual(_term_positions('İstanbul Izmir ızgara içerik','izmir'),[])
        self.assertEqual(_term_positions('İstanbul Izmir ızgara içerik','ızmir'),[(9,14)])
        self.assertEqual(_term_positions('ı i İ I','i'),[(2,3),(4,5)])
        self.assertEqual(_term_positions('ı i İ I','ı'),[(0,1),(6,7)])
        self.assertEqual(_term_positions('foo Straße','strasse'),[])  # no expanding casefold

    def test_worker_timeout_and_no_published_result(self):
        import sys
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            reply=root/'reply.json'
            result=bounded_worker([sys.executable,'-c','import time;time.sleep(5)'],
                timeout=1,memory_bytes=512*1024**2,cwd=root,output_path=reply)
            self.assertFalse(result.ok)
            self.assertEqual(result.code,'PDF_WORKER_TIMEOUT')
            self.assertFalse(reply.exists())

    def test_invalid_worker_cannot_claim_success(self):
        import sys
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);reply=root/'reply.json'
            result=bounded_worker([sys.executable,'-c','raise RuntimeError("bad")'],
                timeout=3,memory_bytes=512*1024**2,cwd=root,output_path=reply)
            self.assertFalse(result.ok)
            self.assertEqual(result.code,'PDF_WORKER_FAILED')

    def test_crop_aware_positions_match_independent_pymupdf(self):
        # fitz is test-only: NOT a runtime dependency or commercial inclusion.
        import pdfplumber,pypdfium2 as fu,fitz
        from reportlab.pdfgen.canvas import Canvas
        from pypdf import PdfReader,PdfWriter
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);source=root/'base.pdf';output=root/'crop.pdf'
            c=Canvas(str(source),pagesize=(600,800));c.setFont('Helvetica',14)
            c.drawString(80,700,'Cropbox check corridor');c.showPage();c.save()
            w=PdfWriter()
            for rotation in (0,90,180,270):
                pg=w.add_page(PdfReader(source).pages[0])
                pg.cropbox.lower_left=(60,40);pg.cropbox.upper_right=(540,760)
                pg.rotate(rotation)
            w.write(str(output))
            with pdfplumber.open(output) as pl,fu.PdfDocument(str(output)) as pdf,fitz.open(output) as reference:
                for n in range(4):
                    with self.subTest(rotation=n*90):
                        p=pl.pages[n];q=pdf[n];f=reference[n]
                        view=_viewport(p,q)
                        self.assertIsNotNone(view)
                        self.assertAlmostEqual(view[2],float(f.rect.width),delta=.6)
                        self.assertAlmostEqual(view[3],float(f.rect.height),delta=.6)
                        words=p.extract_words();target=next(z for z in words if z['text'] in ('Cropbox','xobporC'))
                        refword=next(z for z in f.get_text('words') if z[4]=='Cropbox')
                        from fitz import Rect
                        rotated=Rect(*refword[:4])*f.rotation_matrix
                        a=(target['x0']-view[0], target['top']-view[1],
                           target['x1']-view[0],target['bottom']-view[1])
                        # pdfplumber glyph top is usually slightly lower than
                        # PyMuPDF's font bbox; compare POSITION and extent
                        # within a safe 6pt difference (not pixel-perfect).
                        for x,y in zip(a,(rotated.x0,rotated.y0,rotated.x1,rotated.y1)):
                            self.assertAlmostEqual(x,y,delta=6.0)

    def test_unmatched_crop_geometry_fails_closed(self):
        from reportlab.pdfgen.canvas import Canvas
        import pdfplumber,pypdfium2 as fu
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'t.pdf';c=Canvas(str(p));c.drawString(70,700,'sample');c.save()
            with pdfplumber.open(p) as pl,fu.PdfDocument(str(p)) as pdf:
                self.assertIsNotNone(_viewport(pl.pages[0],pdf[0]))
                class ForgedPage:
                    cropbox=(10,10,100,100)
                    mediabox=pl.pages[0].mediabox
                    width=pl.pages[0].width
                    height=pl.pages[0].height
                self.assertIsNone(_viewport(ForgedPage(),pdf[0]))

if __name__=='__main__':unittest.main()
