"""Strict E3 reliability evaluation for scoped Provider/Account/Model evidence."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class ReliabilityPolicy:
    probes_per_window: int = 3
    required_windows: int = 3
    min_window_separation_seconds: int = 1800
    max_probe_duration_ms: int = 60_000


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _functional_stage(record: dict[str, Any]) -> dict[str, Any]:
    return next((s for s in (record.get("stages") or []) if s.get("stage") == "functional_probe"), {})


def evaluate_probe(record: dict[str, Any], policy: ReliabilityPolicy | None = None) -> dict[str, Any]:
    policy=policy or ReliabilityPolicy()
    reasons=[]
    if record.get("state") != "READY" or record.get("ready") is not True:
        reasons.append("not_ready")
    if int(record.get("duration_ms") or 0) > policy.max_probe_duration_ms:
        reasons.append("duration_exceeded")
    stage=_functional_stage(record); ev=stage.get("evidence") or {}
    if stage.get("ok") is not True:
        reasons.append("functional_probe_failed")
    if not ev.get("expected") or ev.get("expected") != ev.get("observed"):
        reasons.append("exact_token_mismatch")
    if (ev.get("feature_application") or {}).get("mismatches"):
        reasons.append("feature_mismatch")
    c=ev.get("commitment") or {}
    if c.get("commitment_state") != "terminal": reasons.append("commitment_not_terminal")
    if c.get("retry_allowed") is not False: reasons.append("retry_still_allowed")
    return {"passed":not reasons,"reasons":reasons,"provider_id":record.get("provider_id"),"account_id":record.get("account_id"),"model":record.get("model"),"checked_at":record.get("checked_at"),"duration_ms":record.get("duration_ms")}


def evaluate_window(records: list[dict[str, Any]], *, window_id: str, started_at: str, policy: ReliabilityPolicy | None = None) -> dict[str, Any]:
    policy=policy or ReliabilityPolicy()
    probes=[evaluate_probe(r,policy) for r in records]
    scopes={(p.get("provider_id"),p.get("account_id"),p.get("model")) for p in probes}
    passed=len(records)==policy.probes_per_window and len(scopes)==1 and all(p["passed"] for p in probes)
    return {
        "window_id":window_id,"started_at":started_at,"completed_at":records[-1].get("checked_at") if records else None,
        "passed":passed,"required_probes":policy.probes_per_window,"observed_probes":len(records),
        "scope":list(next(iter(scopes))) if len(scopes)==1 else None,"probes":probes,
        "evidence_level":"REPEATED_E2_WINDOW",
    }


def evaluate_program(windows: list[dict[str, Any]], policy: ReliabilityPolicy | None = None) -> dict[str, Any]:
    policy=policy or ReliabilityPolicy()
    ordered=sorted(windows,key=lambda w:_dt(w["started_at"]))
    reasons=[]
    if len(ordered) < policy.required_windows:
        reasons.append("insufficient_windows")
    selected=ordered[:policy.required_windows]
    scopes={tuple(w.get("scope") or []) for w in selected}
    if selected and len(scopes)!=1:
        reasons.append("scope_changed")
    if any(not w.get("passed") for w in selected):
        reasons.append("window_failed")
    for prev,cur in zip(selected,selected[1:]):
        if (_dt(cur["started_at"])-_dt(prev["started_at"])).total_seconds() < policy.min_window_separation_seconds:
            reasons.append("window_separation_too_short")
            break
    passed=len(selected)==policy.required_windows and not reasons
    return {"passed":passed,"evidence_level":"E3" if passed else "E2","required_windows":policy.required_windows,
            "observed_windows":len(windows),"min_window_separation_seconds":policy.min_window_separation_seconds,
            "scope":list(next(iter(scopes))) if len(scopes)==1 else None,"reasons":reasons,"windows":selected}
