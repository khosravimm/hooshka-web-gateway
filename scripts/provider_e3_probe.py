"""Run one governed E3 reliability window; this script never claims E3 by itself."""
from __future__ import annotations

import argparse, json, time, sys
from pathlib import Path
import requests

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from core.reliability import ReliabilityPolicy, evaluate_window


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--provider',required=True)
    ap.add_argument('--window-id',required=True)
    ap.add_argument('--base-url',default='http://127.0.0.1:5080')
    ap.add_argument('--probes',type=int,default=3)
    ap.add_argument('--spacing',type=float,default=3.0)
    args=ap.parse_args()
    policy=ReliabilityPolicy(probes_per_window=args.probes)
    records=[]
    for idx in range(args.probes):
        r=requests.post(f"{args.base_url}/panel/api/providers/{args.provider}/readiness/probe",json={'execution_authority':'automated_validation','ttl_seconds':300},timeout=120)
        r.raise_for_status(); record=r.json(); records.append(record)
        print(json.dumps({'probe':idx+1,'state':record.get('state'),'duration_ms':record.get('duration_ms')},ensure_ascii=False),flush=True)
        if idx+1 < args.probes: time.sleep(args.spacing)
    result=evaluate_window(records,policy)
    out=ROOT/'.runtime-dev'/'reliability'; out.mkdir(parents=True,exist_ok=True)
    path=out/f"{args.provider}-{args.window_id}.json"
    payload={'window_id':args.window_id,'policy':policy.__dict__,'records':records,'window_evaluation':result,'evidence_level':'E2_REPEATED_WINDOW'}
    path.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'window_evaluation':result,'evidence_path':str(path),'note':'One window cannot authorize E3.'},ensure_ascii=False),flush=True)
    return 0 if result['passed'] else 1


if __name__=='__main__':
    raise SystemExit(main())
