"""Account-centric session lifecycle normalization for HWG."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

SESSION_CONTRACT_VERSION = "1.0.0"
ACCESS_STATES = {
    "UNKNOWN",
    "LOGIN_REQUIRED",
    "USER_INTERACTION_REQUIRED",
    "AUTHENTICATED",
    "BLOCKED",
    "EXPIRED",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _legacy_state(access_state: str) -> str:
    return {
        "AUTHENTICATED": "authenticated",
        "LOGIN_REQUIRED": "auth_required",
        "USER_INTERACTION_REQUIRED": "blocked",
        "BLOCKED": "blocked",
        "EXPIRED": "expired",
    }.get(access_state, "unknown")

def normalize_session(
    provider_status: dict[str, Any] | None,
    access_state: str | None = None,
    previous_access_state: str | None = None,
) -> dict[str, Any]:
    status = dict(provider_status or {})
    access = str(access_state or status.get("access_state") or "UNKNOWN").upper()
    if access not in ACCESS_STATES:
        access = "UNKNOWN"

    authenticated = status.get("authenticated") is True
    if access == "UNKNOWN" and authenticated:
        access = "AUTHENTICATED"
    elif access == "UNKNOWN" and previous_access_state == "AUTHENTICATED" and status.get("authenticated") is False:
        access = "EXPIRED"

    reason = status.get("reason") or status.get("error") or status.get("message")
    return {
        "contract_version": SESSION_CONTRACT_VERSION,
        "access_state": access,
        "state": _legacy_state(access),
        "authenticated": access == "AUTHENTICATED",
        "reason": str(reason) if reason else None,
        "validated_at": _now(),
        "evidence": {
            "provider_authenticated": status.get("authenticated"),
            "composer_ready": status.get("composer_ready"),
            "source_access_state": access_state,
        },
    }
