"""Governed interactive browser-behavior probes for Discovery Engine.

Hover/focus are read-only defaults. Click is opt-in and blocked for submit/send,
destructive, auth-exit, or purchase-like surfaces. Observations are bounded and
metadata-first; no secret/storage values are collected.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import re
from typing import Any

DANGEROUS_LABEL = re.compile(
    r"\b(send|submit|delete|remove|logout|log out|sign out|purchase|buy|pay|confirm|terminate)\b|ارسال|حذف|خروج|پرداخت",
    re.I,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class ProbePolicy:
    allow_hover: bool = True
    allow_focus: bool = True
    allow_click: bool = False
    max_network_events: int = 50
    max_websockets: int = 10
    settle_ms: int = 500

@dataclass
class BehaviorAction:
    kind: str  # hover|focus|click
    selector: str
    purpose: str
    risk_class: str = "read_only"


@dataclass
class BehaviorObservation:
    action: dict[str, Any]
    started_at: str
    completed_at: str
    before: dict[str, Any]
    after: dict[str, Any]
    network: list[dict[str, Any]] = field(default_factory=list)
    websockets: list[dict[str, Any]] = field(default_factory=list)
    sse: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def click_guard(meta: dict[str, Any], policy: ProbePolicy) -> tuple[bool, str]:
    if not policy.allow_click:
        return False, "click_not_approved"
    label = " ".join(str(meta.get(k) or "") for k in ("text", "aria", "title", "name"))
    if DANGEROUS_LABEL.search(label):
        return False, "dangerous_semantics"
    if str(meta.get("type") or "").lower() == "submit":
        return False, "submit_control"
    if bool(meta.get("destructive")):
        return False, "destructive_control"
    return True, "approved_reversible_click"

SNAPSHOT_JS = r"""(selector) => {
  const e = document.querySelector(selector);
  if (!e) return {found:false};
  const r = e.getBoundingClientRect();
  return {
    found:true, tag:e.tagName, text:(e.innerText||'').trim().replace(/\s+/g,' ').slice(0,120),
    aria:(e.getAttribute('aria-label')||'').slice(0,120), title:(e.getAttribute('title')||'').slice(0,120),
    role:e.getAttribute('role')||'', type:e.getAttribute('type')||'', name:e.getAttribute('name')||'',
    pressed:e.getAttribute('aria-pressed'), expanded:e.getAttribute('aria-expanded'), checked:e.getAttribute('aria-checked'),
    disabled:e.disabled===true || e.getAttribute('aria-disabled')==='true',
    visible:r.width>0 && r.height>0, x:Math.round(r.x), y:Math.round(r.y), width:Math.round(r.width), height:Math.round(r.height),
    active:document.activeElement===e,
    page_text_tail:(document.body?.innerText||'').slice(-5000),
    page_text_length:(document.body?.innerText||'').length
  };
}"""


async def _snapshot(page, selector: str) -> dict[str, Any]:
    return await page.evaluate(SNAPSHOT_JS, selector)


async def run_behavior_probe(page, action: BehaviorAction, policy: ProbePolicy | None = None) -> BehaviorObservation:
    policy = policy or ProbePolicy()
    if action.kind not in {"hover", "focus", "click"}:
        raise ValueError("unsupported behavior action")
    if action.kind == "hover" and not policy.allow_hover:
        raise PermissionError("hover_not_approved")
    if action.kind == "focus" and not policy.allow_focus:
        raise PermissionError("focus_not_approved")

    before = await _snapshot(page, action.selector)
    if not before.get("found") or not before.get("visible"):
        raise ValueError("target_not_visible")
    if action.kind == "click":
        allowed, reason = click_guard(before, policy)
        if not allowed:
            raise PermissionError(reason)

    network: list[dict[str, Any]] = []
    websockets: list[dict[str, Any]] = []
    sse: list[dict[str, Any]] = []

    def on_request(req):
        if len(network) < policy.max_network_events:
            network.append({"method": req.method, "url": req.url, "resource_type": req.resource_type})

    def on_websocket(ws):
        if len(websockets) < policy.max_websockets:
            websockets.append({"url": ws.url})

    async def on_response(resp):
        if len(sse) >= policy.max_network_events:
            return
        try:
            ctype = (await resp.header_value("content-type")) or ""
            if "text/event-stream" in ctype.lower():
                sse.append({"url": resp.url, "status": resp.status, "content_type": ctype[:120]})
        except Exception:
            return

    page.on("request", on_request)
    page.on("websocket", on_websocket)
    page.on("response", on_response)
    started = _now()
    locator = page.locator(action.selector).first
    try:
        if action.kind == "hover":
            await locator.hover(timeout=5000)
        elif action.kind == "focus":
            await locator.focus(timeout=5000)
        else:
            await locator.click(timeout=5000, no_wait_after=True)
        await page.wait_for_timeout(policy.settle_ms)
        after = await _snapshot(page, action.selector)
    finally:
        page.remove_listener("request", on_request)
        page.remove_listener("websocket", on_websocket)
        page.remove_listener("response", on_response)

    return BehaviorObservation(
        action=asdict(action), started_at=started, completed_at=_now(),
        before=before, after=after, network=network, websockets=websockets, sse=sse,
    )
