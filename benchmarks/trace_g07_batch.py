"""Phase-specific 100-document diagnostic; outputs truthful status even if timeout."""
from pathlib import Path
from tempfile import TemporaryDirectory
from localknowledge.ingest.service import IntakeService
from localknowledge.jobs.runner import Runner
from localknowledge.storage.db import connect
import hashlib,json,time,os

with TemporaryDirectory(prefix='g07perf-') as td:
 base=Path(td);root=base/'data';original=base/'orig';original.mkdir()
 svc=IntakeService(root);import_start=time.monotonic();hashes={};samples=[]
 for n in range(100):
  path=original/f'test_{n:03d}.txt';path.write_text(f'G07 sentetik test {n}\\nSadece test verisidir.\\n',encoding='utf-8')
  hashes[str(path)]=hashlib.sha256(path.read_bytes()).hexdigest()
  svc.import_document(path)
  if n in (0,9,24,49,74,99):
   samples.append({'documents':n+1,'elapsed_seconds':round(time.monotonic()-import_start,3)})
   print('IMPORT',samples[-1],flush=True)
 import_elapsed=time.monotonic()-import_start
 runner=Runner(root,timeout_seconds=30,poll_interval=.03)
 runner.start(workers=2);begin=time.monotonic();worker_sample=[];status={}
 try:
  while time.monotonic()-begin<85:
   with connect(root/'library.sqlite3') as conn:
    status={r['status']:r['n'] for r in conn.execute('SELECT status,count(*) as n FROM index_jobs GROUP BY status').fetchall()}
   if not worker_sample or time.monotonic()-begin - worker_sample[-1]['elapsed_seconds']>=5:
    worker_sample.append({'elapsed_seconds':round(time.monotonic()-begin,2),'states':status})
    print('WORK',worker_sample[-1],flush=True)
   if status.get('COMPLETED',0)==100:break
   time.sleep(.25)
 finally:runner.stop()
 changed=[f for f,h in hashes.items() if hashlib.sha256(Path(f).read_bytes()).hexdigest()!=h]
 result={'status':'PASS' if status.get('COMPLETED')==100 and not changed else 'INCOMPLETE',
         'documents':100,'workers':2,'import_seconds':round(import_elapsed,3),
         'worker_seconds':round(time.monotonic()-begin,3),'import_samples':samples,
         'worker_samples':worker_sample,'end_states':status,'source_changes':len(changed),
         'environment':'Linux container; not clean Windows release acceptance'}
 Path('/mnt/data/g07_benchmark_diagnostics.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
 print('RESULT',json.dumps(result),flush=True)
