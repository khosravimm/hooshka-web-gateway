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
    users: dict[tuple[str, str], list[str]] = {}
    for item in accounts:
        browser = item.get("browser_profile") or {}
        path = str(browser.get("path") or "").strip()
        origin = str(browser.get("origin") or "").strip().lower()
        if path:
            # Missing origin is intentionally conservative: accounts sharing a
            # profile without proven origin separation remain conflicting.
            users.setdefault((path, origin), []).append(str(item.get("account_id") or ""))
    out=[]
    for (path, origin), account_ids in users.items():
        if len(account_ids) > 1:
            out.append({
                "type": "shared_browser_profile",
                "scope": "same_origin" if origin else "origin_unknown",
                "browser_profile": path,
                "origin": origin or None,
                "accounts": account_ids,
                "requirement": "NG-BRW-003 / origin session-storage boundary",
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


def reconcile_isolation_metadata(config_path: str | Path, root: str | Path | None = None) -> dict[str, Any]:
    """Reconcile browser origin/sharing metadata without replacing account state."""
    root = Path(root) if root else DEFAULT_ROOT
    _profiles_dir, accounts_dir = _dirs(root)
    if not accounts_dir.exists():
        raise FileNotFoundError("persistent NG inventory is not initialized")
    projected = project_ng_inventory(config_path)
    desired = {str(a.get("account_id")): dict(a.get("browser_profile") or {})
               for a in projected.get("account_instances", [])}
    changed=[]
    now=_now()
    for path in sorted(accounts_dir.glob("*.json")):
        payload=json.loads(path.read_text(encoding="utf-8-sig"))
        account_id=str(payload.get("account_id") or "")
        target=desired.get(account_id)
        if not target:
            continue
        current=dict(payload.get("browser_profile") or {})
        merged=dict(current)
        for key in ("path","origin","ownership","sharing_mode"):
            if key in target:
                merged[key]=target[key]
        if merged == current:
            continue
        payload["browser_profile"]=merged
        payload["updated_at"]=now
        log=list(payload.get("change_log") or [])
        log.append({"at":now,"change":"isolation_metadata_reconciled","evidence_level":"E1"})
        payload["change_log"]=log
        _atomic_json(path,payload)
        changed.append(account_id)
    result=load_persistent_inventory(root)
    result["reconciled_accounts"]=changed
    return result


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


def update_account_session(account_id: str, session: dict[str, Any], root: str | Path | None = None) -> dict[str, Any]:
    """Persist only allow-listed non-secret session lifecycle metadata."""
    root = Path(root) if root else DEFAULT_ROOT
    _profiles_dir, accounts_dir = _dirs(root)
    path = accounts_dir / (_safe_id(account_id) + ".json")
    if not path.exists():
        raise FileNotFoundError(f"account instance not found: {account_id}")
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    allowed = {"contract_version", "access_state", "state", "authenticated", "reason", "validated_at"}
    safe = {k: session.get(k) for k in allowed if k in session}
    evidence = dict(session.get("evidence") or {})
    safe["evidence"] = {k: evidence.get(k) for k in ("provider_authenticated", "composer_ready", "source_access_state") if k in evidence}
    payload["session"] = safe
    payload["updated_at"] = _now()
    log = list(payload.get("change_log") or [])
    log.append({"at": payload["updated_at"], "change": "session_lifecycle_validated", "evidence_level": "E1"})
    payload["change_log"] = log
    _atomic_json(path, payload)
    return payload


def update_provider_tool_capabilities(provider_id: str, result: dict[str, Any], root: str | Path | None = None) -> dict[str, Any]:
    """Persist bounded non-secret tool qualification evidence in a Provider Profile."""
    root = Path(root) if root else DEFAULT_ROOT
    profiles_dir, _accounts_dir = _dirs(root)
    matches = []
    for candidate in profiles_dir.glob("*.json") if profiles_dir.exists() else []:
        payload = json.loads(candidate.read_text(encoding="utf-8-sig"))
        if str(payload.get("provider_id") or "") == str(provider_id or ""):
            matches.append((candidate, payload))
    if not matches:
        raise FileNotFoundError(f"provider profile not found: {provider_id}")
    if len(matches) > 1:
        raise RuntimeError(f"multiple provider profiles found for provider: {provider_id}")
    path, payload = matches[0]
    allowed = {
        "schema_version", "tested_at", "provider_id", "model", "probe_tool",
        "tested", "supported", "evidence_level", "execution", "marker_match",
        "protocol_valid", "returned_tool", "reason", "error_type", "error_code",
    }
    safe = {k: result.get(k) for k in allowed if k in result}
    safe["provider_id"] = provider_id
    now = _now()
    current = dict(payload.get("tool_capabilities") or {})
    history = list(current.get("history") or [])
    history.append(safe)
    payload["tool_capabilities"] = {
        "schema_version": "1.0.0",
        "latest": safe,
        "history": history[-20:],
        "updated_at": now,
    }
    payload["updated_at"] = now
    log = list(payload.get("change_log") or [])
    log.append({"at": now, "change": "provider_tool_capability_qualified", "evidence_level": safe.get("evidence_level") or "E1"})
    payload["change_log"] = log[-100:]
    _atomic_json(path, payload)
    return payload


def update_provider_media_qualification(provider_id: str, result: dict[str, Any], root: str | Path | None = None) -> dict[str, Any]:
    """Persist E1/E2 media qualification without turning advertised support into certification."""
    root = Path(root) if root else DEFAULT_ROOT
    profiles_dir, _accounts_dir = _dirs(root)
    matches=[]
    for candidate in profiles_dir.glob("*.json") if profiles_dir.exists() else []:
        payload=json.loads(candidate.read_text(encoding="utf-8-sig"))
        if str(payload.get("provider_id") or "") == str(provider_id or ""):
            matches.append((candidate,payload))
    if len(matches) != 1:
        raise FileNotFoundError(f"provider profile resolution failed: {provider_id}")
    path,payload=matches[0]
    current=dict(payload.get("media_qualification") or {})
    previous=dict((current.get("latest") or {}).get("certified") or {})
    incoming=dict(result.get("certified") or {})
    merged={k: bool(previous.get(k) or incoming.get(k)) for k in set(previous)|set(incoming)}
    previous_classes=dict((current.get("latest") or {}).get("certified_classes") or {})
    incoming_classes=dict(result.get("certified_classes") or {})
    merged_classes={k: bool(previous_classes.get(k) or incoming_classes.get(k)) for k in set(previous_classes)|set(incoming_classes)}
    safe=dict(result)
    safe["certified"]=merged
    safe["certified_classes"]=merged_classes
    now=_now()
    history=list(current.get("history") or []); history.append(dict(result))
    payload["media_qualification"]={"schema_version":"1.0.0","latest":safe,"history":history[-50:],"updated_at":now}
    payload["updated_at"]=now
    log=list(payload.get("change_log") or [])
    log.append({"at":now,"change":"provider_media_qualification_recorded","evidence_level":result.get("evidence_level") or "E1"})
    payload["change_log"]=log[-100:]
    _atomic_json(path,payload)
    return payload


def _allocate_account_port(config_path: str | Path, accounts: list[dict[str, Any]], preferred: int | None = None) -> int:
    from core.runtime_inventory import load_runtime_inventory
    used = {int(r["port"]) for r in load_runtime_inventory(config_path)}
    for account in accounts:
        runtime = account.get("runtime") or {}
        if runtime.get("port"):
            used.add(int(runtime["port"]))
    if preferred is not None:
        port = int(preferred)
        if port < 1024 or port > 65535 or port in used:
            raise ValueError(f"account runtime port is unavailable: {port}")
        return port
    for port in range(9340, 9400):
        if port not in used:
            return port
    raise RuntimeError("no free account CDP port in managed range 9340-9399")


def provision_account_instance(
    provider_id: str,
    account_id: str,
    config_path: str | Path,
    root: str | Path | None = None,
    preferred_port: int | None = None,
) -> dict[str, Any]:
    """Create an isolated same-provider Account Instance without cloning a Provider."""
    from urllib.parse import urlparse
    from core.runtime_inventory import inventory_by_id
    root = Path(root) if root else DEFAULT_ROOT
    inv = load_persistent_inventory(root)
    account_id = str(account_id or "").strip()
    provider_id = str(provider_id or "").strip()
    if not account_id or not provider_id:
        raise ValueError("provider_id and account_id are required")
    if any(a.get("account_id") == account_id for a in inv["account_instances"]):
        raise FileExistsError(f"account already exists: {account_id}")
    profile = next((p for p in inv["provider_profiles"] if p.get("provider_id") == provider_id), None)
    if profile is None:
        raise KeyError(f"provider profile not found: {provider_id}")
    base = inventory_by_id(config_path).get(provider_id)
    if not base:
        raise KeyError(f"provider runtime not found: {provider_id}")
    parsed = urlparse(base["home_url"])
    origin = f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"
    port = _allocate_account_port(config_path, inv["account_instances"], preferred_port)
    safe = _safe_id(account_id)
    profile_rel = str(Path(".runtime-dev") / "accounts" / safe)
    now = _now()
    payload = {
        "schema_version": "1.0.0",
        "artifact_version": "1.0.0-provisioned.1",
        "account_id": account_id,
        "provider_profile_id": profile["profile_id"],
        "browser_profile": {
            "path": profile_rel,
            "origin": origin,
            "ownership": "exclusive",
            "sharing_mode": "exclusive_profile",
        },
        "runtime": {
            "kind": "chrome_cdp",
            "cdp_url": f"http://127.0.0.1:{port}",
            "port": port,
            "profile_dir": profile_rel,
            "home_url": base["home_url"],
            "label": f"HWG-Account-{safe}",
        },
        "session": {"state": "unknown", "access_state": "UNKNOWN", "validated_at": None},
        "capability_snapshot": {"version": "unvalidated", "evidence_level": "E0"},
        "enabled": False,
        "source": {"kind": "account_provisioning", "provider_id": provider_id},
        "updated_at": now,
        "change_log": [{"at": now, "change": "isolated_account_provisioned", "evidence_level": "E1"}],
    }
    _profiles_dir, accounts_dir = _dirs(root)
    path = accounts_dir / (_safe_id(account_id) + ".json")
    _atomic_json(path, payload)
    return payload


def account_runtime(account_id: str, root: str | Path | None = None, project_root: str | Path | None = None) -> dict[str, Any]:
    root = Path(root) if root else DEFAULT_ROOT
    project_root = Path(project_root) if project_root else Path(__file__).resolve().parents[1]
    inv = load_persistent_inventory(root)
    account = next((a for a in inv["account_instances"] if a.get("account_id") == account_id), None)
    if account is None:
        raise KeyError(f"account not found: {account_id}")
    runtime = dict(account.get("runtime") or {})
    if not runtime:
        raise KeyError(f"account has no dedicated runtime: {account_id}")
    profile = Path(str(runtime.get("profile_dir") or ""))
    runtime["profile"] = str(profile if profile.is_absolute() else (project_root / profile).resolve())
    runtime["account_id"] = account_id
    runtime["provider_profile_id"] = account.get("provider_profile_id")
    return runtime


def deprovision_account_instance(account_id: str, root: str | Path | None = None) -> dict[str, Any]:
    root = Path(root) if root else DEFAULT_ROOT
    _profiles_dir, accounts_dir = _dirs(root)
    path = accounts_dir / (_safe_id(account_id) + ".json")
    if not path.exists():
        raise FileNotFoundError(f"account instance not found: {account_id}")
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not (payload.get("runtime") or {}):
        raise RuntimeError("default/migrated account cannot be deprovisioned by account-runtime operation")
    path.unlink()
    return {"deleted": True, "account_id": account_id, "browser_profile": payload.get("browser_profile"), "runtime": payload.get("runtime")}
