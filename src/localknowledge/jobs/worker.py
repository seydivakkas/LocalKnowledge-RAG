"""Isolated parser subprocess: bounded output; no DB access or network.

Run with `python -m localknowledge.jobs.worker source.bin PDF result.json progress.json`.
Only the owning runner should execute this module.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import sys
import tempfile
import zipfile

MAX_TOTAL_CHARS=5_000_000
MAX_UNIT_CHARS=5_000_000


def atomic_json(path:Path,record):
    with tempfile.NamedTemporaryFile(dir=path.parent,mode='w',encoding='utf-8',delete=False,suffix='.tmp') as file:
        p=Path(file.name)
        try:
            json.dump(record,file,ensure_ascii=False)
            file.flush()
            os.fsync(file.fileno())
        except BaseException:
            p.unlink(missing_ok=True)
            raise
    os.replace(p,path)


def read_source(path:Path,kind:str,progress_path:Path):
    total=0
    def check(s):
        nonlocal total
        total+=len(s)
        if total>MAX_TOTAL_CHARS or len(s)>MAX_UNIT_CHARS:raise ValueError('TEXT_LIMIT')
        return s
    def yield_progress(spans):
        atomic_json(progress_path,{'units':len(spans)})
    spans=[]
    if kind=='PDF':
        import pdfplumber
        with pdfplumber.open(str(path)) as doc:
            if not 0<len(doc.pages)<=300:raise ValueError('PAGE_LIMIT')
            for i,page in enumerate(doc.pages):
                value=check(page.extract_text() or '')
                spans.append({'kind':'PAGE','number':i,'start':0,'end':len(value),'text':value})
                yield_progress(spans)
    elif kind=='DOCX':
        import docx
        # G03 verified the ZIP entry bounds at import; re-check the managed object.
        with zipfile.ZipFile(path) as z:
            infos=z.infolist()
            if len(infos)>1000 or sum(i.file_size for i in infos)>75*1024*1024:raise ValueError('ZIP_LIMIT')
            if any(i.file_size>20*1024*1024 or (i.compress_size and i.file_size>max(i.compress_size*200,2_000_000)) for i in infos):raise ValueError('ZIP_LIMIT')
        obj=docx.Document(str(path));cursor=0
        for paragraph in obj.paragraphs:
            t=paragraph.text
            if t.strip():
                val=check(t)
                spans.append({'kind':'PARAGRAPH','number':len(spans),'start':cursor,'end':cursor+len(val),'text':val})
                yield_progress(spans)
            cursor+=len(t)+1
    elif kind=='TXT':
        raw=path.read_bytes()
        if len(raw)>50*1024*1024:raise ValueError('SIZE_LIMIT')
        try:t=raw.decode('utf-8-sig',errors='strict')
        except UnicodeDecodeError:t=raw.decode('cp1254',errors='strict')
        cursor=0
        for line in t.splitlines(keepends=True):
            val=line.rstrip('\r\n')
            if val.strip():
                check(val)
                spans.append({'kind':'PARAGRAPH','number':len(spans),'start':cursor,'end':cursor+len(val),'text':val})
                yield_progress(spans)
            cursor+=len(line)
    else:raise ValueError('KIND_NOT_SUPPORTED')
    return spans


def main():
    if len(sys.argv)!=5:return 2
    src,kind,out,progress=map(str,sys.argv[1:])
    try:
        # POSIX defense in depth; Windows resource boundaries remain a distinct release gate.
        if os.name=='posix':
            import resource
            mem=1536*1024*1024
            resource.setrlimit(resource.RLIMIT_AS,(mem,mem))
            resource.setrlimit(resource.RLIMIT_CPU,(115,120))
        result=read_source(Path(src),kind,Path(progress))
        atomic_json(Path(out),{'spans':result})
        return 0
    except BaseException:
        # Never print extracted customer content to shared logs.
        return 3

if __name__=='__main__':sys.exit(main())
