"""Functional readiness state and bounded provider probe for HWG."""
from __future__ import annotations

import asyncio
import json
import os
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.providers import ChatCompletionRequest

CONTRACT_VERSION = "1.0.0"
DEFAULT_TTL_SECONDS = 300
DEFAULT_ROOT = Path(__file__).resolve().parents[1] / ".runtime-dev" / "readiness"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "__", str(value or "unknown"))


def save_readiness(record: dict[str, Any], root: str | Path | None = None) -> Path:
    root = Path(root) if root else DEFAULT_ROOT
    root.mkdir(parents=True, exist_ok=True)
    path = root / (_safe(record["provider_id"]) + ".json")
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return path


def load_readiness(provider_id: str, root: str | Path | None = None) -> dict[str, Any] | None:
    root = Path(root) if root else DEFAULT_ROOT
    path = root / (_safe(provider_id) + ".json")
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    expires = float(data.get("expires_at_epoch") or 0)
    data["current"] = bool(expires and expires >= time.time())
    return data


def invalidate_readiness(provider_id: str, reason: str, root: str | Path | None = None) -> dict[str, Any] | None:
    record = load_readiness(provider_id, root)
    if not record:
        return None
    record["state"] = "INVALIDATED"
    record["ready"] = False
    record["invalidated_at"] = _now()
    record["invalidated_reason"] = str(reason)
    record["expires_at_epoch"] = 0
    save_readiness(record, root)
    record["current"] = False
    return record


def choose_model(provider) -> str:
    cfg = getattr(getattr(provider, "config", None), "config", {}) or {}
    supported = list(getattr(getattr(provider, "capabilities", None), "supported_models", []) or [])
    if supported:
        return supported[0]
    explicit = str(cfg.get("default_upstream_model") or "").strip()
    return explicit or provider.provider_id


async def run_functional_probe(
    provider,
    *,
    account_id: str | None,
    runtime_ready: bool,
    access_state: str,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> dict[str, Any]:
    started = time.time()
    stages: list[dict[str, Any]] = []

    def add(stage: str, ok: bool, **evidence):
        stages.append({"stage": stage, "ok": bool(ok), "at": _now(), "evidence": evidence})

    add("runtime_cdp", runtime_ready)
    if not runtime_ready:
        return _final_record(provider, account_id, "RUNTIME_ABSENT", False, stages, started, ttl_seconds)

    access = str(access_state or "UNKNOWN").upper()
    add("access_auth", access == "AUTHENTICATED", access_state=access)
    if access != "AUTHENTICATED":
        return _final_record(provider, account_id, access, False, stages, started, ttl_seconds)

    model = choose_model(provider)
    try:
        models = await asyncio.wait_for(provider.list_models(), timeout=20)
        ids = [str(getattr(m, "id", "")) for m in models]
        model_ok = model in ids or provider.supports_model(model)
    except Exception as exc:
        ids = []
        model_ok = False
        add("model_state", False, model=model, error=type(exc).__name__)
    else:
        add("model_state", model_ok, model=model, observed_models=ids[:32])
    if not model_ok:
        return _final_record(provider, account_id, "MODEL_INVALID", False, stages, started, ttl_seconds, model=model)

    cfg = getattr(getattr(provider, "config", None), "config", {}) or {}
    defaults = dict(cfg.get("feature_defaults") or {})
    controls = dict(cfg.get("feature_controls") or {})
    feature_ok = isinstance(defaults, dict) and isinstance(controls, dict)
    add("feature_state", feature_ok, defaults=defaults, controls=controls)
    if not feature_ok:
        return _final_record(provider, account_id, "FEATURE_INVALID", False, stages, started, ttl_seconds, model=model)

    marker = "HWG_READY_" + uuid.uuid4().hex[:12].upper()
    req = ChatCompletionRequest(
        model=model,
        messages=[{"role": "user", "content": f"Reply exactly with this token and nothing else: {marker}"}],
        stream=False,
        max_tokens=64,
    )
    try:
        response = await asyncio.wait_for(provider.chat_completion(req), timeout=75)
        observed = ""
        if response.choices:
            observed = (response.choices[0].message.content or "").strip()
        passed = observed == marker
        add("functional_probe", passed, expected=marker, observed=observed[:256])
    except Exception as exc:
        passed = False
        add("functional_probe", False, error=type(exc).__name__)

    state = "READY" if passed else "FUNCTIONAL_PROBE_FAILED"
    return _final_record(provider, account_id, state, passed, stages, started, ttl_seconds, model=model)


def _final_record(provider, account_id, state, ready, stages, started, ttl_seconds, model=None):
    now_epoch = time.time()
    return {
        "contract_version": CONTRACT_VERSION,
        "provider_id": provider.provider_id,
        "account_id": account_id,
        "state": state,
        "ready": bool(ready),
        "model": model,
        "checked_at": _now(),
        "duration_ms": int((now_epoch - started) * 1000),
        "expires_at_epoch": now_epoch + max(1, int(ttl_seconds)) if ready else 0,
        "stages": stages,
    }
