from __future__ import annotations

from dataclasses import dataclass
import mimetypes
from pathlib import Path
from typing import Any

CONTRACT_VERSION = "1.0.0"
MEDIA_KINDS = (
    "text", "image_input", "image_output", "file_upload", "document_upload",
    "audio_input", "audio_output", "video_input", "video_output",
)

class MediaContractError(ValueError):
    def __init__(self, message: str, code: str = "unsupported_media", details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}

def media_manifest_from_capabilities(capabilities: Any) -> dict[str, Any]:
    def get(name: str, default=None):
        if isinstance(capabilities, dict): return capabilities.get(name, default)
        return getattr(capabilities, name, default)
    explicit = dict(get("media", {}) or {})
    support = {
        "text": True,
        "image_input": bool(get("vision", False)),
        "image_output": False,
        "file_upload": bool(get("files", False)),
        "document_upload": bool(get("files", False)),
        "audio_input": False, "audio_output": False,
        "video_input": False, "video_output": False,
    }
    for kind in MEDIA_KINDS:
        entry = explicit.get(kind)
        if isinstance(entry, bool): support[kind] = entry
        elif isinstance(entry, dict) and "supported" in entry: support[kind] = bool(entry["supported"])
    constraints = {}
    for kind in MEDIA_KINDS:
        entry = explicit.get(kind)
        supplied = dict(entry.get("constraints") or {}) if isinstance(entry, dict) else {}
        constraints[kind] = {
            "mime_types": list(supplied.get("mime_types") or []),
            "max_bytes": supplied.get("max_bytes"),
            "max_duration_seconds": supplied.get("max_duration_seconds"),
            "max_resolution": supplied.get("max_resolution"),
            "lifecycle": supplied.get("lifecycle") or "provider_session",
            "privacy": supplied.get("privacy") or "provider_policy_applies",
        }
    return {"contract_version": CONTRACT_VERSION, "support": support, "constraints": constraints}

def provider_media_manifest(provider) -> dict[str, Any]:
    return media_manifest_from_capabilities(provider.capabilities)

def _kind_from_part(part: dict[str, Any]) -> str | None:
    t = str(part.get("type") or "").lower()
    return {
        "image_url":"image_input", "input_image":"image_input", "image":"image_input",
        "input_audio":"audio_input", "audio":"audio_input",
        "input_file":"file_upload", "file":"file_upload",
        "input_video":"video_input", "video":"video_input",
    }.get(t)

def _kind_from_path(value: str) -> str:
    mime, _ = mimetypes.guess_type(str(value))
    mime = mime or "application/octet-stream"
    if mime.startswith("image/"): return "image_input"
    if mime.startswith("audio/"): return "audio_input"
    if mime.startswith("video/"): return "video_input"
    if mime.startswith("text/") or mime in {"application/pdf", "application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}:
        return "document_upload"
    return "file_upload"

def requested_media(data: dict[str, Any]) -> list[dict[str, Any]]:
    requested=[]
    for mi, message in enumerate(data.get("messages") or []):
        content=message.get("content")
        if isinstance(content, list):
            for pi, part in enumerate(content):
                if not isinstance(part, dict): continue
                kind=_kind_from_part(part)
                if kind: requested.append({"kind":kind,"source":"message","message_index":mi,"part_index":pi})
    paths=list(data.get("file_paths") or [])
    if data.get("file_path"): paths.append(data["file_path"])
    for path in paths:
        requested.append({"kind":_kind_from_path(str(path)),"source":"file_path","path":str(path)})
    return requested

def validate_media_request(provider, data: dict[str, Any]) -> dict[str, Any]:
    manifest=provider_media_manifest(provider)
    requested=requested_media(data)
    unsupported=sorted({item["kind"] for item in requested if not manifest["support"].get(item["kind"], False)})
    if unsupported:
        raise MediaContractError(
            "Requested media is not certified for the selected provider: " + ", ".join(unsupported),
            "unsupported_media_type",
            {"provider":provider.provider_id,"unsupported":unsupported,"requested":requested,"media_contract_version":CONTRACT_VERSION},
        )
    return {"requested":requested,"manifest":manifest}
