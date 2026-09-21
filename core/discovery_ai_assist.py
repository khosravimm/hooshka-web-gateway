"""Approval-gated AI assistance for Discovery Engine.

AI is secondary to deterministic probes. Findings produced by an AI model are
never promoted directly to provider/profile truth without evidence validation.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass
class AssistanceRequest:
    provider_id: str
    run_id: str
    reason: str
    unresolved_questions: list[str]
    deterministic_evidence: dict[str, Any]
    approval_mode: str = "explicit"  # explicit|session_grant|disabled
    user_approved: bool = False
    requested_at: str = ""

    def __post_init__(self):
        if not self.requested_at:
            self.requested_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def to_dict(self):
        return asdict(self)


def ai_assistance_allowed(req: AssistanceRequest) -> tuple[bool, str]:
    if req.approval_mode == "disabled":
        return False, "ai_assistance_disabled"
    if not req.unresolved_questions:
        return False, "deterministic_work_complete"
    if req.approval_mode in {"explicit", "session_grant"} and not req.user_approved:
        return False, "user_approval_required"
    return True, "approved_secondary_assistance"


def normalize_ai_finding(model_ref: str, provider_ref: str, finding: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": "ai_assistance",
        "model": model_ref,
        "provider": provider_ref,
        "evidence_level": "E0",
        "status": "CANDIDATE",
        "finding": finding,
        "validation_required": True,
    }
