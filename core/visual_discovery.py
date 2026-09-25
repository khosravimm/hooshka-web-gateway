from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VISUAL_VERSION = "1.0.0"
UPLOAD_BUSY_RE = re.compile(r"\b(uploading|processing|attaching|preparing)\b|در حال آپلود|در حال بارگذاری|آپلود فایل", re.I)


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
          tag:e.tagName, id:e.id||'', label:e.getAttribute('aria-label')||'', testid:e.getAttribute('data-testid')||'',
          text:(e.innerText||e.textContent||'').trim().slice(0,160), disabled:!!e.disabled,
          aria_disabled:e.getAttribute('aria-disabled'), cls:String(e.className||'').slice(0,180)
        }));
      const composers=[...document.querySelectorAll('textarea,[contenteditable="true"]')].filter(visible).map(e=>{const r=e.getBoundingClientRect(); return {tag:e.tagName,id:e.id||'',label:e.getAttribute('aria-label')||'',placeholder:e.getAttribute('placeholder')||'',disabled:!!e.disabled||e.getAttribute('aria-disabled')==='true',rect:{x:r.x,y:r.y,w:r.width,h:r.height}};}).filter(x=>x.rect.w>=160&&x.rect.h>=18).slice(0,12);
      const media=[...document.querySelectorAll('img,[role="img"]')].filter(visible).map(e=>{const r=e.getBoundingClientRect(); return {tag:e.tagName,alt:e.getAttribute('alt')||'',label:e.getAttribute('aria-label')||'',title:e.getAttribute('title')||'',src:(e.getAttribute('src')||'').slice(0,220),rect:{x:r.x,y:r.y,w:r.width,h:r.height}};}).filter(x=>x.rect.w>=24&&x.rect.h>=24).slice(0,40);
      const inViewport=e=>{const r=e.getBoundingClientRect();return r.bottom>0&&r.right>0&&r.top<innerHeight&&r.left<innerWidth};
      const loading=[...document.querySelectorAll('[aria-busy="true"],.loading,.spinner,[class*="loading"],[class*="spinner"]')].filter(e=>visible(e)&&inViewport(e)).slice(0,20).map(e=>({tag:e.tagName,text:(e.innerText||e.textContent||'').trim().slice(0,160),cls:String(e.className||'').slice(0,180)}));
      return {url:location.href,title:document.title,viewport:{width:innerWidth,height:innerHeight},
        body:(document.body?.innerText||'').slice(-4000),controls:nodes,composers,media,loading};
    }""")
    body = str(state.get("body") or "")
    controls = list(state.get("controls") or [])
    preferred = [c for c in controls if (
        str(c.get("testid") or "").lower() in {"send-button", "send-message-button"}
        or str(c.get("id") or "").lower() in {"send-message-button"}
        or str(c.get("label") or "").strip().lower() in {"send", "send message"}
    )]
    send = preferred or [c for c in controls if re.search(r"\bsend\b", " ".join(map(str,[c.get('label'),c.get('testid'),c.get('text')])), re.I)]
    control_text = "\n".join(" ".join(map(str,[c.get("label"),c.get("testid"),c.get("text")])) for c in controls)
    media = list(state.get("media") or [])
    media_text = "\n".join(" ".join(map(str,[m.get("alt"),m.get("label"),m.get("title"),m.get("src")])) for m in media)
    file_key = str(file_name or "").lower()
    stem_key = Path(file_key).stem.lower() if file_key else ""
    attached = bool(file_key and (
        file_key in body.lower()
        or file_key in control_text.lower()
        or (stem_key and stem_key in body.lower())
        or (stem_key and stem_key in control_text.lower())
        or file_key in media_text.lower()
        or (stem_key and stem_key in media_text.lower())
    ))
    send_enabled = any(not bool(c.get("disabled")) and str(c.get("aria_disabled") or "").lower() != "true" for c in send)
    composers = list(state.get("composers") or [])
    composer_enabled = any(not bool(c.get("disabled")) for c in composers)
    dialogs_raw = await visible_blocking_dialogs(page)
    dialogs = dialogs_raw if isinstance(dialogs_raw, list) else []
    overlays_raw = await visible_blocking_overlays(page)
    overlays = overlays_raw if isinstance(overlays_raw, list) else []
    popovers_raw = await visible_transient_popovers(page)
    popovers = popovers_raw if isinstance(popovers_raw, list) else []
    upload_dialog = any(re.search(r"upload|آپلود", str(d.get("text") or ""), re.I) for d in dialogs if isinstance(d, dict))
    return {
        "schema_version": VISUAL_VERSION,
        "url": state.get("url"), "title": state.get("title"), "viewport": state.get("viewport"),
        "body_tail": body, "visible_control_text": control_text[-6000:], "attachment_visible": attached,
        "upload_busy": bool(UPLOAD_BUSY_RE.search(body)) or upload_dialog,
        "blocking_dialogs": dialogs[:8], "blocking_overlays": overlays[:8], "transient_popovers": popovers[:8],
        "send_present": bool(send), "send_enabled": send_enabled,
        "send_controls": send[:8], "composer_present": bool(composers),
        "composer_enabled": composer_enabled, "composer_controls": composers[:8],
        "media_previews": media[:20], "loading_indicators": list(state.get("loading") or [])[:20],
        "loading_visible": bool(state.get("loading")),
    }


USER_VIEW_PATTERNS = [
    ("region_blocked", re.compile(r"not available in your region|unavailable in your region|region (?:is )?not supported", re.I)),
    ("login_required", re.compile(r"(?:\b(?:log in|sign in|continue with google|continue with apple)\b|ورود|ثبت[‌ ]?نام|ادامه با گوگل)", re.I)),
    ("challenge", re.compile(r"captcha|verify you are human|security check|challenge|تأیید.*انسان|کپچا|احراز.*انسان", re.I)),
    ("quota_limited", re.compile(r"quota|usage limit|limit reached|processing limit|محدودیت پردازش|سهمیه|پس از آزادسازی سهمیه", re.I)),
    ("rate_limited", re.compile(r"too many requests|rate limit|try again later|تعداد درخواست|بعداً دوباره", re.I)),
    ("service_error", re.compile(r"something went wrong|service unavailable|internal server error|temporarily unavailable", re.I)),
]

def classify_user_view_state(state: dict[str, Any]) -> dict[str, Any]:
    body_text = str(state.get("body_tail") or "")
    control_text = str(state.get("visible_control_text") or "")
    text = "\n".join(x for x in (body_text, control_text) if x)
    strong_login_surface = re.search(
        r"continue with google|continue with apple|sign in with email|log in with email|don\'t have an account",
        text, re.I,
    )
    login_control = bool(re.search(r"(?:^|\n|\s)(?:log ?in|sign ?in)(?:$|\n|\s)", control_text, re.I))
    signup_control = bool(re.search(r"(?:^|\n|\s)sign ?up(?:$|\n|\s)", control_text, re.I))
    if strong_login_surface:
        return {"state":"login_required","evidence":strong_login_surface.group(0)[:160]}
    if (login_control or signup_control) and state.get("composer_present"):
        return {"state":"auth_ambiguous","evidence":"visible login/signup control with interactive composer"}
    if signup_control:
        return {"state":"login_required","evidence":"Sign up"}
    for name, pattern in USER_VIEW_PATTERNS:
        match = pattern.search(text)
        if match:
            result={"state":name,"evidence":match.group(0)[:160]}
            if name=="quota_limited":
                lower=text.lower()
                media_hint=bool(re.search(r"file|upload|attachment|processing file|فایل|پردازش\s+فایل", lower, re.I))
                result["scope"]="media" if media_hint else "general"
            return result
    overlays=list(state.get("blocking_overlays") or [])
    dialogs=list(state.get("blocking_dialogs") or [])
    if overlays or dialogs:
        item=(overlays or dialogs)[0] if (overlays or dialogs) else {}
        return {"state":"blocking_overlay","evidence":str(item.get("text") or item.get("kind") or "visible blocking overlay")[:160],"overlay_count":len(overlays),"dialog_count":len(dialogs)}
    if state.get("loading_visible"):
        return {"state":"loading","evidence":"visible loading indicator"}
    if state.get("upload_busy"):
        return {"state":"upload_busy","evidence":"visible upload progress"}
    if state.get("send_present") and state.get("send_enabled"):
        return {"state":"ready","evidence":"visible enabled send control"}
    if state.get("composer_present") and state.get("composer_enabled"):
        return {"state":"ready","evidence":"visible enabled chat composer"}
    if state.get("send_present") or state.get("composer_present"):
        return {"state":"interactive_not_ready","evidence":"visible chat composer/send control is disabled"}
    return {"state":"unknown","evidence":"no known visible state matched"}


VISUAL_ACTION_BLOCKING_STATES = {
    "media_qualification": {"region_blocked","login_required","auth_ambiguous","challenge","quota_limited","rate_limited","service_error","blocking_overlay"},
    "send": {"region_blocked","login_required","auth_ambiguous","challenge","quota_limited","rate_limited","service_error","blocking_overlay"},
    "probe": {"region_blocked","login_required","auth_ambiguous","challenge","quota_limited","rate_limited","service_error","blocking_overlay"},
    "provider_interaction": {"region_blocked","login_required","auth_ambiguous","challenge","quota_limited","rate_limited","service_error","blocking_overlay"},
    "certification_probe": {"region_blocked","login_required","auth_ambiguous","challenge","quota_limited","rate_limited","service_error","blocking_overlay"},
}

async def visual_action_gate(page, action: str) -> dict[str, Any]:
    state = await visible_page_state(page)
    classification = classify_user_view_state(state)
    name = str(classification.get("state") or "unknown")
    media_scoped_exception = (
        name=="quota_limited"
        and str(classification.get("scope") or "general")=="media"
        and action!="media_qualification"
    )
    allowed = name=="ready" or media_scoped_exception
    known_blocker = name in VISUAL_ACTION_BLOCKING_STATES.get(action, set())
    reason = "visual_preflight_clear" if allowed else ("blocked_by_provider_state" if known_blocker else "blocked_by_visual_readiness")
    return {
        "action": action,
        "allowed": allowed,
        "classification": classification,
        "state": state,
        "reason": reason,
    }

async def media_qualification_preflight(page) -> dict[str, Any]:
    return await visual_action_gate(page, "media_qualification")


def user_view_access_state(classification: dict[str, Any]) -> str:
    state=str((classification or {}).get("state") or "unknown")
    if state in {"region_blocked","challenge","quota_limited","rate_limited","service_error","blocking_overlay"}:
        return "BLOCKED"
    if state == "login_required":
        return "LOGIN_REQUIRED"
    if state == "auth_ambiguous":
        return "UNKNOWN"
    if state in {"ready","interactive_not_ready","upload_busy","loading"}:
        return "AUTHENTICATED"
    return "UNKNOWN"


async def visible_blocking_overlays(page) -> list[dict[str, Any]]:
    return await page.evaluate(r"""() => {
      const vw=innerWidth, vh=innerHeight, area=Math.max(1,vw*vh);
      const visible=(e,s,r)=>r.width>0&&r.height>0&&s.display!=='none'&&s.visibility!=='hidden'&&Number(s.opacity||1)>0.05&&s.pointerEvents!=='none';
      const center=document.elementFromPoint(vw/2,vh/2);
      const rows=[];
      for(const e of document.querySelectorAll('body *')){
        const s=getComputedStyle(e), r=e.getBoundingClientRect();
        if(!visible(e,s,r) || s.position!=='fixed') continue;
        const w=Math.max(0,Math.min(r.right,vw)-Math.max(r.left,0));
        const h=Math.max(0,Math.min(r.bottom,vh)-Math.max(r.top,0));
        const coverage=(w*h)/area;
        const zi=parseInt(s.zIndex||'0',10);
        const semantic=/overlay|backdrop|modal|dialog|popup|mask|interstitial/i.test(String(e.className||'')+' '+String(e.id||''));
        const centerBlocks=!!center && (e===center || e.contains(center));
        const backdrop=(s.backdropFilter&&s.backdropFilter!=='none') || (s.webkitBackdropFilter&&s.webkitBackdropFilter!=='none');
        if(!centerBlocks) continue;
        if(!(coverage>=0.45 || semantic || backdrop)) continue;
        if(!(zi>=20 || semantic || backdrop || coverage>=0.80)) continue;
        rows.push({kind:'viewport_blocking_overlay',tag:e.tagName,id:e.id||'',cls:String(e.className||'').slice(0,220),coverage:Number(coverage.toFixed(3)),z_index:Number.isFinite(zi)?zi:0,backdrop:!!backdrop,text:(e.innerText||e.textContent||'').trim().slice(0,1000)});
      }
      return rows.sort((a,b)=>(b.z_index-a.z_index)||(b.coverage-a.coverage)).slice(0,8);
    }""")


async def visible_transient_popovers(page) -> list[dict[str, Any]]:
    return await page.evaluate(r"""() => {
      const vw=innerWidth, vh=innerHeight, area=Math.max(1,vw*vh);
      const composers=[...document.querySelectorAll('textarea,[contenteditable="true"]')].filter(e=>{const r=e.getBoundingClientRect(),s=getComputedStyle(e);return r.width>0&&r.height>0&&s.display!=='none'&&s.visibility!=='hidden'});
      const cr=composers.length?composers[0].getBoundingClientRect():null;
      const rows=[];
      for(const e of document.querySelectorAll('body *')){
        const s=getComputedStyle(e),r=e.getBoundingClientRect(),zi=parseInt(s.zIndex||'0',10);
        if(r.width<120||r.height<40||s.display==='none'||s.visibility==='hidden'||Number(s.opacity||1)<0.1||s.pointerEvents==='none') continue;
        if(!['fixed','absolute'].includes(s.position) || !Number.isFinite(zi) || zi<20) continue;
        const w=Math.max(0,Math.min(r.right,vw)-Math.max(r.left,0)), h=Math.max(0,Math.min(r.bottom,vh)-Math.max(r.top,0));
        const coverage=(w*h)/area; if(coverage<=0.005||coverage>=0.45) continue;
        const text=(e.innerText||e.textContent||'').trim(); if(!text) continue;
        let near=false, overlap=0;
        if(cr){const ix=Math.max(0,Math.min(r.right,cr.right)-Math.max(r.left,cr.left)); const iy=Math.max(0,Math.min(r.bottom,cr.bottom)-Math.max(r.top,cr.top)); overlap=ix*iy; const gap=Math.max(0,Math.max(cr.top-r.bottom,r.top-cr.bottom,cr.left-r.right,r.left-cr.right)); near=overlap>0||gap<160;}
        rows.push({kind:'transient_popover',tag:e.tagName,id:e.id||'',cls:String(e.className||'').slice(0,220),coverage:Number(coverage.toFixed(3)),z_index:zi,near_composer:near,overlap_with_composer:Number(overlap.toFixed(1)),text:text.slice(0,1000)});
      }
      return rows.sort((a,b)=>(Number(b.near_composer)-Number(a.near_composer))||(b.z_index-a.z_index)).slice(0,8);
    }""")


async def visible_blocking_dialogs(page) -> list[dict[str, Any]]:
    return await page.evaluate(r"""() => {
      const vis=e=>{const r=e.getBoundingClientRect(),s=getComputedStyle(e);return r.width>0&&r.height>0&&s.display!=='none'&&s.visibility!=='hidden'};
      return [...document.querySelectorAll('[role=dialog],.q-dialog')].filter(vis).map((d,i)=>({
        index:i,text:(d.innerText||d.textContent||'').trim().slice(0,2000),
        buttons:[...d.querySelectorAll('button,[role=button]')].filter(vis).map(b=>({text:(b.innerText||b.textContent||'').trim().slice(0,200),label:b.getAttribute('aria-label')||'',disabled:!!b.disabled||b.getAttribute('aria-disabled')==='true'}))
      }));
    }""")

async def resolve_safe_upload_dialog(page) -> dict[str, Any]:
    dialogs_raw=await visible_blocking_dialogs(page)
    dialogs=dialogs_raw if isinstance(dialogs_raw,list) else []
    for d in dialogs:
        if not isinstance(d,dict):
            continue
        text=str(d.get('text') or '')
        buttons=list(d.get('buttons') or [])
        if not re.search(r'upload|آپلود',text,re.I) or len(buttons)!=1:
            continue
        btn=buttons[0]; label=' '.join([str(btn.get('text') or ''),str(btn.get('label') or '')]).strip()
        if btn.get('disabled') or not re.fullmatch(r'(?i)(ok|okay|accept|close|قبول|باشه|تایید|تأیید)',label):
            continue
        idx=int(d.get('index') or 0)
        loc=page.locator('[role=dialog],.q-dialog').nth(idx).locator('button,[role=button]').first
        await loc.click(timeout=5000)
        await page.wait_for_timeout(250)
        return {'resolved':True,'kind':'upload_dialog','message':text[:300],'action':label}
    return {'resolved':False,'dialogs':dialogs}


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
        try:
            session = await page.context.new_cdp_session(page)
            raw = await session.send("Page.captureScreenshot", {"format":"png","fromSurface":True})
            import base64
            path.write_bytes(base64.b64decode(raw.get("data") or ""))
            if path.exists() and path.stat().st_size:
                screenshot = str(path)
                screenshot_error = None
        except Exception as fallback_exc:
            screenshot_error = f"{screenshot_error}+{type(fallback_exc).__name__}"
    state = await visible_page_state(page, file_name=file_name)
    state.update({"stage": stage, "screenshot": screenshot, "screenshot_error": screenshot_error, "captured_at": stamp})
    return state


async def wait_for_upload_settled(page, provider_id: str, file_name: str, *, timeout_seconds: float = 60.0, settle_seconds: float = 1.5) -> dict[str, Any]:
    """Observe rendered UI until attachment readiness is stable, not merely momentarily visible."""
    import asyncio
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_seconds
    trace = [await capture_user_view(page, provider_id, "upload-selected", file_name=file_name)]
    last_signature = None
    ready_since = None
    while loop.time() < deadline:
        state = await visible_page_state(page, file_name=file_name)
        classification = classify_user_view_state(state)
        if classification.get("state") == "quota_limited":
            trace.append(await capture_user_view(page, provider_id, "upload-quota-limited", file_name=file_name))
            return {"ready":False,"file_name":file_name,"final":state,"trace":trace,"classification":classification,"reason":"provider_quota_limited"}
        signature = (state["attachment_visible"], state["upload_busy"], state["send_present"], state["send_enabled"])
        if signature != last_signature:
            label = f"upload-state-{int(state['attachment_visible'])}{int(state['upload_busy'])}{int(state['send_enabled'])}"
            trace.append(await capture_user_view(page, provider_id, label, file_name=file_name))
            last_signature = signature
        candidate_ready = state["attachment_visible"] and not state["upload_busy"]
        if candidate_ready:
            if ready_since is None:
                ready_since = loop.time()
            elif loop.time() - ready_since >= settle_seconds:
                return {"ready": True, "file_name": file_name, "final": state, "trace": trace, "settle_seconds": settle_seconds}
        else:
            ready_since = None
        await page.wait_for_timeout(250)
    final = await visible_page_state(page, file_name=file_name)
    classification = classify_user_view_state(final)
    trace.append(await capture_user_view(page, provider_id, "upload-timeout", file_name=file_name))
    reason = "provider_quota_limited" if classification.get("state")=="quota_limited" else "upload_not_settled_before_timeout"
    return {"ready": False, "file_name": file_name, "final": final, "trace": trace,
            "classification": classification, "reason": reason}


async def visible_interaction_map(page) -> dict[str, Any]:
    """Capture the rendered viewport as a user-facing interaction map."""
    return await page.evaluate(r"""() => {
      const vis = e => { const r=e.getBoundingClientRect(), s=getComputedStyle(e); return r.width>0&&r.height>0&&r.bottom>=0&&r.top<=innerHeight&&r.right>=0&&r.left<=innerWidth&&s.display!=='none'&&s.visibility!=='hidden'; };
      const rect = e => { const r=e.getBoundingClientRect(); return {x:Math.round(r.x),y:Math.round(r.y),w:Math.round(r.width),h:Math.round(r.height)}; };
      const nodes=[...document.querySelectorAll('button,a,input,select,textarea,[role=button],[role=tab],[role=checkbox]')].filter(vis);
      const controls=nodes.slice(0,300).map((e,i)=>({i,tag:e.tagName.toLowerCase(),id:e.id||'',type:e.type||'',text:(e.innerText||e.value||e.textContent||'').trim().slice(0,180),label:e.getAttribute('aria-label')||e.getAttribute('title')||'',disabled:!!e.disabled||e.getAttribute('aria-disabled')==='true',checked:!!e.checked,selected:e.getAttribute('aria-selected'),rect:rect(e)}));
      const headings=[...document.querySelectorAll('h1,h2,h3,h4,[role=heading]')].filter(vis).slice(0,80).map(e=>({text:(e.innerText||e.textContent||'').trim().slice(0,240),rect:rect(e)}));
      const clipped=[...document.querySelectorAll('main *')].filter(vis).filter(e=>e.scrollWidth>e.clientWidth+8).slice(0,80).map(e=>({tag:e.tagName.toLowerCase(),id:e.id||'',text:(e.innerText||e.textContent||'').trim().slice(0,120),clientWidth:e.clientWidth,scrollWidth:e.scrollWidth,rect:rect(e)}));
      return {viewport:{width:innerWidth,height:innerHeight},scroll:{width:document.documentElement.scrollWidth,height:document.documentElement.scrollHeight,x:scrollX,y:scrollY},horizontal_overflow:document.documentElement.scrollWidth>innerWidth+4,controls,headings,clipped,visible_text:(document.body?.innerText||'').slice(0,12000)};
    }""")
