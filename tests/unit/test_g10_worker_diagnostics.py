"""G10 sanitized parser failure diagnostics: never persist exception messages or user paths."""
from __future__ import annotations
import json
from pathlib import Path
import sys
import tempfile
import unittest
from localknowledge.jobs import worker
from localknowledge.jobs.runner import parser_error_code


class WorkerFailureDiagnosticsTests(unittest.TestCase):
    def test_missing_file_reports_class_not_sensitive_path(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            private_path = root / "private-customer-name-and-email.txt"
            output = root / "result.json"
            progress = root / "progress.json"
            old = sys.argv
            try:
                sys.argv = ["worker", str(private_path), "TXT", str(output), str(progress)]
                self.assertEqual(worker.main(), 3)
            finally:
                sys.argv = old
            raw = progress.read_text(encoding="utf-8")
            self.assertNotIn(private_path.name, raw)
            self.assertEqual(json.loads(raw), {"units": 0, "error_class": "FileNotFoundError"})
            self.assertEqual(parser_error_code(progress), "PARSER_FILENOTFOUNDERROR")
            self.assertFalse(output.exists())

    def test_untrusted_error_class_cannot_be_logged(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "progress.json"
            self.assertEqual(parser_error_code(p), "PARSER_FAILURE")
            p.write_text(json.dumps({"error_class": "FileNotFoundError user@private.com"}), encoding="utf-8")
            self.assertEqual(parser_error_code(p), "PARSER_FAILURE")
            p.write_text(json.dumps({"error_class": {"internal": "secret"}}), encoding="utf-8")
            self.assertEqual(parser_error_code(p), "PARSER_FAILURE")
