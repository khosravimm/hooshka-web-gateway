"""Canonical provider runtime inventory derived from config.yaml.

No provider IDs, counts, CDP ports, profiles, or browser URLs belong in the
runtime orchestration code.  A provider participates in browser runtime
orchestration only when it declares ``runtime.kind: chrome_cdp``.
"""
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse
import json
import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config.yaml"


def _load_config(config_path: str | Path = DEFAULT_CONFIG) -> tuple[Path, dict]:
    path = Path(config_path)
    with path.open("r", encoding="utf-8-sig") as fh:
        return path, (yaml.safe_load(fh) or {})


def _absolute_profile(root: Path, value: str) -> str:
    p = Path(value)
    return str(p if p.is_absolute() else (root / p).resolve())


def load_runtime_inventory(config_path: str | Path = DEFAULT_CONFIG) -> list[dict]:
    path, config = _load_config(config_path)
    root = path.resolve().parent

    shared = ((config.get("runtime_orchestration") or {}).get("shared_browser") or {})
    shared_mode = bool(shared.get("enabled"))
    shared_cdp = str(shared.get("cdp_url") or "").rstrip("/")
    shared_profile = str(shared.get("profile_dir") or "").strip()

    result: list[dict] = []
    seen_ids: set[str] = set()
    seen_ports: set[int] = set()
    for provider in config.get("providers", []) or []:
        provider_id = str(provider.get("id") or "").strip()
        if not provider_id:
            raise ValueError("Provider entry is missing id")
        if provider_id in seen_ids:
            raise ValueError(f"Duplicate provider id: {provider_id}")
        seen_ids.add(provider_id)

        runtime = provider.get("runtime", {}) or {}
        if str(runtime.get("kind") or "").strip() != "chrome_cdp":
            continue
        cdp_url = str(runtime.get("cdp_url") or (provider.get("config", {}) or {}).get("cdp_url") or "").strip()
        profile_dir = str(runtime.get("profile_dir") or "").strip()
        home_url = str(runtime.get("home_url") or "").strip()
        label = str(runtime.get("label") or provider_id).strip()
        if not cdp_url or not profile_dir or not home_url:
            raise ValueError(f"Provider {provider_id} chrome_cdp runtime requires cdp_url, profile_dir and home_url")
        parsed = urlparse(cdp_url)
        if parsed.hostname not in {"127.0.0.1", "localhost", "::1"} or not parsed.port:
            raise ValueError(f"Provider {provider_id} runtime cdp_url must be loopback with explicit port")
        if parsed.port in seen_ports:
            if not (shared_mode and cdp_url.rstrip("/") == shared_cdp
                    and profile_dir == shared_profile):
                raise ValueError(f"Duplicate CDP port in runtime inventory: {parsed.port}")
        seen_ports.add(parsed.port)
        result.append({
            "id": provider_id,
            "type": str(provider.get("type") or ""),
            "enabled": bool(provider.get("enabled", True)),
            "kind": "chrome_cdp",
            "cdp_url": cdp_url.rstrip("/"),
            "port": int(parsed.port),
            "profile": _absolute_profile(root, profile_dir),
            "home_url": home_url,
            "label": label,
        })
    return result


def inventory_by_id(config_path: str | Path = DEFAULT_CONFIG) -> dict[str, dict]:
    return {item["id"]: item for item in load_runtime_inventory(config_path)}


def load_orchestration_settings(config_path: str | Path = DEFAULT_CONFIG) -> dict:
    _path, config = _load_config(config_path)
    settings = config.get("runtime_orchestration", {}) or {}
    required = (
        "gateway_service",
        "gateway_health_url",
        "desktop_agent_task",
        "desktop_agent_url",
        "restart_all_task",
        "restart_gateway_task",
    )
    missing = [key for key in required if not str(settings.get(key) or "").strip()]
    if missing:
        raise ValueError("runtime_orchestration missing required keys: " + ", ".join(missing))
    return {key: settings.get(key) for key in settings}


def load_runtime_configuration(config_path: str | Path = DEFAULT_CONFIG) -> dict:
    return {
        "orchestration": load_orchestration_settings(config_path),
        "providers": load_runtime_inventory(config_path),
    }


if __name__ == "__main__":
    print(json.dumps(load_runtime_configuration(), ensure_ascii=False))
