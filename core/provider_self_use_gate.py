"""Fail-closed qualification gate for using the discovery target as its own AI helper."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

GATE_VERSION = "1.0.0"
ROOT = Path(__file__).resolve().parents[1] / ".runtime-dev" / "discovery" / "self-use-gates"


@dataclass(frozen=True)
class TransportQualification:
    provider_id: str
    transport_fingerprint: str
    send_path: dict[str, Any]
    receive_path: dict[str, Any]
    completion_path: dict[str, Any]
    roundtrip: dict[str, Any]
    recorded_at: str
    gate_version: str = GATE_VERSION


def transport_fingerprint(provider) -> str:
    cfg = getattr(provider, "config", None)
    raw = {
        "provider_id": getattr(provider, "provider_id", ""),
        "provider_type": str(getattr(getattr(provider, "provider_type", None), "value", getattr(provider, "provider_type", ""))),
        "config": getattr(cfg, "config", {}) or {},
    }
    encoded = json.dumps(raw, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _path_ok(item: dict[str, Any]) -> bool:
    return bool(item.get("identified")) and item.get("method") in {"dom", "accessibility", "network", "frontend_controller", "browser_probe"} and bool(item.get("evidence_ref"))


def evaluate_qualification(record: TransportQualification | None, provider) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if record is None:
        return False, ["qualification_missing"]
    if record.provider_id != getattr(provider, "provider_id", None):
        reasons.append("provider_mismatch")
    if record.transport_fingerprint != transport_fingerprint(provider):
        reasons.append("transport_fingerprint_changed")
    if not _path_ok(record.send_path): reasons.append("send_path_not_qualified")
    if not _path_ok(record.receive_path): reasons.append("receive_path_not_qualified")
    if not _path_ok(record.completion_path): reasons.append("completion_path_not_qualified")
    rt = record.roundtrip or {}
    if not (rt.get("tested") is True and rt.get("passed") is True): reasons.append("roundtrip_not_passed")
    if rt.get("tool_class") != "deterministic": reasons.append("roundtrip_not_deterministic")
    if not rt.get("evidence_ref"): reasons.append("roundtrip_evidence_missing")
    return not reasons, reasons


def save_qualification(record: TransportQualification, root: Path | None = None) -> Path:
    base = root or ROOT
    base.mkdir(parents=True, exist_ok=True)
    path = base / f"{record.provider_id}.json"
    path.write_text(json.dumps(asdict(record), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def load_qualification(provider_id: str, root: Path | None = None) -> TransportQualification | None:
    path = (root or ROOT) / f"{provider_id}.json"
    if not path.is_file():
        return None
    return TransportQualification(**json.loads(path.read_text(encoding="utf-8-sig")))


def build_qualification(provider, send_path: dict[str, Any], receive_path: dict[str, Any], completion_path: dict[str, Any], roundtrip: dict[str, Any]) -> TransportQualification:
    return TransportQualification(
        provider_id=provider.provider_id,
        transport_fingerprint=transport_fingerprint(provider),
        send_path=dict(send_path),
        receive_path=dict(receive_path),
        completion_path=dict(completion_path),
        roundtrip=dict(roundtrip),
        recorded_at=datetime.now(timezone.utc).isoformat(),
    )


def self_use_status(provider, root: Path | None = None) -> dict[str, Any]:
    record = load_qualification(provider.provider_id, root)
    allowed, reasons = evaluate_qualification(record, provider)
    return {"provider_id": provider.provider_id, "allowed": allowed, "reasons": reasons, "record": asdict(record) if record else None}
