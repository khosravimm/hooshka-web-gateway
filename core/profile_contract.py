"""Read-only NG Provider Profile / Account Instance projection.

The legacy config remains authoritative for runtime behavior during migration.
This module projects it into the versioned NG relationship model without
persisting secrets or claiming certification that does not exist.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

CONTRACT_VERSION = "1.0.0"
LEGACY_PROFILE_VERSION = "0.legacy-projected"


def _load_config(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8-sig") as fh:
        return yaml.safe_load(fh) or {}


def _profile_path(item: dict[str, Any]) -> str:
    runtime = item.get("runtime") or {}
    config = item.get("config") or {}
    return str(runtime.get("profile_dir") or config.get("profile_dir") or "").strip()

def project_ng_inventory(config_path: str | Path) -> dict[str, Any]:
    cfg = _load_config(config_path)
    providers = cfg.get("providers") or []
    profile_users: dict[str, list[str]] = defaultdict(list)
    for item in providers:
        path = _profile_path(item)
        if path:
            profile_users[path].append(str(item.get("id") or ""))

    provider_profiles = []
    accounts = []
    conflicts = []
    for item in providers:
        provider_id = str(item.get("id") or "").strip()
        if not provider_id:
            continue
        runtime = item.get("runtime") or {}
        config = item.get("config") or {}
        browser_profile = _profile_path(item)
        shared = len(profile_users.get(browser_profile, [])) > 1 if browser_profile else False
        profile_id = f"{provider_id}:default"
        account_id = f"{provider_id}:default-account"
        transport_kind = str(config.get("transport_mode") or runtime.get("kind") or "unknown")
        provider_profiles.append({
            "schema_version": CONTRACT_VERSION,
            "profile_id": profile_id,
            "provider_id": provider_id,
            "profile_version": LEGACY_PROFILE_VERSION,
            "transport": {"kind": transport_kind, "provenance": "legacy_config_projection"},
            "readiness": {"policy": "functional", "probe_required": True},
            "evidence": {"level": "E0", "record": None},
            "source": "config.yaml",
        })
        accounts.append({
            "schema_version": CONTRACT_VERSION,
            "account_id": account_id,
            "provider_profile_id": profile_id,
            "browser_profile": {
                "path": browser_profile,
                "ownership": "shared_conflict" if shared else "exclusive",
            },
            "session": {"state": "unknown", "validated_at": None},
            "capability_snapshot": {"version": "legacy-projected", "evidence_level": "E0"},
            "migration_state": "legacy_projection",
            "enabled": bool(item.get("enabled", True)),
        })

    for path, provider_ids in profile_users.items():
        if len(provider_ids) > 1:
            conflicts.append({
                "type": "shared_browser_profile",
                "browser_profile": path,
                "providers": provider_ids,
                "requirement": "NG-BRW-003 / profile security boundary",
                "status": "CONFLICT",
            })
    return {
        "contract_version": CONTRACT_VERSION,
        "source": "legacy_config_projection",
        "provider_profiles": provider_profiles,
        "account_instances": accounts,
        "conflicts": conflicts,
        "migration_complete": False,
    }
