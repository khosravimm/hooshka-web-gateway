"""Fail-closed tool allowlist policy (ported from hwg-next-0.9.3).

Rules:
- An empty allowlist is NEVER a wildcard: any recognized call is rejected.
- Unknown tool names are dropped (never executed).
- Recognized-but-unparseable tool syntax raises instead of being silently
  treated as prose.
"""

from __future__ import annotations


class ToolProtocolError(RuntimeError):
    pass


def filter_calls_by_allowlist(calls: list[dict] | None, allowed: set[str]) -> list[dict]:
    """Keep only calls whose name is in the allowlist.

    An empty allowlist matches nothing. Raises ToolProtocolError when calls
    were recognized but none survive filtering.
    """
    if not calls:
        return []
    if not allowed:
        raise ToolProtocolError("tool calls recognized but allowlist is empty")
    kept = [c for c in calls if _call_name(c) in allowed]
    if calls and not kept:
        raise ToolProtocolError("tool calls recognized but none are allowlisted")
    return kept


def _call_name(call: dict) -> str | None:
    fn = call.get("function") if isinstance(call.get("function"), dict) else call
    if isinstance(fn, dict):
        return fn.get("name")
    return call.get("name")
