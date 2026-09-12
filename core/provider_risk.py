
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ProviderRiskSignal:
    kind: str
    failure_class: str
    message: str
    wait_hours: Optional[int] = None


_QUOTA_PATTERNS = [
    r"daily\s+usage\s+limit",
    r"usage\s+limit",
    r"quota(?:\s+limit)?",
    r"high\s+demand",
    r"too\s+many\s+requests",
    r"rate\s+limit",
    r"please\s+wait\s+\d+\s+hours?",
    r"wait\s+\d+\s+hours?",
]

_CHALLENGE_PATTERNS = [
    r"please\s+drag\s+the\s+slider",
    r"please\s+slide\s+to\s+verify",
    r"slide\s+to\s+verify",
    r"complete\s+the\s+verification",
    r"human\s+verification",
    r"captcha",
    r"cloudflare",
    r"unusual\s+traffic",
]


def _wait_hours(text: str) -> Optional[int]:
    m = re.search(r"(?:please\s+)?wait\s+(\d+)\s+hours?", text, re.I)
    return int(m.group(1)) if m else None


def detect_provider_risk(text: object) -> Optional[ProviderRiskSignal]:
    """Classify provider UI/upstream risk-control text without bypassing it.

    Returns None for ordinary model text. Quota/rate-limit states are classified
    separately from CAPTCHA/challenge states so KiloGate-WM reports do not count
    them as model capability failures.
    """
    if text is None:
        return None
    raw = str(text)
    if not raw.strip():
        return None
    lower = raw.lower()
    if any(re.search(p, lower, re.I) for p in _CHALLENGE_PATTERNS):
        return ProviderRiskSignal(
            kind="challenge",
            failure_class="risk_control_challenge_visible",
            message="Provider human-verification/CAPTCHA challenge observed.",
        )
    if any(re.search(p, lower, re.I) for p in _QUOTA_PATTERNS):
        hours = _wait_hours(raw)
        msg = "Provider quota/usage-limit/high-demand state observed."
        if hours is not None:
            msg += f" Wait window: {hours} hours."
        return ProviderRiskSignal(
            kind="quota_limit",
            failure_class="quota_limit_observed",
            message=msg,
            wait_hours=hours,
        )
    return None
