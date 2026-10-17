"""G06 actual Tk source screen, tested only when a virtual/real display exists."""
import tempfile
import time
import tkinter as tk
import unittest
from pathlib import Path
from reportlab.pdfgen.canvas import Canvas
from localknowledge.application import AppServices
from localknowledge.jobs.runner import Runner
from localknowledge.ui.app import LocalKnowledgeApp
from localknowledge.ui.routes import RouteId


class G06SourceUiTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name)
        pdf=root/'source.pdf'
        cv=Canvas(str(pdf),pagesize=(600,800))
        cv.drawString(80,700,'Verified original source geometry')
        cv.showPage()
        cv.drawString(80,700,'Other page no evidence overlay')
        cv.save()
        self.services=AppServices(root=root/'data')
        self.services.intake.import_document(pdf)
        self.assertTrue(Runner(root/'data').run_one())
        self.hit=self.services.search.search('Verified')[0]
        try:self.app=LocalKnowledgeApp(services=self.services)
        except tk.TclError as exc:raise unittest.SkipTest(f'No display: {exc}')
        self.app.geometry('1440x900')
        self.addCleanup(self.app.destroy)
        self.addCleanup(self.services.runner.stop)

    def wait(self,fn):
        deadline=time.monotonic()+12
        while time.monotonic()<deadline:
            self.app.update()
            if fn():return True
            time.sleep(.025)
        return False

    def test_search_to_source_real_pdf_page_and_source_overlay(self):
        self.app.open_route(RouteId.SEARCH)
        panel=self.app.search_panel
        panel.query.set('Verified')
        panel.run_search()
        self.assertTrue(self.wait(lambda:len(panel.table.get_children())>0))
        item=panel.table.get_children()[0]
        panel.table.selection_set(item)
        panel.open_source()
        self.assertEqual(self.app.router.state.current_route, RouteId.SOURCE)
        self.assertEqual(self.app.source_query,'Verified')
        vp=self.app.source_panel
        self.assertTrue(self.wait(lambda:vp.preview is not None))
        self.assertEqual(vp.preview.geometry_status,'VERIFIED')
        self.assertEqual(len(vp.preview.highlight_boxes),len('Verified'))
        self.app.update()
        self.assertGreater(len(vp.canvas.find_withtag('verified-highlight')),0)
        vp.move(1)
        self.assertTrue(self.wait(lambda:vp.preview is not None and vp.preview.page_number==2))
        self.assertEqual(vp.preview.geometry_status,'UNVERIFIED_POSITION')
        self.assertEqual(vp.canvas.find_withtag('verified-highlight'),())

    def test_unselected_source_has_no_fabricated_document(self):
        self.assertTrue(self.app.open_route(RouteId.SOURCE))
        self.app.update()
        self.assertIsNone(self.app.source_panel.preview)
        self.assertEqual(self.app.source_panel.canvas.find_withtag('verified-highlight'),())

if __name__=='__main__':unittest.main()
