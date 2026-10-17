"""Build evidence only. Collect packaged files and dependency license metadata.

This file NEVER makes a legal-clearance determination; check obligations with
original upstream notices and actual Windows binaries before distribution.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.metadata as im
import json
from pathlib import Path


def filehash(p):
    with p.open('rb') as fh:
        h=hashlib.sha256()
        for b in iter(lambda:fh.read(1024*1024),b''):h.update(b)
    return h.hexdigest()


def collect(folder:Path):
    if not folder.is_dir():raise ValueError('Package dir missing')
    items=[];native=[]
    for f in sorted(x for x in folder.rglob('*') if x.is_file()):
        rel=f.relative_to(folder).as_posix();row={'path':rel,'size_bytes':f.stat().st_size,'sha256':filehash(f)}
        items.append(row)
        if f.suffix.lower() in ('.dll','.pyd','.exe','.so','.dylib'):
            native.append(row)
    installed=[]
    for pkg in sorted(im.distributions(),key=lambda d:(d.metadata.get('Name') or '').lower()):
        name=pkg.metadata.get('Name') or ''
        installed.append({'name':name,'version':pkg.version,'license_expression':pkg.metadata.get('License-Expression') or '',
            'license_declared':pkg.metadata.get('License') or '', 'home_page':pkg.metadata.get('Home-page') or ''})
    # Detecting installed development components != claiming they are bundled.
    return {'schema':1,'distribution_rights':'HOLD','legal_clearance':False,'licensee_approval':False,
        'total_files':len(items),'native_files':native,'files':items,'environment_distributions':installed,
        'note':'Manifest verifies packaged bytes only, not binary-to-source provenance, REDIST rights or license clearance.'}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('dist_dir');parser.add_argument('output')
    args=parser.parse_args();result=collect(Path(args.dist_dir));out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    print(f"{result['total_files']} files; {len(result['native_files'])} native; legal clearance HOLD")

if __name__=='__main__':main()
