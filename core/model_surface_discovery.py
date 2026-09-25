from __future__ import annotations

import re
from typing import Any

MODEL_TOKEN_RE = re.compile(
    r"\b(?:gpt|claude|gemini|deepseek|qwen|grok|llama|mistral|glm|kimi|minimax|perplexity|yi)\b",
    re.I,
)
VENDOR_RE = re.compile(
    r"^(?:gpt|claude|gemini|deepseek|qwen|grok|llama|mistral|glm|other)$",
    re.I,
)


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _is_model_row(text: str) -> bool:
    t = _clean(text)
    return bool(t and len(t) <= 120 and (MODEL_TOKEN_RE.search(t) or re.search(r"\b\d+(?:\.\d+)?x$", t, re.I)))


async def _storage_model_hints(page) -> dict[str, str]:
    return await page.evaluate(r"""() => {
      const out={};
      for(let i=0;i<localStorage.length;i++){
        const k=localStorage.key(i)||'';
        if(/model/i.test(k)) out[k]=String(localStorage.getItem(k)||'').slice(0,240);
      }
      return out;
    }""")


async def _clickable_rows(container) -> list[dict[str, Any]]:
    return await container.locator("*").evaluate_all(r"""els => els.map(e => {
      const r=e.getBoundingClientRect(), s=getComputedStyle(e);
      const text=(e.innerText||'').trim().replace(/\s+/g,' ');
      return {
        text:text.slice(0,180), tag:e.tagName, role:e.getAttribute('role')||'',
        disabled:e.disabled===true||e.getAttribute('aria-disabled')==='true',
        selected:e.getAttribute('aria-selected')||'', state:e.getAttribute('data-state')||'',
        cursor:s.cursor, child_count:e.children.length,
        cls:String(e.className||'').slice(0,220),
        rect:{x:Math.round(r.x),y:Math.round(r.y),w:Math.round(r.width),h:Math.round(r.height)}
      };
    }).filter(x => x.text && x.text.length < 180 && (x.cursor === 'pointer' || ['option','menuitem','radio','tab'].includes(x.role)))""")


def _dedupe(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out=[]; seen=set()
    for row in rows:
        text=_clean(row.get("text") or "")
        if not text or text in seen:
            continue
        seen.add(text)
        item=dict(row); item["text"]=text; out.append(item)
    return out


def _normalize_model(row: dict[str, Any], category: str | None, upgrade_notice: bool) -> dict[str, Any]:
    text=_clean(row.get("text") or "")
    premium=bool(re.search(r"\bpremium\b", text, re.I))
    multiplier=None
    m=re.search(r"(\d+(?:\.\d+)?)x$", text, re.I)
    if m: multiplier=float(m.group(1))
    return {
        "display_text":text, "category":category,
        "visible":True, "disabled":bool(row.get("disabled")),
        "premium":premium, "requires_upgrade":bool(premium and upgrade_notice),
        "usage_multiplier":multiplier, "evidence_level":"E1",
    }


async def discover_model_surface(page, frontend_controls: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    controls=list(frontend_controls or [])
    hints=await _storage_model_hints(page)
    selection_mode=next((v for k,v in hints.items() if re.search(r"model",k,re.I)),None)
    result={
        "status":"not_observed","evidence_level":"E1","storage_hints":hints,
        "selection_mode":selection_mode,"current_label":None,"selector":None,
        "categories":[],"models":[],"opened":False,
    }
    candidate=None
    for control in controls:
        if str(control.get("kind") or "")!="model_selector":
            continue
        sel=str(control.get("selector") or "").strip()
        if not sel: continue
        try:
            loc=page.locator(sel).first
            if await loc.count() and await loc.is_visible():
                candidate=loc; result["selector"]=sel; break
        except Exception:
            continue
    if candidate is None:
        pop=page.locator("button[aria-haspopup='dialog'],button[aria-haspopup='listbox'],[role='combobox']")
        count=await pop.count()
        for i in range(count):
            loc=pop.nth(i)
            try:
                text=_clean(await loc.inner_text())
                if MODEL_TOKEN_RE.search(text) or (str(selection_mode or "").lower()=="auto" and text.lower()=="auto"):
                    candidate=loc; break
            except Exception:
                continue
    if candidate is None:
        return result
    result["current_label"]=_clean(await candidate.inner_text())
    from core.visual_discovery import visual_action_gate
    gate=await visual_action_gate(page,"provider_interaction")
    result["visual_preflight"]=gate.get("classification") or {}
    if not gate.get("allowed"):
        result["status"]="blocked"; result["reason"]="visual_preflight"; return result
    try:
        await candidate.click(no_wait_after=True,timeout=5000)
        await page.wait_for_timeout(500)
        popups=page.locator("[role='dialog']:visible,[role='listbox']:visible,[role='menu']:visible")
        if await popups.count()==0:
            result["status"]="selector_open_failed"; result["reason"]="no_visible_popup"; return result
        popup=popups.last; result["opened"]=True
        box=await popup.bounding_box() or {}; popup_width=max(1.0,float(box.get("width") or 1.0))
        rows=_dedupe(await _clickable_rows(popup))
        categories=[]
        for row in rows:
            text=_clean(row.get("text") or ""); width=float((row.get("rect") or {}).get("w") or 0)
            if VENDOR_RE.match(text) and width < popup_width*0.55:
                categories.append(text)
        categories=list(dict.fromkeys(categories))
        upgrade_notice=bool(await popup.get_by_text(re.compile(r"upgrade.*premium|premium.*upgrade",re.I)).count())
        inventory=[]
        for label in categories:
            try:
                nav=popup.get_by_text(label,exact=True).first
                if await nav.count() and await nav.is_visible():
                    await nav.click(no_wait_after=True,timeout=3000); await page.wait_for_timeout(300)
                popup=page.locator("[role='dialog']:visible,[role='listbox']:visible,[role='menu']:visible").last
                box=await popup.bounding_box() or {}; popup_width=max(1.0,float(box.get("width") or 1.0))
            except Exception:
                continue
            for row in _dedupe(await _clickable_rows(popup)):
                text=_clean(row.get("text") or ""); width=float((row.get("rect") or {}).get("w") or 0)
                if width < popup_width*0.55 or not _is_model_row(text) or VENDOR_RE.match(text):
                    continue
                inventory.append(_normalize_model(row,label,upgrade_notice))
        result["categories"]=categories
        result["models"]=_dedupe([{"text":m["display_text"],**m} for m in inventory])
        for m in result["models"]: m.pop("text",None)
        result["upgrade_notice_visible"]=upgrade_notice
        result["status"]="observed"
        return result
    finally:
        try: await page.keyboard.press("Escape")
        except Exception: pass
