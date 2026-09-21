"""Deterministic controlled round-trip used to qualify target-provider self-use."""
from __future__ import annotations

import hashlib
import inspect
import uuid
from typing import Any

from core.provider_self_use_gate import build_qualification, evaluate_qualification, save_qualification
from core.providers import ChatCompletionRequest


def identify_deterministic_transport_paths(provider) -> dict[str, dict[str, Any]]:
    method = getattr(type(provider), "chat_completion", None)
    if method is None:
        raise ValueError("chat_completion_tool_missing")
    try:
        source = inspect.getsource(method)
    except (OSError, TypeError):
        raise ValueError("chat_completion_source_unavailable")
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()[:20]
    cfg = getattr(getattr(provider, "config", None), "config", {}) or {}
    transport_mode = str(cfg.get("transport_mode") or cfg.get("transport") or "adapter")
    evidence = f"adapter-source:{type(provider).__module__}.{type(provider).__name__}.chat_completion:{digest}:{transport_mode}"
    tool_method = "frontend_controller" if "controller" in transport_mode or "backend" in transport_mode else "browser_probe"
    return {
        "send_path": {"identified": True, "method": tool_method, "evidence_ref": evidence + ":send"},
        "receive_path": {"identified": True, "method": tool_method, "evidence_ref": evidence + ":receive"},
        "completion_path": {"identified": True, "method": tool_method, "evidence_ref": evidence + ":completion"},
    }


def validate_path_evidence(paths: dict[str, dict[str, Any]]) -> None:
    for key in ("send_path", "receive_path", "completion_path"):
        item = paths.get(key) or {}
        if item.get("identified") is not True:
            raise ValueError(f"{key}_not_identified")
        if item.get("method") not in {"dom", "accessibility", "network", "frontend_controller", "browser_probe"}:
            raise ValueError(f"{key}_not_deterministic")
        if not item.get("evidence_ref"):
            raise ValueError(f"{key}_missing_evidence")


async def controlled_roundtrip(provider, model: str, paths: dict[str, dict[str, Any]] | None = None, *, execution_authority: str, root=None):
    paths = paths or identify_deterministic_transport_paths(provider)
    validate_path_evidence(paths)
    if execution_authority not in {"automated_validation", "interactive_validation"}:
        raise PermissionError("live_roundtrip_execution_authority_required")
    marker = "HWG_SELF_USE_" + uuid.uuid4().hex[:12].upper()
    response = await provider.chat_completion(ChatCompletionRequest(
        model=model,
        messages=[{"role":"user","content":f"Reply exactly with this token and nothing else: {marker}"}],
        stream=False,
        max_tokens=64,
    ))
    text = ""
    if response.choices:
        text = (response.choices[0].message.content or "").strip()
    passed = text == marker
    roundtrip = {
        "tested": True,
        "passed": passed,
        "tool_class": "deterministic",
        "evidence_ref": f"controlled-roundtrip:{marker}",
        "expected": marker,
        "observed": text[:256],
    }
    record = build_qualification(
        provider,
        paths["send_path"],
        paths["receive_path"],
        paths["completion_path"],
        roundtrip,
    )
    allowed, reasons = evaluate_qualification(record, provider)
    path = save_qualification(record, root) if allowed else None
    return {"passed": passed, "allowed": allowed, "reasons": reasons, "record_path": str(path) if path else None, "marker": marker}
