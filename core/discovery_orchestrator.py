"""HWG Next Generation Discovery Engine orchestration.

The existing discovery scanner is one probe inside this governed pipeline.
This module owns lifecycle, evidence promotion, drift/update-candidate state,
and versioned run records. It does not bypass provider/session risk controls.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any
import json
import uuid

ENGINE_VERSION = "2.1.0-dev.1"
SCHEMA_VERSION = "1.0.0"
RUNTIME_ROOT = Path(__file__).resolve().parents[1] / ".runtime-dev" / "discovery"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class DiscoveryState(str, Enum):
    RESEARCH_REQUIRED = "RESEARCH_REQUIRED"
    BASELINE_REQUIRED = "BASELINE_REQUIRED"
    EXPLORATION_READY = "EXPLORATION_READY"
    WAITING_FOR_LOGIN = "WAITING_FOR_LOGIN"
    WAITING_FOR_USER_INTERACTION = "WAITING_FOR_USER_INTERACTION"
    DIAGNOSTIC_REQUIRED = "DIAGNOSTIC_REQUIRED"
    BLOCKED = "BLOCKED"
    EXPLORING = "EXPLORING"
    SYNTHESIZING = "SYNTHESIZING"
    UPDATE_CANDIDATE = "UPDATE_CANDIDATE"
    CERTIFICATION_REQUIRED = "CERTIFICATION_REQUIRED"
    CERTIFYING = "CERTIFYING"
    CERTIFIED = "CERTIFIED"
    HOLD = "HOLD"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


ALLOWED_TRANSITIONS = {
    DiscoveryState.RESEARCH_REQUIRED: {DiscoveryState.BASELINE_REQUIRED, DiscoveryState.HOLD, DiscoveryState.FAILED},
    DiscoveryState.BASELINE_REQUIRED: {DiscoveryState.EXPLORATION_READY, DiscoveryState.WAITING_FOR_LOGIN, DiscoveryState.WAITING_FOR_USER_INTERACTION, DiscoveryState.DIAGNOSTIC_REQUIRED, DiscoveryState.BLOCKED, DiscoveryState.HOLD, DiscoveryState.FAILED},
    DiscoveryState.WAITING_FOR_LOGIN: {DiscoveryState.BASELINE_REQUIRED, DiscoveryState.HOLD, DiscoveryState.FAILED},
    DiscoveryState.WAITING_FOR_USER_INTERACTION: {DiscoveryState.BASELINE_REQUIRED, DiscoveryState.HOLD, DiscoveryState.FAILED},
    DiscoveryState.DIAGNOSTIC_REQUIRED: {DiscoveryState.BASELINE_REQUIRED, DiscoveryState.HOLD, DiscoveryState.FAILED},
    DiscoveryState.BLOCKED: {DiscoveryState.BASELINE_REQUIRED, DiscoveryState.HOLD, DiscoveryState.FAILED},
    DiscoveryState.EXPLORATION_READY: {DiscoveryState.EXPLORING, DiscoveryState.HOLD, DiscoveryState.FAILED},
    DiscoveryState.EXPLORING: {DiscoveryState.SYNTHESIZING, DiscoveryState.HOLD, DiscoveryState.FAILED},
    DiscoveryState.SYNTHESIZING: {DiscoveryState.UPDATE_CANDIDATE, DiscoveryState.CERTIFICATION_REQUIRED, DiscoveryState.HOLD, DiscoveryState.FAILED},
    DiscoveryState.UPDATE_CANDIDATE: {DiscoveryState.CERTIFICATION_REQUIRED, DiscoveryState.HOLD, DiscoveryState.REJECTED},
    DiscoveryState.CERTIFICATION_REQUIRED: {DiscoveryState.CERTIFYING, DiscoveryState.HOLD, DiscoveryState.REJECTED},
    DiscoveryState.CERTIFYING: {DiscoveryState.CERTIFIED, DiscoveryState.HOLD, DiscoveryState.FAILED},
    DiscoveryState.CERTIFIED: set(), DiscoveryState.HOLD: set(), DiscoveryState.REJECTED: set(), DiscoveryState.FAILED: set(),
}


@dataclass
class DiscoveryRun:
    provider_id: str
    recipe_version: str
    account_id: str | None = None
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    schema_version: str = SCHEMA_VERSION
    engine_version: str = ENGINE_VERSION
    state: str = DiscoveryState.RESEARCH_REQUIRED.value
    evidence_level: str = "E0"
    started_at: str = field(default_factory=_now)
    completed_at: str | None = None
    findings: dict[str, Any] = field(default_factory=dict)
    drift: list[dict[str, Any]] = field(default_factory=list)
    candidate: dict[str, Any] | None = None
    decision: str = "PENDING"
    history: list[dict[str, Any]] = field(default_factory=list)

    def transition(self, target: DiscoveryState, reason: str, evidence_level: str | None = None) -> None:
        current = DiscoveryState(self.state)
        if target not in ALLOWED_TRANSITIONS[current]:
            raise ValueError(f"invalid discovery transition: {current.value} -> {target.value}")
        self.state = target.value
        if evidence_level:
            self.evidence_level = evidence_level
        self.history.append({"at": _now(), "from": current.value, "to": target.value, "reason": reason, "evidence_level": self.evidence_level})
        if target in {DiscoveryState.CERTIFIED, DiscoveryState.HOLD, DiscoveryState.REJECTED, DiscoveryState.FAILED}:
            self.completed_at = _now()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def save(self, root: Path | None = None) -> Path:
        base = (root or RUNTIME_ROOT) / self.provider_id / self.run_id
        base.mkdir(parents=True, exist_ok=True)
        path = base / "result.json"
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return path


def new_run(provider_id: str, recipe_version: str, account_id: str | None = None) -> DiscoveryRun:
    return DiscoveryRun(provider_id=provider_id, recipe_version=recipe_version, account_id=account_id)


def load_run(provider_id: str, run_id: str, root: Path | None = None) -> DiscoveryRun:
    path = (root or RUNTIME_ROOT) / provider_id / run_id / "result.json"
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    return DiscoveryRun(**payload)


def list_runs(root: Path | None = None) -> list[dict[str, Any]]:
    base = root or RUNTIME_ROOT
    rows = []
    if not base.exists():
        return rows
    for path in base.glob("*/*/result.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
            rows.append({k: payload.get(k) for k in ("run_id", "provider_id", "account_id", "recipe_version", "engine_version", "state", "evidence_level", "started_at", "completed_at", "decision")})
        except Exception:
            continue
    return sorted(rows, key=lambda x: x.get("started_at") or "", reverse=True)


def attach_research(run: DiscoveryRun, sources: list[dict[str, Any]]) -> None:
    if DiscoveryState(run.state) is not DiscoveryState.RESEARCH_REQUIRED:
        raise ValueError("research can only be attached at RESEARCH_REQUIRED")
    if not sources:
        raise ValueError("research-first gate requires at least one source record")
    run.findings["research"] = sources
    run.transition(DiscoveryState.BASELINE_REQUIRED, "research evidence attached", "E0")


def attach_baseline(run: DiscoveryRun, baseline: dict[str, Any]) -> None:
    if DiscoveryState(run.state) is not DiscoveryState.BASELINE_REQUIRED:
        raise ValueError("baseline can only be attached at BASELINE_REQUIRED")
    required = {"runtime", "session", "page", "account"}
    missing = sorted(required - set(baseline))
    if missing:
        raise ValueError(f"baseline missing fields: {', '.join(missing)}")
    run.findings["baseline"] = baseline
    access = str((baseline.get("session") or {}).get("access_state") or "").upper()
    mapping = {
        "LOGIN_REQUIRED": (DiscoveryState.WAITING_FOR_LOGIN, "login required before exploration"),
        "USER_INTERACTION_REQUIRED": (DiscoveryState.WAITING_FOR_USER_INTERACTION, "user interaction required before exploration"),
        "BLOCKED": (DiscoveryState.BLOCKED, "provider/account access is blocked"),
        "UNKNOWN": (DiscoveryState.DIAGNOSTIC_REQUIRED, "session/access state unresolved"),
    }
    target, reason = mapping.get(access, (DiscoveryState.EXPLORATION_READY, "baseline captured without mutation"))
    run.transition(target, reason, "E1")


def request_rebaseline(run: DiscoveryRun, reason: str = "access condition changed; re-baseline required") -> None:
    state = DiscoveryState(run.state)
    allowed = {DiscoveryState.WAITING_FOR_LOGIN, DiscoveryState.WAITING_FOR_USER_INTERACTION, DiscoveryState.DIAGNOSTIC_REQUIRED, DiscoveryState.BLOCKED}
    if state not in allowed:
        raise ValueError("re-baseline is only valid from an access-gated discovery state")
    run.transition(DiscoveryState.BASELINE_REQUIRED, reason, run.evidence_level)


def begin_exploration(run: DiscoveryRun) -> None:
    run.transition(DiscoveryState.EXPLORING, "controlled exploration started", run.evidence_level)


def attach_exploration(run: DiscoveryRun, findings: dict[str, Any], drift: list[dict[str, Any]]) -> None:
    if DiscoveryState(run.state) is not DiscoveryState.EXPLORING:
        raise ValueError("exploration findings require EXPLORING state")
    run.findings["exploration"] = findings
    run.drift = list(drift)
    run.transition(DiscoveryState.SYNTHESIZING, "exploration evidence captured", "E1")


def synthesize(run: DiscoveryRun) -> None:
    if DiscoveryState(run.state) is not DiscoveryState.SYNTHESIZING:
        raise ValueError("synthesis requires SYNTHESIZING state")
    if run.drift:
        run.candidate = {"kind": "provider_profile_update", "drift": run.drift, "status": "PENDING_REVIEW"}
        run.transition(DiscoveryState.UPDATE_CANDIDATE, "drift requires reviewed update candidate", "E1")
    else:
        run.transition(DiscoveryState.CERTIFICATION_REQUIRED, "no profile drift; live certification still required", "E1")

def review_candidate(run: DiscoveryRun, decision: str, note: str = "") -> None:
    if DiscoveryState(run.state) is not DiscoveryState.UPDATE_CANDIDATE:
        raise ValueError("candidate review requires UPDATE_CANDIDATE state")
    decision = decision.upper().strip()
    if decision not in {"ACCEPT", "HOLD", "REJECT"}:
        raise ValueError("candidate decision must be ACCEPT, HOLD or REJECT")
    run.decision = decision
    if run.candidate is not None:
        run.candidate["status"] = decision
        run.candidate["review_note"] = note
    if decision == "ACCEPT":
        run.transition(DiscoveryState.CERTIFICATION_REQUIRED, "update candidate accepted for certification", "E1")
    elif decision == "HOLD":
        run.transition(DiscoveryState.HOLD, "update candidate held by reviewer", "E1")
    else:
        run.transition(DiscoveryState.REJECTED, "update candidate rejected by reviewer", "E1")


def begin_certification(run: DiscoveryRun) -> None:
    run.transition(DiscoveryState.CERTIFYING, "interactive certification started", run.evidence_level)


def complete_certification(run: DiscoveryRun, passed: bool, evidence_record: str, confirmed_by_user: bool = False, execution_authority: str = "interactive_validation") -> None:
    if DiscoveryState(run.state) is not DiscoveryState.CERTIFYING:
        raise ValueError("certification completion requires CERTIFYING state")
    if execution_authority not in {"automated_validation", "interactive_validation"}:
        raise ValueError("certification execution authority is invalid")
    if passed and execution_authority == "interactive_validation" and not confirmed_by_user:
        raise ValueError("interactive E2 certification pass requires explicit user confirmation")
    if passed and not evidence_record:
        raise ValueError("E2 certification pass requires an evidence record")
    run.findings["certification"] = {
        "passed": bool(passed),
        "evidence_record": evidence_record,
        "execution_authority": execution_authority,
        "confirmed_by_user": bool(confirmed_by_user),
    }
    if passed:
        run.decision = "CERTIFIED"
        run.transition(DiscoveryState.CERTIFIED, "interactive certification passed", "E2")
    else:
        run.decision = "HOLD"
        run.transition(DiscoveryState.HOLD, "interactive certification did not pass", run.evidence_level)
