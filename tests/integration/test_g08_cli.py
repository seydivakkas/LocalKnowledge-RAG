"""Independent CLI roundtrip with named new restore data directory."""
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest

class TestG08CLI(unittest.TestCase):
    def test_cli_backup_inspect_restore_and_refuse_overwrite(self):
        from localknowledge.ingest.service import IntakeService
        with tempfile.TemporaryDirectory() as t:
            base=Path(t);source=base/'girdi.txt';source.write_text('Sadece sentetik test.\n',encoding='utf-8')
            IntakeService(base/'live').import_document(source)
            def call(*args):
                proc=subprocess.run([sys.executable,'-m','localknowledge','--data-dir',str(base/'live'),*args],
                                    capture_output=True,text=True,timeout=30)
                return proc.returncode,json.loads(proc.stdout)
            code,res=call('--backup-dir',str(base/'backup'))
            self.assertEqual(code,0,res)
            self.assertEqual(res['status'],'VERIFIED')
            code,res=call('--verify-backup',str(base/'backup'))
            self.assertEqual(code,0,res)
            code,res=call('--restore-backup',str(base/'backup'),'--restore-to',str(base/'restore'))
            self.assertEqual(code,0,res)
            self.assertTrue((base/'restore'/'library.sqlite3').is_file())
            code,res=call('--restore-backup',str(base/'backup'),'--restore-to',str(base/'restore'))
            self.assertEqual((code,res['error']),(1,'DESTINATION_EXISTS'))

if __name__=='__main__':unittest.main()
