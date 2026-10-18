"""Bounded subprocess worker, cooperative cancellation, crash recovery and thread safety."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
from .queue import JobQueue,Job


def parser_error_code(progress: Path) -> str:
    """Return a bounded non-sensitive error class; never expose source text/paths."""
    try:
        payload = json.loads(progress.read_text(encoding='utf-8'))
        name = payload.get('error_class', '')
        if isinstance(name, str) and name.isascii() and name.isidentifier() and 1 <= len(name) <= 48:
            return 'PARSER_' + name.upper()
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    return 'PARSER_FAILURE'
from ..storage.db import connect

class Runner:
    def __init__(self,root:Path|str,*,timeout_seconds:float=120.0,poll_interval:float=0.1):
        self.root=Path(root)
        self.queue=JobQueue(self.root/'library.sqlite3')
        self.timeout_seconds=timeout_seconds
        self.poll_interval=poll_interval
        self._quit=threading.Event()
        self._cancel:set[int]=set()
        self._lock=threading.Lock()
        self._threads:list[threading.Thread]=[]
        self._active:dict[int,subprocess.Popen]={}

    def start(self,workers:int=1):
        if not 1<=workers<=2:raise ValueError('En fazla iki paralel işçi desteklenir.')
        self.queue.recover()
        for i in range(workers):
            t=threading.Thread(target=self._loop,daemon=True,name=f'LK-G04-{i}')
            t.start();self._threads.append(t)

    def request_cancel(self,id:int)->bool:
        if self.queue.cancel_pending(id):return True
        with self._lock:
            self._cancel.add(id)
        return True

    def stop(self):
        self._quit.set()
        with self._lock:
            procs=list(self._active.values())
        for proc in procs:
            if proc.poll() is None:proc.terminate()
        for t in self._threads:t.join(timeout=4)

    def run_one(self)->bool:
        job=self.queue.claim()
        if job is None:return False
        self._run(job)
        return True

    def _loop(self):
        while not self._quit.is_set():
            if not self.run_one():self._quit.wait(0.2)

    def _managed_source(self,job:Job):
        with connect(self.queue.db_path) as conn:
            v=conn.execute('''SELECT v.object_relpath,v.byte_size,d.kind FROM versions v
                              JOIN documents d ON d.id=v.document_id WHERE v.document_id=? AND v.revision=?''',(job.document_id,job.revision)).fetchone()
        if not v:raise ValueError('SOURCE_MISSING')
        safe=f'objects/{job.sha256[:2]}/{job.sha256}.bin'
        if v['object_relpath']!=safe:raise ValueError('SOURCE_PATH_INVALID')
        path=self.root/safe
        if path.is_symlink() or not path.is_file() or path.stat().st_size!=v['byte_size']:raise ValueError('SOURCE_MISSING')
        sha=hashlib.sha256()
        with path.open('rb') as f:
            for block in iter(lambda:f.read(1024*1024),b''):sha.update(block)
        if sha.hexdigest()!=job.sha256:raise ValueError('SOURCE_HASH_MISMATCH')
        return path,v['kind']

    def _run(self,job:Job):
        proc=None
        try:
            src,kind=self._managed_source(job)
            with tempfile.TemporaryDirectory(prefix='.g04-',dir=self.root) as work:
                result=Path(work)/'result.json';progress=Path(work)/'progress.json'
                from ..runtime import worker_command
                cmd=worker_command('extract',str(src),kind,str(result),str(progress))
                # Never use shell=True. Frozen --onedir worker entrypoint shares this executable.
                proc=subprocess.Popen(cmd,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                                      start_new_session=(os.name=='posix'))
                with self._lock:self._active[job.id]=proc
                last=0;start=time.monotonic()
                while proc.poll() is None:
                    with self._lock:cancelled=job.id in self._cancel
                    if cancelled or self._quit.is_set():
                        proc.terminate()
                        try:proc.wait(timeout=2)
                        except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=2)
                        self.queue.state(job.id,'CANCELLED' if cancelled else 'INTERRUPTED','USER_CANCELLED' if cancelled else 'APPLICATION_STOP')
                        return
                    if time.monotonic()-start>self.timeout_seconds:
                        proc.kill();proc.wait(timeout=2)
                        self.queue.state(job.id,'FAILED','TIME_LIMIT')
                        return
                    if progress.exists():
                        try:
                            units=int(json.loads(progress.read_text(encoding='utf-8'))['units'])
                            if last<units<=job.total_units:
                                last=units;self.queue.progress(job.id,last)
                        except (OSError,ValueError,KeyError,TypeError):pass
                    time.sleep(self.poll_interval)
                # Shutdown/cancel may terminate the subprocess between polls.
                with self._lock: cancelled=job.id in self._cancel
                if cancelled or self._quit.is_set():
                    self.queue.state(job.id,'CANCELLED' if cancelled else 'INTERRUPTED','USER_CANCELLED' if cancelled else 'APPLICATION_STOP')
                    return
                if proc.returncode!=0 or not result.exists():
                    self.queue.state(job.id,'FAILED',parser_error_code(progress))
                    return
                if result.stat().st_size>24*1024*1024:
                    self.queue.state(job.id,'FAILED','OUTPUT_LIMIT');return
                spans=json.loads(result.read_text(encoding='utf-8'))['spans']
                # Rehash before the atomic publication of extracted spans.
                self._managed_source(job)
                with self._lock:cancelled=job.id in self._cancel
                if cancelled or self._quit.is_set():
                    self.queue.state(job.id,'CANCELLED' if cancelled else 'INTERRUPTED','USER_CANCELLED' if cancelled else 'APPLICATION_STOP')
                    return
                self.queue.complete(job,spans)
        except (OSError,ValueError,RuntimeError,KeyError,TypeError,OverflowError):
            self.queue.state(job.id,'FAILED','VALIDATION_OR_STORAGE_ERROR')
        finally:
            with self._lock:
                self._active.pop(job.id,None)
                self._cancel.discard(job.id)
            if proc is not None and proc.poll() is None:
                proc.kill();proc.wait()
