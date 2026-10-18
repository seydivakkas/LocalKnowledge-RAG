"""G09 hash-lock and notice staging tests; synthetic wheels only."""
from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
import zipfile

SCRIPT = Path(__file__).resolve().parents[2] / "packaging" / "wheelhouse_stage.py"
spec = importlib.util.spec_from_file_location("lk_wheelhouse_stage", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class RuntimeWheelhouseStageTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.wheels = self.root / "wheels"
        self.wheels.mkdir()
        self.pins = self.root / "pins.txt"
        self.pins.write_text("fixturepkg==1.0.0\n", encoding="utf-8")

    def wheel(self, notice=True, unsafe=False):
        path = self.wheels / "fixturepkg-1.0.0-py3-none-any.whl"
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("fixturepkg/__init__.py", "pass")
            if notice:
                z.writestr("fixturepkg-1.0.0.dist-info/licenses/LICENSE.txt", "Synthetic notice")
            if unsafe:
                z.writestr("../LICENSE.txt", "unsafe")
        return path

    def test_hash_lock_matches_exact_wheel(self):
        wheel = self.wheel()
        out = self.root / "locked.txt"
        result = mod.lock(self.wheels, self.pins, out)
        self.assertEqual(result["count"], 1)
        self.assertIn("fixturepkg==1.0.0 --hash=sha256:" + hashlib.sha256(wheel.read_bytes()).hexdigest(), out.read_text())

    def test_stage_notice_bytes_and_holds_rights(self):
        self.wheel()
        dest = self.root / "dist" / "THIRD_PARTY_NOTICES"
        result = mod.stage_notices(self.wheels, self.pins, dest)
        record = result["distributions"][0]["notices"][0]
        self.assertEqual((dest / record["packaged_path"]).read_text(), "Synthetic notice")
        self.assertEqual(result["missing_notice_packages"], [])
        self.assertFalse(result["legal_clearance"])
        self.assertEqual(result["commercial_release"], "HOLD")
        with self.assertRaises(FileExistsError):
            mod.stage_notices(self.wheels, self.pins, dest)

    def test_no_notice_is_not_license_clearance(self):
        self.wheel(notice=False)
        result = mod.stage_notices(self.wheels, self.pins, self.root / "notices")
        self.assertEqual(result["missing_notice_packages"], ["fixturepkg"])
        self.assertFalse(result["legal_clearance"])

    def test_archive_path_traversal_is_rejected(self):
        self.wheel(unsafe=True)
        with self.assertRaisesRegex(ValueError, "Unsafe wheel archive"):
            mod.lock(self.wheels, self.pins, self.root / "lock.txt")

    def test_missing_or_unexpected_wheel_fails(self):
        with self.assertRaisesRegex(ValueError, "Missing wheels"):
            mod.lock(self.wheels, self.pins, self.root / "locked.txt")
        self.wheel()
        with zipfile.ZipFile(self.wheels / "unexpected-1.0.0-py3-none-any.whl", "w") as archive:
            archive.writestr("unrelated/__init__.py", "pass")
        with self.assertRaisesRegex(ValueError, "Unexpected"):
            mod.lock(self.wheels, self.pins, self.root / "locked.txt")

    def test_unpinned_or_duplicate_requirement_fails(self):
        self.pins.write_text("fixturepkg>=1.0\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Expected one exact"):
            mod.lock(self.wheels, self.pins, self.root / "locked.txt")
        self.pins.write_text("fixturepkg==1.0.0\nfixturepkg==1.0.0\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Duplicate distribution"):
            mod.lock(self.wheels, self.pins, self.root / "locked.txt")


if __name__ == "__main__":
    unittest.main()
