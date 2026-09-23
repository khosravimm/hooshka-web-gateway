from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse

from core.visual_discovery import visible_page_state, visible_interaction_map, classify_user_view_state

SCHEMA_VERSION = "1.0.0"
KNOWN_ORIGINS = {
    "chatgpt.com": "chatgpt_web",
    "chat.deepseek.com": "deepseek_web",
    "chat.qwen.ai": "qwen_web",
    "chat.z.ai": "zai_web",
}

def normalize_chat_url(raw: str) -> str:
    value = str(raw or "").strip()
    if not value:
        raise ValueError("web chat URL is required")
    if "://" not in value:
        value = "https://" + value
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("a valid http/https web chat URL is required")
    host = parsed.hostname.lower()
    port = f":{parsed.port}" if parsed.port else ""
    path = parsed.path or "/"
    return urlunparse((parsed.scheme.lower(), host + port, path, "", parsed.query, ""))


def _slug_host(host: str) -> str:
    parts = [p for p in host.lower().split(".") if p and p not in {"www", "chat", "app"}]
    stem = parts[0] if parts else "provider"
    stem = re.sub(r"[^a-z0-9]+", "-", stem).strip("-") or "provider"
    return f"{stem}-web"

def analyze_url(raw_url: str, runtimes: list[dict[str, Any]], existing_ids: list[str]) -> dict[str, Any]:
    url = normalize_chat_url(raw_url)
    parsed = urlparse(url)
    host = parsed.hostname or ""
    known_type = KNOWN_ORIGINS.get(host)
    base_id = _slug_host(host)
    same_origin = []
    origin = f"{parsed.scheme}://{parsed.netloc}"
    for runtime in runtimes:
        for provider in runtime.get("providers") or []:
            try:
                purl = normalize_chat_url(provider.get("home_url") or "")
                pp = urlparse(purl)
                if f"{pp.scheme}://{pp.netloc}" == origin:
                    same_origin.append(provider.get("id"))
            except ValueError:
                pass
    suggested_id = base_id
    n = 2
    while suggested_id in set(existing_ids):
        suggested_id = f"{base_id}-{n}"; n += 1
    ready = [r for r in runtimes if r.get("ready")]
    shared = [r for r in ready if r.get("shared")]
    recommended = (shared or ready or runtimes or [None])[0]
    return {
        "schema_version": SCHEMA_VERSION,
        "url": url,
        "origin": origin,
        "host": host,
        "known_adapter_type": known_type,
        "reuse_existing_adapter": bool(known_type),
        "suggested_provider_id": suggested_id,
        "suggested_name": base_id.removesuffix("-web").replace('-', ' ').title() or suggested_id,
        "recommended_runtime_key": recommended.get("runtime_key") if recommended else None,
        "recommended_runtime": recommended,
        "existing_origin_provider_ids": [x for x in same_origin if x],
        "recommendation": "use_existing_provider" if same_origin else ("reuse_adapter" if known_type else "discovery_candidate"),
        "register_new_provider": not bool(same_origin),
        "next_action": "use_existing_provider_account" if same_origin else "observe_user_view",
    }


def candidate_path(root: Path, candidate_id: str) -> Path:
    folder = root / ".runtime-dev" / "provider-onboarding"
    folder.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^a-zA-Z0-9._-]+", "-", candidate_id).strip("-") or "candidate"
    return folder / f"{safe}.json"

async def observe_url(url: str, cdp_url: str) -> dict[str, Any]:
    from playwright.async_api import async_playwright

    pw = await async_playwright().start()
    browser = await pw.chromium.connect_over_cdp(cdp_url)
    context = browser.contexts[0]
    page = await context.new_page()
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    except Exception:
        pass
    try:
        await page.wait_for_timeout(3500)
        state = await visible_page_state(page)
        interaction_map = await visible_interaction_map(page)
        classification = classify_user_view_state(state)
        file_inputs = await page.locator('input[type="file"]').count()
        editable = await page.locator('textarea:visible,[contenteditable="true"]:visible,input[type="text"]:visible').count()
        selects = await page.locator('select:visible,[role="combobox"]:visible').count()
        return {
            "schema_version": SCHEMA_VERSION,
            "final_url": page.url,
            "title": await page.title(),
            "classification": classification,
            "user_view": state,
            "interaction_summary": {
                "controls": len(interaction_map.get("controls") or []),
                "headings": len(interaction_map.get("headings") or []),
                "horizontal_overflow": bool(interaction_map.get("horizontal_overflow")),
                "clipped": len(interaction_map.get("clipped") or []),
                "file_inputs": file_inputs,
                "editable_inputs": editable,
                "selectors": selects,
            },
            "page_left_open": True,
        }
    finally:
        # Stop the Playwright client only. The remote Chrome and opened tab remain available to the user.
        await pw.stop()


def save_candidate(root: Path, analysis: dict[str, Any], observation: dict[str, Any] | None = None) -> dict[str, Any]:
    candidate_id = analysis["suggested_provider_id"]
    record = {
        "schema_version": SCHEMA_VERSION,
        "candidate_id": candidate_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "state": "OBSERVED" if observation else "ANALYZED",
        "analysis": analysis,
        "observation": observation,
    }
    path = candidate_path(root, candidate_id)
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"candidate": record, "record": str(path)}


def observe_url_sync(url: str, cdp_url: str) -> dict[str, Any]:
    return asyncio.run(observe_url(url, cdp_url))
