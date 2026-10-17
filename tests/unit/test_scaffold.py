import io
import os
import tempfile
from pathlib import Path
from unittest.mock import patch
import json
from contextlib import redirect_stdout
import unittest
from localknowledge.application import AppServices, DashboardService
from localknowledge.config import data_dir
from localknowledge.cli import main
from localknowledge.ui.routes import ROUTES, ROUTE_MAP, RouteId
from localknowledge.ui.state import Router, ViewStatus
from localknowledge.ui.theme import TOKENS


class ScaffoldTests(unittest.TestCase):
    def test_smoke_is_truthful(self):
        out = io.StringIO()
        with redirect_stdout(out): self.assertEqual(main(["--smoke"]), 0)
        proof = json.loads(out.getvalue())
        self.assertEqual(proof["phase"], "G08")
        self.assertTrue(proof["index_ready"])
        self.assertFalse(proof["data_connected"])
        self.assertEqual(proof["commercial_release"], "HOLD")
        self.assertIsInstance(proof["fts5_capable"], bool)

    def test_user_data_path_is_local_and_not_written(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"LOCALKNOWLEDGE_DATA_DIR": tmp}):
            self.assertEqual(data_dir(), Path(tmp).resolve())
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_version_no_gui(self):
        out = io.StringIO()
        with redirect_stdout(out): self.assertEqual(main(["--version"]), 0)
        self.assertIn("dev0", out.getvalue())

    def test_dashboard_does_not_forge_zero_counts(self):
        summary = DashboardService().summary()
        self.assertFalse(summary.available)
        self.assertIsNone(summary.indexed_documents)
        self.assertIsNone(summary.indexed_chunks)
        with tempfile.TemporaryDirectory() as tmp:
            actual = AppServices(root=tmp).dashboard.summary()
            self.assertTrue(actual.available)
            self.assertEqual(actual.registered_documents,0)
            self.assertEqual(actual.indexed_documents,0)
            self.assertEqual(actual.indexed_chunks,0)

    def test_all_route_ids_unique(self):
        self.assertEqual(len(ROUTES), len(ROUTE_MAP))
        self.assertEqual(len(ROUTES), 16)

    def test_phase_gated_routes(self):
        router = Router()
        self.assertEqual(router.state.current_route, RouteId.HOME)
        self.assertTrue(router.open(RouteId.IMPORT))
        self.assertEqual(router.state.view_status, ViewStatus.EMPTY)
        self.assertFalse(router.open(RouteId.GROUNDED))
        self.assertEqual(router.state.current_route, RouteId.IMPORT)
        self.assertTrue(router.open(RouteId.HOME))
        self.assertEqual(router.state.view_status, ViewStatus.EMPTY)

    def test_tokens_reproduce_design_system(self):
        self.assertEqual(TOKENS["nav"], "#132238")
        self.assertEqual(TOKENS["primary"], "#246BDA")
        self.assertEqual(TOKENS["canvas"], "#F4F7FB")
