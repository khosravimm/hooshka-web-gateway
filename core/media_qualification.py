from __future__ import annotations

from pathlib import Path
from typing import Any

QUALIFICATION_VERSION = "1.0.0"
REPRESENTATIVE_EXTENSIONS = {
    "text": [".txt", ".md"],
    "document": [".pdf", ".docx"],
    "spreadsheet": [".csv", ".xlsx"],
    "image": [".png", ".jpg", ".jpeg"],
    "code": [".py", ".js", ".ts"],
    "presentation": [".ppt", ".pptx"],
    "audio": [".mp3", ".wav", ".m4a"],
    "video": [".mp4", ".webm", ".mov"],
}


def media_qualification_policy() -> dict[str, Any]:
    return {
        "version": QUALIFICATION_VERSION,
        "required": True,
        "scope": "all_current_and_future_providers",
        "classes": list(REPRESENTATIVE_EXTENSIONS),
        "representatives": {k:list(v) for k,v in REPRESENTATIVE_EXTENSIONS.items()},
        "promotion_rule": "E2_required_for_certified",
    }


def parse_accept(accept: str) -> dict[str, Any]:
    tokens=[x.strip().lower() for x in str(accept or "").split(",") if x.strip()]
    extensions=sorted({x for x in tokens if x.startswith(".")})
    mime_types=sorted({x for x in tokens if "/" in x and not x.startswith(".")})
    classes={}
    for name,reps in REPRESENTATIVE_EXTENSIONS.items():
        classes[name]=any(ext in extensions for ext in reps)
    return {"tokens":tokens,"extensions":extensions,"mime_types":mime_types,"classes":classes}


async def observe_file_upload_surface(page) -> dict[str, Any]:
    inputs=await page.locator("input[type=file]").evaluate_all("""nodes => nodes.map((e,i)=>({index:i,accept:e.accept||'',multiple:!!e.multiple,disabled:!!e.disabled}))""")
    parsed=[]
    combined=set()
    for item in inputs:
        info=parse_accept(item.get("accept") or "")
        combined.update(info["extensions"])
        parsed.append({**item,"parsed":info})
    classes={name:any(ext in combined for ext in reps) for name,reps in REPRESENTATIVE_EXTENSIONS.items()}
    return {
        "schema_version": QUALIFICATION_VERSION,
        "qualification_policy": media_qualification_policy(),
        "input_present": bool(inputs),
        "input_count": len(inputs),
        "multiple_supported": any(bool(x.get("multiple")) for x in inputs),
        "advertised_extensions": sorted(combined),
        "advertised_classes": classes,
        "inputs": parsed,
        "evidence_level": "E1",
        "status": "advertised_unverified" if inputs else "not_advertised",
    }


def apply_persisted_media_certification(provider, inventory: dict[str, Any]) -> dict[str, Any]:
    profile=next((p for p in inventory.get("provider_profiles",[]) if p.get("provider_id")==provider.provider_id),None)
    latest=((profile or {}).get("media_qualification") or {}).get("latest") or {}
    certified=dict(latest.get("certified") or {})
    media=dict(getattr(provider.capabilities,"media",{}) or {})
    if certified.get("file_upload"):
        provider.capabilities.files=True
        media["file_upload"]={"supported":True,"constraints":latest.get("constraints") or {}}
        media["document_upload"]={"supported":True,"constraints":latest.get("constraints") or {}}
    if certified.get("image_input"):
        provider.capabilities.vision=True
        media["image_input"]={"supported":True,"constraints":latest.get("constraints") or {}}
    provider.capabilities.media=media
    return certified


def qualification_result(provider_id: str, media_kind: str, file_path: str, response: str, expected_marker: str, *, advertised: dict | None = None) -> dict[str, Any]:
    matched=bool(expected_marker and expected_marker in (response or ""))
    return {
        "schema_version": QUALIFICATION_VERSION,
        "provider_id": provider_id,
        "media_kind": media_kind,
        "file_name": Path(file_path).name,
        "tested": True,
        "response_received": bool(response),
        "marker_match": matched,
        "certified": {"file_upload": matched, "image_input": matched if media_kind=="image_input" else False},
        "advertised": advertised or {},
        "evidence_level": "E2" if matched else "E1",
        "status": "certified" if matched else "failed",
    }
