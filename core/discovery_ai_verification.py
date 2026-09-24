"""Deterministic verification for AI-assisted Discovery hypotheses."""
from __future__ import annotations
from typing import Any
from urllib.parse import urlparse

from core.browser_behavior_probe import BehaviorAction, ProbePolicy, run_behavior_probe

SAFE_PROBES={"inspect","hover","focus"}


def _control_map(record: dict[str,Any]) -> dict[str,dict[str,Any]]:
    rows=(record.get("technical_candidate") or {}).get("unresolved_controls") or []
    return {str(x.get("control_id") or ""):x for x in rows if x.get("control_id")}


async def _select_page(browser, record):
    origin=str(((record.get("analysis") or {}).get("origin") or "")).lower()
    host=urlparse(origin).hostname or ""
    for context in browser.contexts:
        for page in context.pages:
            if (urlparse(page.url).hostname or "").lower()==host:
                return page
    return None

async def verify_ai_queue(cdp_url:str, record:dict[str,Any], finding:dict[str,Any], *, allow_click:bool=False) -> list[dict[str,Any]]:
    from playwright.async_api import async_playwright
    queue=((finding.get("finding") or {}).get("verification_queue") or [])
    controls=_control_map(record)
    pw=await async_playwright().start()
    browser=await pw.chromium.connect_over_cdp(cdp_url)
    try:
        page=await _select_page(browser,record)
        if page is None:
            return [{"status":"target_page_missing"}]
        out=[]
        for idx,h in enumerate(queue):
            target=str(h.get("target") or "")
            probe=str(h.get("next_probe") or "").lower()
            control=controls.get(target)
            if not control:
                out.append({"index":idx,"target":target,"status":"target_missing"}); continue
            selector=str(control.get("selector") or "")
            if probe=="click" and not allow_click:
                out.append({"index":idx,"target":target,"probe":probe,"status":"requires_confirmation","verification_state":"REQUIRES_CONFIRMATION","promotion":"not_promoted","meaning":str(h.get("meaning") or "")}); continue
            if probe not in SAFE_PROBES|{"click"}:
                out.append({"index":idx,"target":target,"probe":probe,"status":"unsupported_probe"}); continue
            try:
                if probe=="inspect":
                    meta=await page.evaluate("""(s)=>{const e=document.querySelector(s); if(!e)return null; const r=e.getBoundingClientRect(); return {tag:e.tagName,text:(e.innerText||'').trim().slice(0,160),aria:e.getAttribute('aria-label')||'',title:e.getAttribute('title')||'',role:e.getAttribute('role')||'',type:e.getAttribute('type')||'',disabled:e.disabled===true||e.getAttribute('aria-disabled')==='true',visible:r.width>0&&r.height>0};}""",selector)
                    out.append({"index":idx,"target":target,"probe":probe,"status":"probe_completed","verification_state":"OBSERVED_E1","evidence_level":"E1","promotion":"not_promoted","meaning":str(h.get("meaning") or ""),"observation":meta})
                else:
                    obs=await run_behavior_probe(page,BehaviorAction(probe,selector,"verify AI-assisted discovery hypothesis"),ProbePolicy(allow_click=allow_click))
                    changed=(obs.before.get("text")!=obs.after.get("text") or obs.before.get("aria")!=obs.after.get("aria") or obs.before.get("title")!=obs.after.get("title") or obs.before.get("page_text_length")!=obs.after.get("page_text_length"))
                    out.append({"index":idx,"target":target,"probe":probe,"status":"probe_completed" if changed else "no_new_signal","verification_state":"OBSERVED_E1" if changed else "NO_NEW_SIGNAL","evidence_level":"E1","promotion":"not_promoted","meaning":str(h.get("meaning") or ""),"observation":obs.to_dict()})
            except Exception as exc:
                out.append({"index":idx,"target":target,"probe":probe,"status":"probe_failed","verification_state":"FAILED","promotion":"not_promoted","meaning":str(h.get("meaning") or ""),"error":type(exc).__name__,"message":str(exc)[:240]})
        return out
    finally:
        await pw.stop()


def attach_verification_results(finding:dict[str,Any], results:list[dict[str,Any]]) -> dict[str,Any]:
    """Attach deterministic observations to AI hypotheses without semantic promotion."""
    payload=finding.setdefault("finding", {})
    hypotheses=list(payload.get("hypotheses") or [])
    by_target={str(r.get("target") or ""):r for r in results if r.get("target")}
    for h in hypotheses:
        target=str(h.get("target") or "")
        if target in by_target:
            h["verification"]=by_target[target]
            h["status"]="VERIFICATION_OBSERVED" if by_target[target].get("status") in {"probe_completed","no_new_signal"} else "CANDIDATE"
            h["evidence_level"]="E0"
            h["semantic_promotion"]="blocked_pending_deterministic_classification"
    payload["hypotheses"]=hypotheses
    payload["verification_results"]=results
    return finding
