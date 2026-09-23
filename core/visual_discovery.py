from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VISUAL_VERSION = "1.0.0"
UPLOAD_BUSY_RE = re.compile(r"\b(uploading|processing|attaching|preparing)\b", re.I)


def _slug(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "-", str(value or "unknown")).strip("-") or "unknown"


async def visible_page_state(page, file_name: str | None = None) -> dict[str, Any]:
    state = await page.evaluate("""() => {
      const visible = (e) => {
        const r = e.getBoundingClientRect(); const s = getComputedStyle(e);
        return r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden';
      };
      const nodes = [...document.querySelectorAll('button,[role="button"],[aria-label],[data-testid]')]
        .filter(visible).slice(0, 180).map(e => ({
          tag:e.tagName, label:e.getAttribute('aria-label')||'', testid:e.getAttribute('data-testid')||'',
          text:(e.innerText||e.textContent||'').trim().slice(0,160), disabled:!!e.disabled,
          aria_disabled:e.getAttribute('aria-disabled'), cls:String(e.className||'').slice(0,180)
        }));
      return {url:location.href,title:document.title,viewport:{width:innerWidth,height:innerHeight},
        body:(document.body?.innerText||'').slice(-4000),controls:nodes};
    }""")
    body = str(state.get("body") or "")
    controls = list(state.get("controls") or [])
    send = [c for c in controls if re.search(r"\bsend\b", " ".join(map(str,[c.get('label'),c.get('testid'),c.get('text')])), re.I)]
    control_text = "\n".join(" ".join(map(str,[c.get("label"),c.get("testid"),c.get("text")])) for c in controls)
    file_key = str(file_name or "").lower()
    stem_key = Path(file_key).stem.lower() if file_key else ""
    attached = bool(file_key and (
        file_key in body.lower()
        or file_key in control_text.lower()
        or (stem_key and stem_key in body.lower())
        or (stem_key and stem_key in control_text.lower())
    ))
    send_enabled = any(not bool(c.get("disabled")) and str(c.get("aria_disabled") or "").lower() != "true" for c in send)
    return {
        "schema_version": VISUAL_VERSION,
        "url": state.get("url"), "title": state.get("title"), "viewport": state.get("viewport"),
        "body_tail": body, "attachment_visible": attached,
        "upload_busy": bool(UPLOAD_BUSY_RE.search(body)),
        "send_present": bool(send), "send_enabled": send_enabled,
        "send_controls": send[:8],
    }


async def capture_user_view(page, provider_id: str, stage: str, *, root: Path | None = None,
                            file_name: str | None = None) -> dict[str, Any]:
    root = root or (Path(__file__).resolve().parents[1] / ".runtime-dev" / "discovery-visual")
    folder = root / _slug(provider_id)
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = folder / f"{stamp}-{_slug(stage)}.png"
    screenshot = None
    screenshot_error = None
    try:
        await page.screenshot(path=str(path), full_page=False, timeout=8000)
        screenshot = str(path)
    except Exception as exc:
        screenshot_error = type(exc).__name__
    state = await visible_page_state(page, file_name=file_name)
    state.update({"stage": stage, "screenshot": screenshot, "screenshot_error": screenshot_error, "captured_at": stamp})
    return state


async def wait_for_upload_settled(page, provider_id: str, file_name: str, *, timeout_seconds: float = 60.0) -> dict[str, Any]:
    """Observe what a user sees and wait until an attachment is visible and upload busy state clears."""
    import asyncio
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_seconds
    trace = [await capture_user_view(page, provider_id, "upload-selected", file_name=file_name)]
    last_signature = None
    while loop.time() < deadline:
        state = await visible_page_state(page, file_name=file_name)
        signature = (state["attachment_visible"], state["upload_busy"], state["send_present"], state["send_enabled"])
        if signature != last_signature:
            label = f"upload-state-{int(state['attachment_visible'])}{int(state['upload_busy'])}{int(state['send_enabled'])}"
            trace.append(await capture_user_view(page, provider_id, label, file_name=file_name))
            last_signature = signature
        if state["attachment_visible"] and not state["upload_busy"]:
            return {"ready": True, "file_name": file_name, "final": state, "trace": trace}
        await page.wait_for_timeout(250)
    final = await visible_page_state(page, file_name=file_name)
    trace.append(await capture_user_view(page, provider_id, "upload-timeout", file_name=file_name))
    return {"ready": False, "file_name": file_name, "final": final, "trace": trace,
            "reason": "upload_not_settled_before_timeout"}
