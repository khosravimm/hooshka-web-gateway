"""Discover a webchat (known or NEW): frontend + backend capabilities.

Read-only: never submits prompts, never clicks state-changing controls,
never reads secret values. Output: versioned draft profile under
docs/profiles/<provider-id>/ usable for onboarding new webchats.

Usage:
  python scripts/discover_provider.py --provider zai-web
  python scripts/discover_provider.py --provider newchat --cdp http://127.0.0.1:9330 --host chat.example.com
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

import yaml
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.discovery_engine import discover_page, save_report


def provider_map(config_path: Path) -> dict:
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    out = {}
    for p in data.get("providers", []) or []:
        pid = p.get("id")
        if not pid:
            continue
        rt, cfg = p.get("runtime", {}) or {}, p.get("config", {}) or {}
        out[pid] = {
            "cdp": (rt.get("cdp_url") or cfg.get("cdp_url") or "").strip(),
            "home": (rt.get("home_url") or cfg.get("base_url") or cfg.get("chatgpt_url") or ""),
        }
    return out


async def run(provider_id: str, cdp: str, host: str) -> Path:
    async with async_playwright() as pw:
        browser = await pw.chromium.connect_over_cdp(cdp, timeout=20000)
        ctx = browser.contexts[0] if browser.contexts else None
        if ctx is None:
            raise SystemExit(f"no browser context on {cdp}")
        pages = [x for x in ctx.pages if host in (x.url or "")] or ctx.pages[:1]
        page = pages[0]
        report = await discover_page(page, provider_id)
        path = save_report(report)
        summary = {
            "profile": str(path),
            "controls": [(c["kind"], c["selector"][:50], c["confidence"])
                         for c in report.frontend["controls"]],
            "endpoints": len(report.backend["candidate_endpoints"]),
            "transports": report.backend["stream_transports"],
            "drift": report.drift,
        }
        print(json.dumps(summary, ensure_ascii=False, indent=1))
        return path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", required=True)
    ap.add_argument("--cdp", default="")
    ap.add_argument("--host", default="")
    ap.add_argument("--config", default=str(ROOT / "config.yaml"))
    args = ap.parse_args()
    pmap = provider_map(Path(args.config))
    entry = pmap.get(args.provider, {})
    cdp = args.cdp or entry.get("cdp")
    host = args.host or entry.get("home", "").split("//")[-1].split("/")[0]
    if not cdp:
        raise SystemExit("no CDP url: pass --cdp (required for new webchats)")
    asyncio.run(run(args.provider, cdp, host or ""))


if __name__ == "__main__":
    main()
