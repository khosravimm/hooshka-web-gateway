"""Policy router for governed AI-assisted discovery workloads.

The router is for resilience/load distribution while respecting provider
limits and exact-routing semantics. It must never bypass provider challenges,
suspensions, rate limits, or access controls.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable


@dataclass(frozen=True)
class RouteCandidate:
    provider_id: str
    model: str
    enabled: bool = True
    healthy: bool = True
    capabilities: tuple[str, ...] = ()
    inflight: int = 0
    weight: int = 1
    cooldown_until: str | None = None


@dataclass(frozen=True)
class RouteRequest:
    purpose: str
    required_capabilities: tuple[str, ...] = ()
    exact_provider_id: str | None = None
    exact_model: str | None = None
    avoid_provider_id: str | None = None

def _cooling_down(candidate: RouteCandidate, now: datetime | None = None) -> bool:
    if not candidate.cooldown_until:
        return False
    now = now or datetime.now(timezone.utc)
    try:
        until = datetime.fromisoformat(candidate.cooldown_until.replace("Z", "+00:00"))
    except ValueError:
        return True
    return until > now


def eligible_candidates(candidates: Iterable[RouteCandidate], request: RouteRequest) -> list[RouteCandidate]:
    result=[]
    required=set(request.required_capabilities)
    for c in candidates:
        if request.exact_provider_id and c.provider_id != request.exact_provider_id:
            continue
        if not request.exact_provider_id and request.avoid_provider_id and c.provider_id == request.avoid_provider_id:
            continue
        if request.exact_model and c.model != request.exact_model:
            continue
        if not c.enabled or not c.healthy or _cooling_down(c):
            continue
        if not required.issubset(set(c.capabilities)):
            continue
        result.append(c)
    return result


def select_candidate(candidates: Iterable[RouteCandidate], request: RouteRequest, policy: str = "least_loaded") -> RouteCandidate:
    eligible = eligible_candidates(candidates, request)
    if not eligible:
        scope = request.exact_provider_id or "eligible provider"
        raise LookupError(f"no route candidate for {scope}")
    if request.exact_provider_id or request.exact_model:
        return eligible[0]
    if policy == "ordered":
        return eligible[0]
    if policy == "least_loaded":
        return sorted(eligible, key=lambda c: (c.inflight, -c.weight, c.provider_id, c.model))[0]
    if policy == "weighted_load":
        return sorted(eligible, key=lambda c: (c.inflight / max(c.weight, 1), c.provider_id, c.model))[0]
    raise ValueError(f"unsupported routing policy: {policy}")
