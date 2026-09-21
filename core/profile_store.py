"""Persistent NG Provider Profile / Account Instance store.

The store contains non-secret relationship/configuration metadata only. It
separates Provider Profile artifacts from Account Instance artifacts and keeps
legacy config migration reversible and auditable.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any
import json
import os
import re
import uuid

from core.profile_contract import project_ng_inventory

STORE_VERSION = "1.0.0"
ARTIFACT_VERSION = "1.0.0-migrated.1"
DEFAULT_ROOT = Path(__file__).resolve().parents[1] / ".runtime-dev" / "ng-store"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _safe_id(value: str) -> str:
    value = str(value or "").strip()
    if not value:
        raise ValueError("artifact id is required")
    return re.sub(r"[^A-Za-z0-9._-]+", "__", value)


def _dirs(root: Path) -> tuple[Path, Path]:
    return root / "provider_profiles", root / "account_instances"


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _source_record(config_path: Path) -> dict[str, Any]:
    return {
        "kind": "legacy_config_migration",
        "path": str(config_path.resolve()),
        "sha256": _sha(config_path),
    }


def _enrich(payload: dict[str, Any], source: dict[str, Any], now: str) -> dict[str, Any]:
    out = dict(payload)
    out["artifact_version"] = ARTIFACT_VERSION
    out["updated_at"] = now
    out["source"] = source
    out["change_log"] = [{"at": now, "change": "migrated_from_legacy_config", "evidence_level": "E0"}]
    return out


def migrate_legacy_inventory(config_path: str | Path, root: str | Path | None = None) -> dict[str, Any]:
    config_path = Path(config_path)
    root = Path(root) if root else DEFAULT_ROOT
    profiles_dir, accounts_dir = _dirs(root)
    manifest_path = root / "migration.json"
    if manifest_path.exists() or any(profiles_dir.glob("*.json")) or any(accounts_dir.glob("*.json")):
        raise FileExistsError("persistent NG inventory already exists")

    projected = project_ng_inventory(config_path)
    now = _now()
    source = _source_record(config_path)
    created: list[dict[str, str]] = []
    for item in projected.get("provider_profiles", []):
        payload = _enrich(item, source, now)
        path = profiles_dir / (_safe_id(payload["profile_id"]) + ".json")
        _atomic_json(path, payload)
        created.append({"kind": "provider_profile", "path": str(path.relative_to(root)), "sha256": _sha(path)})
    for item in projected.get("account_instances", []):
        payload = _enrich(item, source, now)
        path = accounts_dir / (_safe_id(payload["account_id"]) + ".json")
        _atomic_json(path, payload)
        created.append({"kind": "account_instance", "path": str(path.relative_to(root)), "sha256": _sha(path)})

    manifest = {
        "store_version": STORE_VERSION,
        "migration_id": str(uuid.uuid4()),
        "created_at": now,
        "source": source,
        "created_files": created,
        "reversible": True,
    }
    _atomic_json(manifest_path, manifest)
    return load_persistent_inventory(root)


def _load_json_files(folder: Path) -> list[dict[str, Any]]:
    rows=[]
    if not folder.exists():
        return rows
    for path in sorted(folder.glob("*.json")):
        rows.append(json.loads(path.read_text(encoding="utf-8-sig")))
    return rows


def _conflicts(accounts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    users: dict[str, list[str]] = {}
    for item in accounts:
        path = str((item.get("browser_profile") or {}).get("path") or "").strip()
        if path:
            users.setdefault(path, []).append(str(item.get("account_id") or ""))
    out=[]
    for path, account_ids in users.items():
        if len(account_ids) > 1:
            out.append({
                "type": "shared_browser_profile",
                "browser_profile": path,
                "accounts": account_ids,
                "requirement": "NG-BRW-003 / profile security boundary",
                "status": "CONFLICT",
            })
    return out


def load_persistent_inventory(root: str | Path | None = None) -> dict[str, Any]:
    root = Path(root) if root else DEFAULT_ROOT
    profiles_dir, accounts_dir = _dirs(root)
    profiles = _load_json_files(profiles_dir)
    accounts = _load_json_files(accounts_dir)
    if not profiles and not accounts:
        raise FileNotFoundError("persistent NG inventory is not initialized")
    return {
        "contract_version": "1.0.0",
        "store_version": STORE_VERSION,
        "source": "persistent_store",
        "authority": "persistent_ng_store",
        "provider_profiles": profiles,
        "account_instances": accounts,
        "conflicts": _conflicts(accounts),
        "persistence_complete": True,
        "migration_complete": True,
    }


def load_ng_inventory(config_path: str | Path, root: str | Path | None = None) -> dict[str, Any]:
    try:
        return load_persistent_inventory(root)
    except FileNotFoundError:
        projected = project_ng_inventory(config_path)
        projected["authority"] = "legacy_projection"
        projected["persistence_complete"] = False
        return projected


def rollback_legacy_migration(root: str | Path | None = None) -> dict[str, Any]:
    root = Path(root) if root else DEFAULT_ROOT
    manifest_path = root / "migration.json"
    if not manifest_path.exists():
        raise FileNotFoundError("migration manifest not found")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    for entry in manifest.get("created_files", []):
        path = root / entry["path"]
        if not path.exists():
            continue
        if _sha(path) != entry.get("sha256"):
            raise RuntimeError(f"rollback refused: artifact changed after migration: {entry['path']}")
    removed=[]
    for entry in manifest.get("created_files", []):
        path = root / entry["path"]
        if path.exists():
            path.unlink(); removed.append(entry["path"])
    manifest_path.unlink()
    for folder in reversed(_dirs(root)):
        if folder.exists() and not any(folder.iterdir()):
            folder.rmdir()
    if root.exists() and not any(root.iterdir()):
        root.rmdir()
    return {"rolled_back": True, "migration_id": manifest.get("migration_id"), "removed": removed}
