"""Shared upstream response classification for unofficial Web Chat transports.

This module performs content-type and application-envelope checks before a
provider hands a response to an SSE parser. It deliberately does not contain
provider credentials or transport retry policy.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional


@dataclass(frozen=True)
class UpstreamDisposition:
    kind: str
    code: str
    terminal: bool
    retryable: bool = False
    details: dict[str, Any] = field(default_factory=dict)


def classify_initial_response(
    *,
    http_status: int,
    content_type: str | None,
    json_body: Optional[Mapping[str, Any]] = None,
) -> UpstreamDisposition:
    """Classify headers/application envelope before streaming begins.

    Secrets and arbitrary upstream body text are intentionally excluded from
    returned details so callers can safely audit the classification.
    """
    ctype = (content_type or "").split(";", 1)[0].strip().lower()

    if http_status in (401, 403):
        return UpstreamDisposition("failure", "auth", True, False, {"http_status": http_status})
    if http_status == 429:
        return UpstreamDisposition("failure", "rate_limit", True, True, {"http_status": http_status})
    if http_status >= 500:
        return UpstreamDisposition("failure", "provider_wide", True, True, {"http_status": http_status})
    if http_status < 200 or http_status >= 300:
        return UpstreamDisposition("failure", "upstream_http", True, False, {"http_status": http_status})

    if json_body is not None:
        data = json_body.get("data") if isinstance(json_body, Mapping) else None
        biz_code = data.get("biz_code") if isinstance(data, Mapping) else None
        biz_msg = data.get("biz_msg") if isinstance(data, Mapping) else None
        biz_data = data.get("biz_data") if isinstance(data, Mapping) else None
        if isinstance(biz_data, Mapping) and biz_data.get("is_muted"):
            details = {"http_status": http_status, "biz_code": biz_code, "account_state": "muted"}
            if biz_data.get("mute_until") is not None:
                details["has_mute_until"] = True
            return UpstreamDisposition("failure", "account_local_muted", True, False, details)
        if biz_code not in (None, 0):
            return UpstreamDisposition(
                "failure", "application_error", True, False,
                {"http_status": http_status, "biz_code": biz_code, "has_biz_msg": bool(biz_msg)},
            )
        code = json_body.get("code") if isinstance(json_body, Mapping) else None
        if code not in (None, 0):
            return UpstreamDisposition("failure", "application_error", True, False, {"http_status": http_status, "code": code})

    if ctype == "text/event-stream":
        return UpstreamDisposition("stream", "sse", False)
    if ctype in ("application/json", "application/problem+json"):
        return UpstreamDisposition("json", "json_success", True)
    return UpstreamDisposition("unknown", "unexpected_content_type", True, False, {"http_status": http_status, "content_type": ctype})
