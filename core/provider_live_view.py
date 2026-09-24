from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import urlparse


def _origin(url: str) -> str:
    p = urlparse(url or "")
    return f"{p.scheme}://{p.netloc}" if p.scheme and p.netloc else ""


async def _target_id(context, page) -> str:
    session = await context.new_cdp_session(page)
    try:
        info = await session.send("Target.getTargetInfo")
        return str((info.get("targetInfo") or {}).get("targetId") or "")
    finally:
        await session.detach()


async def _find_page(context, target_id: str = "", url: str = ""):
    wanted = _origin(url)
    fallback = None
    for page in reversed(context.pages):
        if wanted and page.url.startswith(wanted) and fallback is None:
            fallback = page
        if target_id and await _target_id(context, page) == target_id:
            return page
    return fallback


async def open_target(cdp_url: str, url: str) -> dict[str, Any]:
    from playwright.async_api import async_playwright
    pw = await async_playwright().start()
    try:
        browser = await pw.chromium.connect_over_cdp(cdp_url)
        context = browser.contexts[0]
        page = await context.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        except Exception:
            pass
        return {
            "target_id": await _target_id(context, page),
            "url": page.url,
            "title": await page.title(),
        }
    finally:
        await pw.stop()


def open_target_sync(cdp_url: str, url: str) -> dict[str, Any]:
    return asyncio.run(open_target(cdp_url, url))


async def capture_live_view(cdp_url: str, target_id: str = "", url: str = "") -> dict[str, Any]:
    from playwright.async_api import async_playwright
    pw = await async_playwright().start()
    try:
        browser = await pw.chromium.connect_over_cdp(cdp_url)
        context = browser.contexts[0]
        page = await _find_page(context, target_id=target_id, url=url)
        if page is None:
            return {"status": "target_not_found"}
        viewport = await page.evaluate("() => ({width: innerWidth, height: innerHeight, dpr: devicePixelRatio})")
        image = await page.screenshot(type="jpeg", quality=72)
        return {
            "status": "ok",
            "target_id": await _target_id(context, page),
            "url": page.url,
            "title": await page.title(),
            "viewport": viewport,
            "image": image,
        }
    finally:
        await pw.stop()


def capture_live_view_sync(cdp_url: str, target_id: str = "", url: str = "") -> dict[str, Any]:
    return asyncio.run(capture_live_view(cdp_url, target_id=target_id, url=url))


async def dispatch_live_input(cdp_url: str, action: dict[str, Any]) -> dict[str, Any]:
    from playwright.async_api import async_playwright
    pw = await async_playwright().start()
    try:
        browser = await pw.chromium.connect_over_cdp(cdp_url)
        context = browser.contexts[0]
        page = await _find_page(context, target_id=str(action.get("target_id") or ""), url=str(action.get("url") or ""))
        if page is None:
            return {"status": "target_not_found"}
        kind = str(action.get("kind") or "")
        if kind == "click":
            await page.mouse.click(float(action.get("x") or 0), float(action.get("y") or 0))
        elif kind == "scroll":
            await page.mouse.wheel(float(action.get("dx") or 0), float(action.get("dy") or 0))
        elif kind == "text":
            sensitive = await page.evaluate("""() => {
              const e=document.activeElement;
              return !!(e && e.tagName==='INPUT' && String(e.type||'').toLowerCase()==='password');
            }""")
            if sensitive:
                return {"status":"blocked","reason":"sensitive_input_requires_native_tab"}
            await page.keyboard.insert_text(str(action.get("text") or ""))
        elif kind == "key":
            await page.keyboard.press(str(action.get("key") or ""))
        elif kind == "focus":
            await page.bring_to_front()
        else:
            return {"status":"blocked","reason":"unsupported_action"}
        return {
            "status":"ok",
            "target_id": await _target_id(context, page),
            "url": page.url,
        }
    finally:
        await pw.stop()


def dispatch_live_input_sync(cdp_url: str, action: dict[str, Any]) -> dict[str, Any]:
    return asyncio.run(dispatch_live_input(cdp_url, action))
