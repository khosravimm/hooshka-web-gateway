from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import time
import uuid
from pathlib import Path
from typing import BinaryIO, Iterable

UPLOAD_SCHEMA_VERSION = "1.0.0"
DEFAULT_MAX_BYTES = 64 * 1024 * 1024
DEFAULT_TTL_SECONDS = 60 * 60
_ID_RE = re.compile(r"^[0-9a-f]{32}$")


class UploadStoreError(Exception):
    def __init__(self, message: str, code: str, status: int = 400):
        super().__init__(message)
        self.code = code
        self.status = status
def upload_root() -> Path:
    configured = os.getenv("HWG_UPLOAD_ROOT", "").strip()
    root = Path(configured) if configured else Path(tempfile.gettempdir()) / "hooshka-hwg" / "uploads"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_suffix(filename: str) -> str:
    suffix = Path(str(filename or "")).suffix.lower()
    return suffix if re.fullmatch(r"\.[a-z0-9]{1,12}", suffix) else ""


def _meta_path(upload_id: str) -> Path:
    return upload_root() / upload_id / "meta.json"


def cleanup_expired(now: float | None = None) -> int:
    now = time.time() if now is None else now
    removed = 0
    for folder in upload_root().iterdir():
        if not folder.is_dir() or not _ID_RE.fullmatch(folder.name):
            continue
        try:
            meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
            if float(meta.get("expires_at", 0)) <= now:
                shutil.rmtree(folder, ignore_errors=True)
                removed += 1
        except Exception:
            continue
    return removed
def save_upload(stream: BinaryIO, original_name: str, content_type: str = "",
                *, max_bytes: int = DEFAULT_MAX_BYTES,
                ttl_seconds: int = DEFAULT_TTL_SECONDS) -> dict:
    cleanup_expired()
    upload_id = uuid.uuid4().hex
    folder = upload_root() / upload_id
    folder.mkdir(parents=True, exist_ok=False)
    stored = folder / ("payload" + _safe_suffix(original_name))
    size = 0
    try:
        with stored.open("wb") as fh:
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > int(max_bytes):
                    raise UploadStoreError("Upload exceeds gateway size limit", "upload_too_large", 413)
                fh.write(chunk)
        now = time.time()
        meta = {
            "schema_version": UPLOAD_SCHEMA_VERSION,
            "id": upload_id,
            "name": Path(str(original_name or "upload")).name,
            "content_type": str(content_type or "application/octet-stream"),
            "size": size,
            "created_at": now,
            "expires_at": now + int(ttl_seconds),
            "path": str(stored),
        }
        (folder / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        return {k: v for k, v in meta.items() if k != "path"}
    except Exception:
        shutil.rmtree(folder, ignore_errors=True)
        raise
def resolve_upload(upload_id: str, *, now: float | None = None) -> tuple[str, dict]:
    upload_id = str(upload_id or "").strip().lower()
    if not _ID_RE.fullmatch(upload_id):
        raise UploadStoreError("Invalid upload id", "invalid_upload_id", 400)
    meta_path = _meta_path(upload_id)
    if not meta_path.exists():
        raise UploadStoreError("Upload not found", "upload_not_found", 404)
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise UploadStoreError("Upload metadata is unreadable", "upload_metadata_invalid", 500) from exc
    now = time.time() if now is None else now
    if float(meta.get("expires_at", 0)) <= now:
        shutil.rmtree(meta_path.parent, ignore_errors=True)
        raise UploadStoreError("Upload expired", "upload_expired", 410)
    path = Path(str(meta.get("path") or ""))
    if not path.is_file() or path.parent != meta_path.parent:
        raise UploadStoreError("Upload payload is unavailable", "upload_payload_missing", 410)
    return str(path), {k: v for k, v in meta.items() if k != "path"}


def resolve_upload_ids(upload_ids: Iterable[str]) -> tuple[list[str], list[dict]]:
    paths, metas = [], []
    for upload_id in upload_ids or []:
        path, meta = resolve_upload(str(upload_id))
        paths.append(path)
        metas.append(meta)
    return paths, metas


def delete_upload(upload_id: str) -> bool:
    upload_id = str(upload_id or "").strip().lower()
    if not _ID_RE.fullmatch(upload_id):
        return False
    folder = upload_root() / upload_id
    if not folder.exists():
        return False
    shutil.rmtree(folder, ignore_errors=True)
    return True
