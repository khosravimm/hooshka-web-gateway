"""Governed provider tool-call qualification probe.

The probe proves whether a provider can emit a structurally valid forced
function call. It never executes the requested function and never asks for a
privileged or state-changing operation.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import uuid

from core.providers import ChatCompletionRequest

PROBE_SCHEMA_VERSION = "1.0.0"
PROBE_TOOL_NAME = "hwg_tool_capability_probe"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def probe_tool_definition() -> dict:
    return {
        "type": "function",
        "function": {
            "name": PROBE_TOOL_NAME,
            "description": "Return the exact discovery marker as a tool argument. This tool is never executed.",
            "parameters": {
                "type": "object",
                "properties": {"marker": {"type": "string"}},
                "required": ["marker"],
                "additionalProperties": False,
            },
        },
    }


def _decode_arguments(raw) -> dict:
    if isinstance(raw, dict):
        return dict(raw)
    if not isinstance(raw, str):
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _first_tool_call(response) -> dict | None:
    if not getattr(response, "choices", None):
        return None
    message = response.choices[0].message
    calls = getattr(message, "tool_calls", None) or []
    return calls[0] if calls else None


async def probe_provider_tool_call(provider, model: str) -> dict:
    """Run one forced, non-executed tool-call probe and return bounded evidence."""
    marker = "HWG_TOOL_PROBE_" + uuid.uuid4().hex[:12].upper()
    started_at = _now()
    result = {
        "schema_version": PROBE_SCHEMA_VERSION,
        "tested_at": started_at,
        "provider_id": getattr(provider, "provider_id", None),
        "model": model,
        "probe_tool": PROBE_TOOL_NAME,
        "tested": True,
        "supported": False,
        "evidence_level": "E2",
        "execution": "not_executed",
        "marker_match": False,
        "protocol_valid": False,
    }
    try:
        response = await provider.chat_completion(ChatCompletionRequest(
            model=model,
            messages=[{"role": "user", "content": (
                "Capability qualification only. Call the required function exactly once "
                f"with marker={marker}. Do not answer in prose."
            )}],
            tools=[probe_tool_definition()],
            tool_choice={"type": "function", "function": {"name": PROBE_TOOL_NAME}},
            stream=False,
            max_tokens=128,
        ))
        call = _first_tool_call(response)
        if not call:
            result["reason"] = "no_tool_call_returned"
            return result
        fn = call.get("function") or call
        name = str(fn.get("name") or "")
        args = _decode_arguments(fn.get("arguments"))
        result["returned_tool"] = name
        result["protocol_valid"] = name == PROBE_TOOL_NAME
        result["marker_match"] = args.get("marker") == marker
        result["supported"] = bool(result["protocol_valid"] and result["marker_match"])
        result["reason"] = "forced_tool_call_valid" if result["supported"] else "tool_call_mismatch"
        return result
    except Exception as exc:
        result["reason"] = "probe_failed"
        result["error_type"] = type(exc).__name__
        result["error_code"] = getattr(exc, "code", None)
        return result
