"""G09 wheel audit: synthetic archives only, no customer or network data."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

SCRIPT = Path(__file__).resolve().parents[2] / "packaging" / "wheel_evidence.py"
spec = importlib.util.spec_from_file_location("lk_g09_wheel_audit", SCRIPT)
audit_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_module)


class WheelAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.wheels = self.root / "wheels"
        self.wheels.mkdir()
        self.plan = self.root / "runtime.txt"
        self.plan.write_text("fixturepkg==1.0.0\n", encoding="utf-8")
        self.native = self.root / "native.json"
        self.blob = b"fixture-binary-bytes"
        digest = hashlib.sha256(self.blob).hexdigest()
        self.native.write_text(json.dumps({"native_files": [
            {"path": "_internal/fixture.pyd", "sha256": digest},
            {"path": "LocalKnowledge.exe", "sha256": "0" * 64},
        ]}), encoding="utf-8")

    def build_wheel(self, *, include_notice=True):
        path = self.wheels / "fixturepkg-1.0.0-py3-none-any.whl"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("fixturepkg/fixture.pyd", self.blob)
            if include_notice:
                archive.writestr("fixturepkg-1.0.0.dist-info/licenses/LICENSE.txt", "Example fixture")
        return path

    def test_exact_byte_match_and_release_hold(self):
        self.build_wheel()
        proof = audit_module.audit(self.wheels, self.plan, self.native)
        self.assertEqual(proof["wheel_count"], 1)
        self.assertEqual(proof["matched_bundled_native_count"], 1)
        self.assertEqual(proof["bundled_native_count"], 2)
        self.assertEqual(proof["bundled_native"][0]["classification"], "BYTE_MATCH_WHEEL_CANDIDATE")
        self.assertEqual(proof["bundled_native"][1]["classification"], "UNMATCHED_REQUIRES_REVIEW")
        self.assertFalse(proof["legal_clearance"])
        self.assertEqual(proof["commercial_release"], "HOLD")

    def test_missing_wheel_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "Missing wheels"):
            audit_module.audit(self.wheels, self.plan, self.native)

    def test_missing_notices_are_reported_not_cleared(self):
        self.build_wheel(include_notice=False)
        proof = audit_module.audit(self.wheels, self.plan, self.native)
        self.assertTrue(proof["wheels"][0]["notice_review_required"])
        self.assertFalse(proof["legal_clearance"])

    def test_duplicate_requirement_fails_closed(self):
        self.plan.write_text("fixturepkg==1.0.0\nfixturepkg==1.0.0\n", encoding="utf-8")
        self.build_wheel()
        with self.assertRaisesRegex(ValueError, "Duplicate runtime"):
            audit_module.audit(self.wheels, self.plan, self.native)

    def test_unexpected_archive_fails_closed(self):
        self.build_wheel()
        with zipfile.ZipFile(self.wheels / "unrelated-1.0-py3-none-any.whl", "w") as z:
            z.writestr("unrelated/a.py", "pass")
        with self.assertRaisesRegex(ValueError, "Unexpected wheel"):
            audit_module.audit(self.wheels, self.plan, self.native)


if __name__ == "__main__":
    unittest.main()
