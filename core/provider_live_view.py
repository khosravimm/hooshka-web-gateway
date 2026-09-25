from __future__ import annotations

import asyncio
import base64
import threading
import time
from typing import Any
from urllib.parse import urlparse

_OWNED_TARGETS: set[tuple[str, str]] = set()
_SCREENCASTS: dict[tuple[str, str], dict[str, Any]] = {}
_SCREENCAST_LOCK = threading.RLock()


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
        if target_id:
            if await _target_id(context, page) == target_id:
                return page
            continue
        if wanted and page.url.startswith(wanted) and fallback is None:
            fallback = page
    return fallback


async def _find_owned_page(context, cdp_url: str, url: str):
    wanted_origin = _origin(url)
    for owned_cdp, owned_target_id in list(_OWNED_TARGETS):
        if owned_cdp != cdp_url:
            continue
        existing = await _find_page(context, target_id=owned_target_id)
        if existing is None:
            _OWNED_TARGETS.discard((owned_cdp, owned_target_id))
            continue
        if wanted_origin and _origin(existing.url) == wanted_origin:
            return existing, owned_target_id
    return None, ""


async def open_target(cdp_url: str, url: str) -> dict[str, Any]:
    from playwright.async_api import async_playwright
    pw = await async_playwright().start()
    try:
        browser = await pw.chromium.connect_over_cdp(cdp_url)
        context = browser.contexts[0]
        existing, owned_target_id = await _find_owned_page(context, cdp_url, url)
        if existing is not None:
            return {
                "target_id": owned_target_id,
                "url": existing.url,
                "title": await existing.title(),
                "owned_by_wizard": True,
                "reused_existing": True,
            }
        # Wizard-owned Provider targets must be created in background. context.new_page()
        # activates the new tab in headed Chrome and steals focus from the Wizard.
        browser_cdp = await browser.new_browser_cdp_session()
        try:
            created = await browser_cdp.send("Target.createTarget", {"url": url, "background": True})
            target_id = str(created.get("targetId") or "")
        finally:
            await browser_cdp.detach()
        if not target_id:
            raise RuntimeError("background_target_creation_failed")
        page = None
        for _ in range(80):
            page = await _find_page(context, target_id=target_id)
            if page is not None:
                break
            await asyncio.sleep(0.05)
        if page is None:
            raise RuntimeError("background_target_not_attached")
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=30000)
        except Exception:
            pass
        _OWNED_TARGETS.add((cdp_url, target_id))
        return {
            "target_id": target_id,
            "url": page.url,
            "title": await page.title(),
            "owned_by_wizard": True,
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


async def close_owned_target(cdp_url: str, target_id: str) -> dict[str, Any]:
    key=(cdp_url, str(target_id or ""))
    if key not in _OWNED_TARGETS:
        return {"status":"blocked","reason":"target_not_owned_by_wizard"}
    from playwright.async_api import async_playwright
    pw=await async_playwright().start()
    try:
        browser=await pw.chromium.connect_over_cdp(cdp_url)
        context=browser.contexts[0]
        page=await _find_page(context, target_id=key[1])
        if page is None:
            _OWNED_TARGETS.discard(key)
            return {"status":"gone","target_id":key[1]}
        await page.close(run_before_unload=False)
        _OWNED_TARGETS.discard(key)
        return {"status":"closed","target_id":key[1]}
    finally:
        await pw.stop()

def close_owned_target_sync(cdp_url: str, target_id: str) -> dict[str, Any]:
    return asyncio.run(close_owned_target(cdp_url, target_id))


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


def _screencast_key(cdp_url: str, target_id: str) -> tuple[str, str]:
    return (str(cdp_url or ''), str(target_id or ''))

async def _run_screencast(cdp_url: str, target_id: str, url: str, state: dict[str, Any]) -> None:
    from playwright.async_api import async_playwright
    pw = await async_playwright().start()
    session = None
    try:
        browser = await pw.chromium.connect_over_cdp(cdp_url)
        context = browser.contexts[0]
        page = await _find_page(context, target_id=target_id, url=url)
        if page is None:
            with _SCREENCAST_LOCK: state.update(status='target_not_found', error='target_not_found')
            return
        actual_target = await _target_id(context, page)
        session = await context.new_cdp_session(page)
        with _SCREENCAST_LOCK:
            state.update(status='starting', target_id=actual_target, url=page.url, title=await page.title())
        def on_frame(params):
            try:
                frame = base64.b64decode(params.get('data') or '')
                meta = params.get('metadata') or {}
                with _SCREENCAST_LOCK:
                    state['frame'] = frame; state['metadata'] = meta; state['sequence'] = int(state.get('sequence') or 0) + 1
                    state['last_frame_at'] = time.time(); state['status'] = 'streaming'
                sid = params.get('sessionId')
                if sid is not None: asyncio.create_task(session.send('Page.screencastFrameAck', {'sessionId': sid}))
            except Exception as exc:
                with _SCREENCAST_LOCK: state['last_frame_error'] = type(exc).__name__
        session.on('Page.screencastFrame', on_frame)
        await session.send('Page.startScreencast', {'format':'jpeg','quality':72,'maxWidth':1440,'maxHeight':900,'everyNthFrame':1})
        while not state['stop_event'].is_set():
            await asyncio.sleep(0.1)
    except Exception as exc:
        with _SCREENCAST_LOCK: state.update(status='error', error=type(exc).__name__)
    finally:
        if session is not None:
            try: await session.send('Page.stopScreencast')
            except Exception: pass
            try: await session.detach()
            except Exception: pass
        try: await pw.stop()
        except Exception: pass
        with _SCREENCAST_LOCK:
            if state.get('status') not in {'error','target_not_found'}: state['status']='stopped'

def start_screencast_sync(cdp_url: str, target_id: str, url: str = '') -> dict[str, Any]:
    key=_screencast_key(cdp_url,target_id)
    with _SCREENCAST_LOCK:
        current=_SCREENCASTS.get(key)
        if current and current.get('thread') and current['thread'].is_alive():
            return {'status':current.get('status'),'target_id':current.get('target_id') or target_id,'sequence':current.get('sequence',0),'reused':True}
        state={'status':'starting','frame':b'','metadata':{},'sequence':0,'stop_event':threading.Event(),'target_id':target_id,'url':url,'error':None}
        thread=threading.Thread(target=lambda: asyncio.run(_run_screencast(cdp_url,target_id,url,state)),daemon=True,name=f'hwg-screencast-{target_id[:8]}')
        state['thread']=thread; _SCREENCASTS[key]=state; thread.start()
    return {'status':'starting','target_id':target_id,'sequence':0,'reused':False}

def get_screencast_frame(cdp_url: str, target_id: str) -> dict[str, Any]:
    key=_screencast_key(cdp_url,target_id)
    with _SCREENCAST_LOCK:
        state=_SCREENCASTS.get(key)
        if not state: return {'status':'not_started'}
        frame=bytes(state.get('frame') or b'')
        return {'status':state.get('status'),'target_id':state.get('target_id') or target_id,'sequence':state.get('sequence',0),'frame':frame,'metadata':dict(state.get('metadata') or {}),'error':state.get('error')}

def stop_screencast_sync(cdp_url: str, target_id: str) -> dict[str, Any]:
    key=_screencast_key(cdp_url,target_id)
    with _SCREENCAST_LOCK:
        state=_SCREENCASTS.get(key)
        if not state: return {'status':'not_started','target_id':target_id}
        state['stop_event'].set(); thread=state.get('thread')
    if thread and thread.is_alive(): thread.join(timeout=3.0)
    with _SCREENCAST_LOCK:
        final=_SCREENCASTS.pop(key,None) or state
    return {'status':'stopped','target_id':final.get('target_id') or target_id,'sequence':final.get('sequence',0)}
