"""Windows-only acceptance helpers. SKIP on Linux, never claim PASS on Windows."""
import os
import pathlib
import tempfile
import unittest

from localknowledge.viewer.sandbox import bounded_worker

@unittest.skipUnless(os.name=='nt','Windows suspended Job Object needs Windows runner')
class WindowsSuspendedJobTests(unittest.TestCase):
    def test_worker_success_and_timeout(self):
        import sys
        with tempfile.TemporaryDirectory() as temp:
            target=pathlib.Path(temp)/'ok.txt'
            program='from pathlib import Path;Path(%r).write_text("ok",encoding="utf8")' % str(target)
            result=bounded_worker([sys.executable,'-c',program],timeout=8,
                memory_bytes=512*1024**2,cwd=temp,output_path=target)
            self.assertTrue(result.ok,result)
            self.assertEqual(target.read_text(),'ok')
            missing=pathlib.Path(temp)/'no.txt'
            result=bounded_worker([sys.executable,'-c','import time;time.sleep(4)'],timeout=1,
                memory_bytes=512*1024**2,cwd=temp,output_path=missing)
            self.assertFalse(result.ok)
            self.assertEqual(result.code,'PDF_WORKER_TIMEOUT')

if __name__=='__main__':unittest.main()
