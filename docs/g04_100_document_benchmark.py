"""No real users: deterministic, local 100 TXT synthetic documents and two workers."""
from pathlib import Path
from tempfile import TemporaryDirectory
from localknowledge.ingest.service import IntakeService
from localknowledge.jobs.runner import Runner
from localknowledge.storage.db import connect
import hashlib
import json
import time

with TemporaryDirectory() as tmp:
    base=Path(tmp);source=base/'inputs';source.mkdir()
    svc=IntakeService(base/'data');hashes={}
    for i in range(100):
        f=source/f'test_{i:03d}.txt'
        f.write_text(f'Sentetik dosya {i:03d}\nSadece test kaydı\n',encoding='utf-8')
        hashes[f]=hashlib.sha256(f.read_bytes()).hexdigest()
        svc.import_document(f)
    before=time.perf_counter()
    runner=Runner(svc.root,poll_interval=.02,timeout_seconds=30)
    runner.start(workers=2)
    try:
        deadline=time.monotonic()+90
        while time.monotonic()<deadline:
            stats=svc.repository.stats();states=svc.repository.extraction_statuses(tuple(r.document_id for r in svc.repository.list_documents(limit=200)))
            if all(s=='COMPLETED' for s in states.values()):break
            time.sleep(.12)
        elapsed=time.perf_counter()-before
    finally:runner.stop()
    items=svc.repository.list_documents(limit=200)
    with connect(svc.db_path) as conn:
        stats={r['status']:r['n'] for r in conn.execute('SELECT status,count(*) AS n FROM index_jobs GROUP BY status').fetchall()}
        spans=conn.execute('SELECT count(*) FROM extracted_spans').fetchone()[0]
        violations=conn.execute('PRAGMA foreign_key_check').fetchall()
    changed=[str(f) for f,h in hashes.items() if hashlib.sha256(f.read_bytes()).hexdigest()!=h]
    result={'synthetic_documents':len(items),'job_states':stats,'extracted_units':spans,'workers':2,
            'elapsed_seconds':round(elapsed,3),'modified_source_files':len(changed),'foreign_key_violations':len(violations),
            'search_fts_implemented':False,'environment':'Linux current container, not physical Windows'}
    print(json.dumps(result,ensure_ascii=False,indent=2))
    assert len(items)==100 and stats=={'COMPLETED':100} and spans==200 and not changed and not violations
