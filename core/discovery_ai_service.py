"""Execute bounded, approval-gated AI assistance for a Discovery Run."""
from __future__ import annotations

import json
from pathlib import Path
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
        caps=["chat"]
        if bool(getattr(provider.capabilities,"vision",False)):
            caps.append("vision")
        for model in _models_for_provider(provider):
            rows.append(RouteCandidate(provider.provider_id, model, enabled=True, healthy=healthy, capabilities=tuple(caps)))
    return rows

def _bounded_evidence(evidence: dict[str, Any], max_chars: int = 12000) -> str:
    raw = json.dumps(evidence, ensure_ascii=False, default=str)
    return raw[:max_chars]


def _parse_structured_analysis(text: str) -> dict[str, Any]:
    raw = str(text or "").strip()
    candidates = [raw]
    if "```" in raw:
        for part in raw.split("```"):
            part = part.strip()
            if part.lower().startswith("json"):
                part = part[4:].strip()
            if part.startswith("{"):
                candidates.append(part)
    for item in candidates:
        try:
            obj = json.loads(item)
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass
    return {"summary": raw[:4000], "hypotheses": []}


def _normalize_hypotheses(raw_hypotheses:list[Any]) -> tuple[list[dict[str,Any]],list[dict[str,Any]],list[dict[str,Any]]]:
    hypotheses=[]
    for item in raw_hypotheses:
        if not isinstance(item,dict):
            continue
        probe=str(item.get("next_probe") or "").strip().lower()
        target=str(item.get("target") or "").strip()
        if not target or probe not in {"inspect","hover","focus","click"}:
            continue
        confidence=str(item.get("confidence") or "low").strip().lower()
        if confidence not in {"low","medium","high"}: confidence="low"
        hypotheses.append({"target":target,"meaning":str(item.get("meaning") or "").strip(),"confidence":confidence,"evidence_refs":[str(x) for x in (item.get("evidence_refs") or [])][:12],"next_probe":probe,"rationale":str(item.get("rationale") or "").strip(),"status":"CANDIDATE","evidence_level":"E0"})
    auto_safe=[h for h in hypotheses if h["next_probe"] in {"inspect","hover","focus"}]
    approval_required=[h for h in hypotheses if h["next_probe"]=="click"]
    return hypotheses,auto_safe,approval_required


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
    visual_evidence_paths: list[str] | None = None,
    require_vision: bool = False,
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
    visual_paths=[str(Path(x).resolve()) for x in (visual_evidence_paths or []) if Path(x).is_file()]
    if require_vision and not visual_paths:
        raise FileNotFoundError("visual_evidence_required")
    required_caps=("chat","vision") if require_vision else ("chat",)
    route_req = RouteRequest(
        purpose="discovery_ai_assistance",
        required_capabilities=required_caps,
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
            required_capabilities=required_caps,
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
        "Identify ambiguities, likely explanations, and the smallest next deterministic or browser-behavior probes needed. Return strict JSON only with keys summary and hypotheses. Each hypothesis must contain target (the control_id only, never a selector), meaning, confidence (low|medium|high), evidence_refs (array of short IDs such as control:unclassified-1 or behavior:1; never copy raw evidence text), next_probe (inspect|hover|focus|click), and rationale. Do not put unescaped quotes inside string values. "
        "Do not recommend bypassing CAPTCHA, access controls, rate limits, suspension, or provider safeguards.\n\n"
        f"Target provider: {target_provider_id}\n"
        f"Unresolved questions: {json.dumps(unresolved_questions, ensure_ascii=False)}\n"
        f"Evidence: {_bounded_evidence(deterministic_evidence)}"
        + ("\nA screenshot is attached as governed visual evidence. Analyze it only as supplemental evidence and distinguish visual observations from deterministic evidence." if visual_paths else "")
    )
    response = await provider.chat_completion(ChatCompletionRequest(
        model=selected.model,
        messages=[{"role":"system","content":"You are a cautious discovery analyst. Evidence first; proposals are candidates only."},
                  {"role":"user","content":prompt}],
        stream=False,
        max_tokens=1200,
        provider_options={"file_paths":visual_paths} if visual_paths else None,
    ))
    text = ""
    if response.choices:
        text = response.choices[0].message.content or ""
    structured = _parse_structured_analysis(text)
    raw_hypotheses = structured.get("hypotheses") if isinstance(structured.get("hypotheses"), list) else []
    hypotheses, auto_safe, approval_required = _normalize_hypotheses(raw_hypotheses)
    finding = normalize_ai_finding(selected.model, selected.provider_id, {
        "target_provider": target_provider_id,
        "analysis": text,
        "structured": structured,
        "hypotheses": hypotheses,
        "verification_queue": hypotheses,
        "auto_safe_queue": auto_safe,
        "approval_required_queue": approval_required,
        "hypothesis_contract_version": "1.0.0",
        "unresolved_questions": unresolved_questions,
    })
    finding["routing_policy"] = routing_policy
    finding["target_provider_avoided"] = selected.provider_id != target_provider_id
    finding["approval"] = {"mode": req.approval_mode, "user_approved": user_approved}
    finding["visual_evidence"]={"attached":bool(visual_paths),"count":len(visual_paths),"vision_required":bool(require_vision)}
    if target_gate is not None:
        rec = target_gate.get("record") or {}
        finding["self_use_transport_gate"] = {"qualified": True, "gate_version": rec.get("gate_version"), "recorded_at": rec.get("recorded_at"), "transport_fingerprint": rec.get("transport_fingerprint")}
    return finding
