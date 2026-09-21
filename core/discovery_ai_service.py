"""Execute bounded, approval-gated AI assistance for a Discovery Run."""
from __future__ import annotations

import json
from typing import Any

from core.discovery_ai_assist import AssistanceRequest, ai_assistance_allowed, normalize_ai_finding
from core.discovery_model_router import RouteCandidate, RouteRequest, select_candidate
from core.providers import ChatCompletionRequest
from core.provider_self_use_gate import self_use_status


def _models_for_provider(provider) -> list[str]:
    models = list(getattr(provider.capabilities, "supported_models", []) or [])
    default_model = str((provider.config.config or {}).get("default_model") or "").strip()
    if default_model and default_model not in models:
        models.insert(0, default_model)
    return models


async def _route_candidates(registry) -> list[RouteCandidate]:
    rows=[]
    for provider in registry.list_providers(enabled_only=True):
        try:
            healthy = bool(await provider.health_check())
        except Exception:
            healthy = False
        for model in _models_for_provider(provider):
            rows.append(RouteCandidate(provider.provider_id, model, enabled=True, healthy=healthy, capabilities=("chat",)))
    return rows

def _bounded_evidence(evidence: dict[str, Any], max_chars: int = 12000) -> str:
    raw = json.dumps(evidence, ensure_ascii=False, default=str)
    return raw[:max_chars]


async def execute_ai_assistance(
    registry,
    target_provider_id: str,
    run_id: str,
    unresolved_questions: list[str],
    deterministic_evidence: dict[str, Any],
    *,
    user_approved: bool,
    routing_policy: str = "least_loaded",
    exact_provider_id: str | None = None,
    exact_model: str | None = None,
    allow_target_provider: bool = False,
) -> dict[str, Any]:
    req = AssistanceRequest(
        provider_id=target_provider_id,
        run_id=run_id,
        reason="deterministic discovery left unresolved questions",
        unresolved_questions=list(unresolved_questions),
        deterministic_evidence=deterministic_evidence,
        user_approved=user_approved,
    )
    allowed, reason = ai_assistance_allowed(req)
    if not allowed:
        raise PermissionError(reason)

    candidates = await _route_candidates(registry)
    route_req = RouteRequest(
        purpose="discovery_ai_assistance",
        required_capabilities=("chat",),
        exact_provider_id=exact_provider_id,
        exact_model=exact_model,
        avoid_provider_id=None if allow_target_provider or exact_provider_id else target_provider_id,
    )
    try:
        selected = select_candidate(candidates, route_req, routing_policy)
    except LookupError:
        if exact_provider_id or not allow_target_provider:
            raise
        fallback_req = RouteRequest(
            purpose="discovery_ai_assistance",
            required_capabilities=("chat",),
            exact_provider_id=target_provider_id,
            exact_model=exact_model,
        )
        selected = select_candidate(candidates, fallback_req, routing_policy)

    provider = registry.get(selected.provider_id)
    if provider is None:
        raise LookupError("selected provider disappeared")
    target_gate = None
    if selected.provider_id == target_provider_id:
        target_gate = self_use_status(provider)
        if not target_gate["allowed"]:
            raise PermissionError("target_provider_transport_not_qualified:" + ",".join(target_gate["reasons"]))

    prompt = (
        "Analyze this governed Web Chat discovery evidence. Do not invent observations. "
        "Identify ambiguities, likely explanations, and the smallest next deterministic or browser-behavior probes needed. "
        "Do not recommend bypassing CAPTCHA, access controls, rate limits, suspension, or provider safeguards.\n\n"
        f"Target provider: {target_provider_id}\n"
        f"Unresolved questions: {json.dumps(unresolved_questions, ensure_ascii=False)}\n"
        f"Evidence: {_bounded_evidence(deterministic_evidence)}"
    )
    response = await provider.chat_completion(ChatCompletionRequest(
        model=selected.model,
        messages=[{"role":"system","content":"You are a cautious discovery analyst. Evidence first; proposals are candidates only."},
                  {"role":"user","content":prompt}],
        stream=False,
        max_tokens=1200,
    ))
    text = ""
    if response.choices:
        text = response.choices[0].message.content or ""
    finding = normalize_ai_finding(selected.model, selected.provider_id, {
        "target_provider": target_provider_id,
        "analysis": text,
        "unresolved_questions": unresolved_questions,
    })
    finding["routing_policy"] = routing_policy
    finding["target_provider_avoided"] = selected.provider_id != target_provider_id
    finding["approval"] = {"mode": req.approval_mode, "user_approved": user_approved}
    if target_gate is not None:
        rec = target_gate.get("record") or {}
        finding["self_use_transport_gate"] = {"qualified": True, "gate_version": rec.get("gate_version"), "recorded_at": rec.get("recorded_at"), "transport_fingerprint": rec.get("transport_fingerprint")}
    return finding
