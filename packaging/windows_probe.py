"""G09: synthetic Windows portable EXE / PDF worker / source proof.

Developer/CI check, NOT end-user Windows acceptance.
"""
from __future__ import annotations
import argparse
from contextlib import closing
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from reportlab.pdfgen.canvas import Canvas


def call(exe:Path,*args:str):
    p=subprocess.run([str(exe),*args],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=100,text=True,encoding='utf-8',errors='replace')
    if p.returncode:raise AssertionError(f'{args[0]} failed: exit {p.returncode}; stderr suffix {p.stderr[-350:]}')
    return json.loads(p.stdout)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('exe');ap.add_argument('evidence_json');a=ap.parse_args()
    exe=Path(a.exe).resolve();assert exe.exists()
    with tempfile.TemporaryDirectory(prefix='lk-g09-ci-') as folder:
        root=Path(folder);db=root/'data';src=root/'source.pdf';canvas=Canvas(str(src));canvas.setFont('Helvetica',16);canvas.drawString(96,600,'Koridor plan area');canvas.showPage();canvas.save()
        imported=call(exe,'--data-dir',str(db),'--import-file',str(src))
        done=call(exe,'--data-dir',str(db),'--process-next')
        assert done['processed'] is True,done
        hits=call(exe,'--data-dir',str(db),'--search','Koridor')
        assert hits and hits[0]['verified'] and hits[0]['unit_number']==0,hits
        # Private PDF worker is executed via same frozen executable.
        digest=imported['sha256'];req=root/'request.json';reply=root/'reply.json';png=root/'page.png'
        import sqlite3
        with closing(sqlite3.connect(str(db/'library.sqlite3'))) as con:
            unit=con.execute('SELECT original_text FROM extracted_spans WHERE document_id=? AND revision=? ORDER BY unit_number LIMIT 1',(imported['document_id'],imported['revision'])).fetchone()[0]
        quote=hits[0]['excerpt'];start=unit.find(quote)
        assert start>=0
        req.write_text(json.dumps({'root':str(db),'sha256':digest,'full':unit,'quote':quote,'start':start,'unit_number':0,'page_number':1,'scale':1.0,'highlight_query':'Koridor'}),encoding='utf-8')
        worker=subprocess.run([str(exe),'--internal-pdf-worker',str(req),str(reply),str(png)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30)
        assert worker.returncode==0 and reply.exists() and png.exists(),f'PDF worker exit={worker.returncode}'
        data=json.loads(reply.read_text(encoding='utf-8'))
        assert data['sha256']==digest and data['page_number']==1 and data['status']=='VERIFIED',data
        backup=call(exe,'--data-dir',str(db),'--backup-dir',str(root/'backup'))
        restored=call(exe,'--restore-backup',str(root/'backup'),'--restore-to',str(root/'restored'))
        restored_hits=call(exe,'--data-dir',str(root/'restored'),'--search','Koridor')
        assert restored_hits and restored_hits[0]['verified']
        result={'status':'PASS','exe':exe.name,'synthetic_pdf_sha256':digest,'search_hits':len(hits),'source_verified':True,'frozen_extraction_worker':True,'frozen_pdf_worker':True,'backup_restore':True,'windows_end_user_acceptance':False,'commercial_release':'HOLD'}
        out=Path(a.evidence_json);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
