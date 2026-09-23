"""Read-only live probes used by the governed Discovery pipeline.

This module never submits prompts, changes provider controls, applies profile
updates, or captures storage values/secrets. It only observes the already-owned
provider runtime and returns bounded metadata to a Discovery Run.
"""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright

from core.discovery_engine import discover_page, diff_drift
from core.visual_discovery import capture_user_view, classify_user_view_state
from core.visual_discovery import capture_user_view

PROFILE_ROOT = Path(__file__).resolve().parents[1] / "docs" / "profiles"


def _host(url: str) -> str:
    try:
        return urlparse(url).hostname or ""
    except Exception:
        return ""


def _latest_discovery(provider_id: str) -> dict:
    root = PROFILE_ROOT / provider_id
    files = sorted(root.glob("discovery.v*.json")) if root.exists() else []
    if not files:
        return {}
    try:
        return json.loads(files[-1].read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def _flatten(report: dict) -> dict:
    return {
        "controls": ((report.get("frontend") or {}).get("controls") or []),
        "upload_surface": ((report.get("frontend") or {}).get("upload_surface") or {}),
        "candidate_endpoints": ((report.get("backend") or {}).get("candidate_endpoints") or []),
    }


async def explore_cdp(provider_id: str, cdp_url: str, home_url: str) -> tuple[dict, list[dict]]:
    """Observe one existing owned browser runtime without changing page state."""
    home_host = urlparse(home_url).hostname or ""
    async with async_playwright() as pw:
        browser = await pw.chromium.connect_over_cdp(cdp_url, timeout=15000)
        if not browser.contexts:
            raise RuntimeError("owned runtime has no browser context")
        context = browser.contexts[0]
        pages = [p for p in context.pages if home_host and home_host in (p.url or "")]
        if not pages:
            pages = list(context.pages)
        if not pages:
            raise RuntimeError("owned runtime has no page")
        report = await discover_page(pages[0], provider_id)
        from core.media_qualification import observe_file_upload_surface
        media_surface = await observe_file_upload_surface(pages[0])
        user_view = await capture_user_view(pages[0], provider_id, "discovery-user-view")
        user_view["classification"] = classify_user_view_state(user_view)
        visual_observation = await capture_user_view(pages[0], provider_id, "discovery-read-only")

    findings = {
        "page_url": report.page_url,
        "engine_version": report.engine_version,
        "discovered_at": report.discovered_at,
        "frontend": report.frontend,
        "backend": report.backend,
        "capabilities": report.capabilities,
        "media_upload_surface": media_surface,
        "user_view": user_view,
        "visual_observation": visual_observation,
    }
    old = _flatten(_latest_discovery(provider_id))
    drift = diff_drift(old, _flatten(findings))
    return findings, drift


async def probe_cdp_behavior(provider_id: str, cdp_url: str, home_url: str, action, policy):
    """Run one governed hover/focus/click behavior observation on provider page."""
    from playwright.async_api import async_playwright
    from core.browser_behavior_probe import run_behavior_probe
    host = _host(home_url)
    async with async_playwright() as pw:
        browser = await pw.chromium.connect_over_cdp(cdp_url, timeout=20000)
        ctx = browser.contexts[0] if browser.contexts else None
        if ctx is None:
            raise RuntimeError(f"no browser context on {cdp_url}")
        pages = [p for p in ctx.pages if host and host in _host(p.url)] or ctx.pages[:1]
        if not pages:
            raise RuntimeError(f"no provider page for {provider_id}")
        return await run_behavior_probe(pages[0], action, policy)
