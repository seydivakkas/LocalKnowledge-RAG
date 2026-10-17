import tkinter as tk
import unittest
import tempfile
import time
from pathlib import Path
from localknowledge.ui.app import LocalKnowledgeApp
from localknowledge.ui.routes import RouteId
from localknowledge.ui.state import ViewStatus


class ShellUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from localknowledge.application import AppServices
            cls.tmp = tempfile.TemporaryDirectory()
            cls.app = LocalKnowledgeApp(services=AppServices(root=cls.tmp.name))
            cls.app.update()
        except tk.TclError as exc:
            if hasattr(cls,'tmp'):cls.tmp.cleanup()
            raise unittest.SkipTest(f"No interactive/display environment: {exc}")

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "app"):
            cls.app.services.runner.stop()
            cls.app.destroy()
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()
        import gc
        gc.collect()

    def tearDown(self):
        self.app.open_route(RouteId.HOME)
        self.app.update()

    def test_initial_home_and_actual_title(self):
        self.assertEqual(self.app.router.state.current_route, RouteId.HOME)
        self.assertIn("LocalKnowledge", self.app.title())
        self.assertIn("Ana Panel", self.app.topbar.title.cget("text"))

    def test_g03_real_routes_and_remaining_placeholders(self):
        for route in (RouteId.IMPORT, RouteId.LIBRARY, RouteId.HISTORY, RouteId.JOBS, RouteId.SEARCH):
            with self.subTest(route=route):
                self.assertTrue(self.app.open_route(route))
                self.assertEqual(self.app.router.state.view_status, ViewStatus.EMPTY)
                self.app.update_idletasks()
        self.assertTrue(self.app.open_route(RouteId.SOURCE))
        self.assertEqual(self.app.router.state.view_status, ViewStatus.EMPTY)
        self.assertTrue(self.app.open_route(RouteId.BACKUP))
        self.assertEqual(self.app.router.state.view_status, ViewStatus.EMPTY)

    def test_model_pages_disabled(self):
        self.assertFalse(self.app.open_route(RouteId.GROUNDED))
        self.assertFalse(self.app.open_route(RouteId.OCR))
        self.assertEqual(self.app.sidebar.nav_buttons[RouteId.GROUNDED].cget("state"), "disabled")

    def test_about_and_return(self):
        self.assertTrue(self.app.open_route(RouteId.ABOUT))
        self.assertEqual(self.app.topbar.title.cget("text"), "Hakkında")
        self.assertTrue(self.app.open_route(RouteId.HOME))
        self.assertEqual(self.app.topbar.title.cget("text"), "Ana Panel")

    def test_keyboard_shortcuts_navigate_to_truthful_state(self):
        self.app.event_generate("<Control-o>")
        self.app.update()
        self.assertEqual(self.app.router.state.current_route, RouteId.IMPORT)
        self.assertEqual(self.app.router.state.view_status, ViewStatus.EMPTY)

    def test_real_async_import_library_and_dashboard(self):
        fixture = Path(self.tmp.name) / 'Sentetik_Belge.txt'
        fixture.write_text('Bu test belgesi gerçektir ama sentetiktir.\n', encoding='utf-8')
        self.app.open_route(RouteId.IMPORT)
        panel = self.app.import_panel
        panel.set_files([str(fixture)])
        panel.start()
        deadline = time.monotonic() + 6.0
        while panel.busy and time.monotonic() < deadline:
            self.app.update()
            time.sleep(0.02)
        self.assertFalse(panel.busy)
        self.app.open_route(RouteId.LIBRARY)
        self.app.update_idletasks()
        records = list(self.app.library_panel.records.values())
        self.assertTrue(any(r.name == fixture.name for r in records))
        self.assertGreaterEqual(self.app.services.dashboard.summary().registered_documents, 1)
        self.assertTrue(self.app.services.intake.verify(records[0].document_id,records[0].revision))

    def test_g05_ui_search_and_verified_local_source(self):
        src=Path(self.tmp.name)/'Arama_G05_sentetik.txt'
        src.write_text('Türkçe kaynak doğrulaması için koridor analizi.\n',encoding='utf-8')
        self.app.services.intake.import_document(src)
        deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            self.app.update()
            if any(j.status=='COMPLETED' for j in self.app.services.jobs.list()):break
            time.sleep(.03)
        self.assertTrue(any(j.status=='COMPLETED' for j in self.app.services.jobs.list()))
        self.assertTrue(self.app.open_route(RouteId.SEARCH))
        panel=self.app.search_panel
        panel.query.set('koridor');panel.run_search()
        deadline=time.monotonic()+8
        while time.monotonic()<deadline and (panel._busy or not panel.table.get_children()):
            self.app.update();time.sleep(.02)
        self.assertGreater(len(panel.table.get_children()),0)
        first=panel.table.get_children()[0]
        panel.table.selection_set(first)
        detail=self.app.services.search.source_passage(int(first))
        self.assertIsNotNone(detail)
        self.assertEqual(detail[1][detail[2]:detail[3]],detail[0].exact_quote)
        panel.open_source()
        self.app.update()
        self.assertEqual(self.app.router.state.current_route, RouteId.SOURCE)
        self.assertEqual(self.app.source_chunk_id, int(first))
        self.assertEqual(self.app.source_panel.chunk_id, int(first))

    def test_minimum_geometry(self):
        self.app.geometry("1100x720")
        self.app.update()
        self.assertGreaterEqual(self.app.winfo_width(), 1100)
        self.assertGreaterEqual(self.app.winfo_height(), 720)
