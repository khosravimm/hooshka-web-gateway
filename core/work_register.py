from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

REGISTER_PATH = Path(__file__).resolve().parents[1] / "docs" / "governance" / "HWG_REMAINING_WORK_REGISTER.json"
REQUIRED = {"id","title","area","status","priority","source","depends_on","target_version","evidence_required","exit_criteria"}
VALID_STATUS = {"OPEN","IN_PROGRESS","PARTIAL","BLOCKED","HOLD","DONE"}

def load_register(path: str | Path = REGISTER_PATH) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))

def validate_register(doc: dict[str, Any]) -> list[str]:
    errors=[]; ids=[]
    for idx,item in enumerate(doc.get("items") or []):
        missing=sorted(REQUIRED-set(item));
        if missing: errors.append(f"item[{idx}] missing: {','.join(missing)}"); continue
        ids.append(item["id"])
        if item["status"] not in VALID_STATUS: errors.append(f"{item['id']} invalid status")
        if not item["source"]: errors.append(f"{item['id']} missing source")
        if not item["exit_criteria"]: errors.append(f"{item['id']} missing exit criteria")
        if not item["evidence_required"]: errors.append(f"{item['id']} missing evidence requirement")
        if item["status"] == "DONE":
            if not item.get("evidence"): errors.append(f"{item['id']} DONE without evidence")
            if not item.get("completed_at"): errors.append(f"{item['id']} DONE without completed_at")
    dup=[x for x,c in Counter(ids).items() if c>1]
    if dup: errors.append("duplicate ids: "+','.join(sorted(dup)))
    known=set(ids)
    for item in doc.get("items") or []:
        for dep in item.get("depends_on") or []:
            if dep not in known: errors.append(f"{item.get('id')} unknown dependency: {dep}")
    return errors

def summarize_register(doc: dict[str, Any]) -> dict[str, Any]:
    items=doc.get("items") or []; open_items=[x for x in items if x.get("status") != "DONE"]
    blockers=[x for x in open_items if x.get("priority")=="P0"]
    ready=[x for x in open_items if all(next((d for d in items if d.get("id")==dep),{}).get("status")=="DONE" for dep in x.get("depends_on") or [])]
    return {"register_id":doc.get("register_id"),"version":doc.get("version"),"updated_at":doc.get("updated_at"),"total":len(items),"open":len(open_items),"p0_open":len(blockers),"status_counts":dict(Counter(x.get("status") for x in items)),"next_actions":[{"id":x["id"],"title":x["title"],"priority":x["priority"],"target_version":x["target_version"]} for x in sorted(ready,key=lambda y:(y.get("priority","P9"),y.get("id")))[:8]]}
