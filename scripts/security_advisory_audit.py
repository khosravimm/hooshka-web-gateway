"""Query OSV for advisories affecting the exact direct dependency lock."""
from __future__ import annotations

import json
from pathlib import Path
from importlib.metadata import requires, version as installed_version
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
import requests

ROOT=Path(__file__).resolve().parents[1]
LOCK=ROOT/'requirements.lock'
OSV_URL='https://api.osv.dev/v1/querybatch'


def locked_rows():
    rows=[]
    for raw in LOCK.read_text(encoding='utf-8-sig').splitlines():
        line=raw.strip()
        if not line or line.startswith('#'):
            continue
        name, version=line.split('==',1)
        rows.append((name.strip(),version.strip()))
    return rows



def resolved_closure():
    roots=[name for name,_ in locked_rows()]
    queue=list(roots)
    seen={}
    while queue:
        raw=queue.pop(0)
        name=canonicalize_name(raw)
        if name in seen:
            continue
        try:
            ver=installed_version(raw)
        except Exception:
            continue
        seen[name]=(raw,ver)
        for req_text in requires(raw) or []:
            try:
                req=Requirement(req_text)
                if req.marker is not None and not req.marker.evaluate():
                    continue
                queue.append(req.name)
            except Exception:
                continue
    return sorted(seen.values(), key=lambda x: canonicalize_name(x[0]))


def audit(timeout=15):
    rows=resolved_closure()
    payload={'queries':[{'package':{'ecosystem':'PyPI','name':n},'version':v} for n,v in rows]}
    response=requests.post(OSV_URL,json=payload,timeout=timeout)
    response.raise_for_status()
    results=response.json().get('results') or []
    findings=[]
    for (name,version), item in zip(rows,results):
        for vuln in item.get('vulns') or []:
            findings.append({'package':name,'version':version,'id':vuln.get('id'),'aliases':vuln.get('aliases') or []})
    return {'source':'OSV','scope':'resolved_dependency_closure','packages_checked':len(rows),'direct_packages':len(locked_rows()),'findings':findings}


def main():
    try:
        result=audit()
    except Exception as exc:
        print(json.dumps({'source':'OSV','status':'UNAVAILABLE','error':type(exc).__name__}))
        return 2
    print(json.dumps(result,ensure_ascii=False))
    return 1 if result['findings'] else 0


if __name__=='__main__':
    raise SystemExit(main())
