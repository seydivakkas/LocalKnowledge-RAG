"""Frozen entry routing: silent workers must never open the GUI."""
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from localknowledge.runtime import dispatch_private_worker, worker_command

class WorkerRoutingTests(unittest.TestCase):
    def test_source_worker_uses_module(self):
        self.assertEqual(worker_command('pdf','request','reply','png',executable='python',frozen=False),
            ['python','-m','localknowledge.viewer.worker','request','reply','png'])
        self.assertEqual(worker_command('extract','source','TXT','out','progress',executable='python',frozen=False)[2],
            'localknowledge.jobs.worker')
    def test_frozen_worker_uses_private_flag(self):
        self.assertEqual(worker_command('pdf','a','b','c',executable='LocalKnowledge.exe',frozen=True),
            ['LocalKnowledge.exe','--internal-pdf-worker','a','b','c'])
        self.assertEqual(worker_command('extract','a','TXT','b','c',executable='LocalKnowledge.exe',frozen=True)[1],
            '--internal-extract-worker')
    def test_unknown_kind_rejected(self):
        with self.assertRaises(ValueError):worker_command('wrong')
    def test_private_dispatch_never_falls_through_cli(self):
        self.assertIsNone(dispatch_private_worker(['--gui']))
        with mock.patch('localknowledge.viewer.worker.main',return_value=2) as fn:
            self.assertEqual(dispatch_private_worker(['--internal-pdf-worker','a','b','c']),2)
            self.assertTrue(fn.called)
        with mock.patch('localknowledge.jobs.worker.main',return_value=3) as fn:
            self.assertEqual(dispatch_private_worker(['--internal-extract-worker','a','TXT','b','c']),3)
            self.assertTrue(fn.called)
    def test_actual_python_private_worker_process(self):
        with tempfile.TemporaryDirectory() as d:
            target=pathlib.Path(d)
            source=target/'src.bin';source.write_text('Koridor tasarımı\n',encoding='utf-8')
            out=target/'out.json';progress=target/'progress.json'
            p=subprocess.run([sys.executable,'-m','localknowledge','--internal-extract-worker',
                str(source),'TXT',str(out),str(progress)],capture_output=True,timeout=15)
            self.assertEqual(p.returncode,0,p.stderr)
            self.assertIn('Koridor',out.read_text(encoding='utf-8'))
