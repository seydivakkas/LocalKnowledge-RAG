"""G08 independent *synthetic* multi-page PDF negative/regression corpus.

This verifies geometry/cross-parser agreement. It is NOT independent customer corpus.
"""
from __future__ import annotations
from pathlib import Path
import tempfile
import unittest

class G08PdfCorpus(unittest.TestCase):
    def test_24_page_crop_rotation_and_repeated_token(self):
        import pdfplumber,pypdfium2 as pdfium,fitz
        from pypdf import PdfReader,PdfWriter
        from reportlab.pdfgen.canvas import Canvas
        from localknowledge.viewer.worker import _viewport
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp); source=base/'base.pdf';multi=base/'multi.pdf'
            pdf=Canvas(str(source),pagesize=(600,800))
            pdf.setFont('Helvetica',11)
            pdf.drawString(83,698,'Koridor kaynagi ve bina mimarisi.')
            pdf.drawString(83,648,'Koridor kaynagi ve bina mimarisi.')
            pdf.showPage();pdf.save()
            w=PdfWriter()
            for idx in range(24):
                page=w.add_page(PdfReader(source).pages[0])
                if idx%2:
                    page.cropbox.lower_left=(60,38)
                    page.cropbox.upper_right=(545,758)
                page.rotate((idx%4)*90)
            w.write(str(multi))
            with pdfplumber.open(multi) as text, pdfium.PdfDocument(str(multi)) as raster, fitz.open(multi) as independent:
                self.assertEqual((len(text.pages),len(raster),len(independent)),(24,24,24))
                for idx in range(24):
                    with self.subTest(page=idx+1):
                        p=text.pages[idx];q=raster[idx];ref=independent[idx]
                        vp=_viewport(p,q)
                        # If a rotated, asymmetrically cropped page disagrees
                        # with independent geometry, NO highlight is allowed.
                        if idx % 2:
                            self.assertIsNone(vp)
                        else:
                            self.assertIsNotNone(vp)
                            self.assertAlmostEqual(vp[2],float(ref.rect.width),delta=.7)
                            self.assertAlmostEqual(vp[3],float(ref.rect.height),delta=.7)
                            self.assertTrue(vp[2]>0 and vp[3]>0)
                        extracted=p.extract_text().lower()
                        # pdfplumber reverses glyph order on rotated pages;
                        # never normalize offsets silently or fake positions.
                        self.assertEqual(extracted.count('koridor')+extracted.count('rodirok'),2)
                        self.assertEqual(ref.get_text().lower().count('koridor'),2)

    def test_bad_crop_fails_closed(self):
        import pdfplumber,pypdfium2 as pdfium
        from reportlab.pdfgen.canvas import Canvas
        from localknowledge.viewer.worker import _viewport
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'one.pdf';c=Canvas(str(path));c.drawString(80,720,'Verifiability');c.save()
            with pdfplumber.open(path) as pl,pdfium.PdfDocument(str(path)) as pd:
                class Forged:
                    cropbox=(999,999,9999,9999)
                    mediabox=pl.pages[0].mediabox
                    width=pl.pages[0].width
                    height=pl.pages[0].height
                self.assertIsNone(_viewport(Forged(),pd[0]))


if __name__=='__main__':unittest.main()
