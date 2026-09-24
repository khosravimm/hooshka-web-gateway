from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse

from core.visual_discovery import visible_page_state, visible_interaction_map, classify_user_view_state, capture_user_view

SCHEMA_VERSION = "1.0.0"

def _is_ephemeral_dom_id(value: str) -> bool:
    value=str(value or "").strip()
    if not value:
        return False
    if re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", value, re.I):
        return True
    if re.match(r"^f_[0-9a-f-]{20,}$", value, re.I) or re.search(r"\d{10,}", value):
        return True
    parts=[x for x in re.split(r"[-_]", value) if x]
    randomish=[x for x in parts if len(x)>=6 and re.search(r"[A-Za-z]",x) and re.search(r"\d",x)]
    if len(randomish)>=2:
        return True
    if len(value)>=32 and randomish:
        return True
    return False

SUBMIT_COMMITMENT_TIMEOUT_SECONDS = 4.0
COMMITMENT_NOISE_RE = re.compile(r"(?:/cdn-cgi/rum|analytics|/g/collect|/userinfo(?:$|[/?])|quota|plan-quota|messages\.json|/agent/share/list)", re.I)

def meaningful_commitment_requests(requests: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out=[]
    for item in requests:
        endpoint=str(item.get("endpoint") or "")
        method=str(item.get("method") or "").upper()
        resource_type=str(item.get("resource_type") or "").lower()
        if COMMITMENT_NOISE_RE.search(endpoint):
            continue
        if resource_type == "websocket" or method in {"POST","PUT","PATCH"}:
            out.append(item)
    return out

async def _read_composer_value(composer) -> str | None:
    try:
        if await composer.count() == 0:
            return None
        try:
            return await composer.input_value()
        except Exception:
            return (await composer.inner_text()).strip()
    except Exception:
        return None

async def _observe_commitment(page, composer, prompt: str, expected: str, started_url: str, requests: list[dict[str, Any]], request_offset: int, timeout_seconds: float) -> dict[str, Any]:
    deadline=asyncio.get_running_loop().time()+float(timeout_seconds)
    transition_observed=False
    prompt_absent_after_navigation=False
    while asyncio.get_running_loop().time() < deadline:
        await page.wait_for_timeout(250)
        current_value=await _read_composer_value(composer)
        body=await page.locator("body").inner_text()
        if expected in body:
            return {"signal":"verified_response_observed","current_value":current_value,"transition_observed":True,"prompt_absent_after_navigation":False}
        meaningful=meaningful_commitment_requests(requests[request_offset:])
        if meaningful:
            return {"signal":"provider_network_activity","current_value":current_value,"transition_observed":True,"prompt_absent_after_navigation":False,"meaningful_requests":meaningful}
        if page.url != started_url:
            transition_observed=True
            prompt_absent_after_navigation = prompt not in body
        elif current_value is None or prompt not in str(current_value):
            transition_observed=True
    return {"signal":None,"current_value":await _read_composer_value(composer),"transition_observed":transition_observed,"prompt_absent_after_navigation":prompt_absent_after_navigation,"meaningful_requests":meaningful_commitment_requests(requests[request_offset:])}

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


async def probe_composer_submit_candidates(page, discovery: dict[str, Any], access_semantics: dict[str, Any] | None = None) -> dict[str, Any]:
    frontend = discovery.get("frontend") or {}
    selector = str(frontend.get("composer_selector") or "").strip()
    if not selector:
        return {"status":"skipped","reason":"composer_selector_missing","candidates":[]}
    loc = page.locator(selector).first
    if await loc.count() == 0 or not await loc.is_visible():
        return {"status":"skipped","reason":"composer_not_visible","candidates":[]}
    try:
        original = await loc.input_value()
    except Exception:
        original = (await loc.inner_text()).strip()
    if original:
        return {"status":"skipped","reason":"composer_not_empty","candidates":[]}
    from core.visual_discovery import visual_action_gate
    gate = await visual_action_gate(page, "provider_interaction")
    if not gate.get("allowed"):
        return {"status":"blocked","reason":"provider_visual_state","candidates":[],"marker_sent":False,"classification":gate.get("classification") or {}}
    from core.control_discovery import ENUMERATE_JS
    before = await page.evaluate(ENUMERATE_JS)
    before_by_selector = {str(x.get("selector") or ""): x for x in before if str(x.get("selector") or "")}
    box = await loc.bounding_box() or {}
    marker = "HWG_DISCOVERY_PROBE"
    try:
        await loc.fill(marker)
        await page.wait_for_timeout(700)
        after = await page.evaluate(ENUMERATE_JS)
    finally:
        try:
            await loc.fill("")
            await page.wait_for_timeout(250)
        except Exception:
            pass
    def near_composer(item: dict[str, Any]) -> bool:
        r = item.get("rect") or {}
        if not box or not r:
            return False
        cy = float(box.get("y",0)) + float(box.get("height",0))/2
        iy = float(r.get("y",0)) + float(r.get("h",0))/2
        vertical = abs(cy - iy) <= max(80.0, float(box.get("height",0))*2.5)
        left_gap = abs(float(r.get("x",0)) - (float(box.get("x",0)) + float(box.get("width",0))))
        right_gap = abs((float(r.get("x",0)) + float(r.get("w",0))) - float(box.get("x",0)))
        return vertical and min(left_gap,right_gap) <= 180.0
    candidates=[]
    for item in after:
        sel=str(item.get("selector") or "")
        if not sel or not near_composer(item):
            continue
        if str(item.get("tag") or "").upper() != "BUTTON" and str(item.get("role") or "").lower() != "button":
            continue
        previous=before_by_selector.get(sel)
        appeared=previous is None
        enabled_transition=bool(previous and previous.get("disabled") is True and item.get("disabled") is not True)
        if not appeared and not enabled_transition:
            continue
        candidates.append({
            "selector":sel,"text":item.get("text") or "","aria":item.get("aria") or "",
            "title":item.get("title") or "","rect":item.get("rect") or {},
            "evidence":"appears_when_empty_composer_is_temporarily_filled" if appeared else "becomes_enabled_when_composer_is_temporarily_filled",
            "status":"candidate_unverified","confidence":"medium",
        })
    return {"status":"observed","marker_sent":False,"composer_restored":True,"candidates":candidates}

async def observe_url(url: str, cdp_url: str, preferred_target_id: str | None = None, candidate_id: str | None = None) -> dict[str, Any]:
    from playwright.async_api import async_playwright

    pw = await async_playwright().start()
    browser = await pw.chromium.connect_over_cdp(cdp_url)
    context = browser.contexts[0]
    page = None
    target_reused = False
    if preferred_target_id:
        for existing in context.pages:
            try:
                sess = await context.new_cdp_session(existing)
                info = await sess.send("Target.getTargetInfo")
                await sess.detach()
                if ((info.get("targetInfo") or {}).get("targetId") == preferred_target_id):
                    page = existing; target_reused = True; break
            except Exception:
                continue
    if page is None:
        page = await context.new_page()
    try:
        try:
            if not target_reused:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        except Exception:
            pass
        host = urlparse(url).hostname or "candidate"
        trace = []
        state = {}; interaction_map = {}; classification = {"state":"unknown","evidence":"not observed"}
        for idx, ratio in enumerate((0.0, 0.5, 1.0, 0.0), start=1):
            await page.wait_for_timeout(1500 if idx > 1 else 3500)
            try:
                await page.evaluate("r => scrollTo(0, Math.max(0,(document.documentElement.scrollHeight-innerHeight)*r))", ratio)
                await page.wait_for_timeout(500)
            except Exception:
                pass
            state = await visible_page_state(page)
            interaction_map = await visible_interaction_map(page)
            classification = classify_user_view_state(state)
            shot = await capture_user_view(page, host, f"onboarding-pass-{idx}")
            trace.append({"pass":idx,"scroll_ratio":ratio,"classification":classification,"url":page.url,"title":await page.title(),"controls":len(interaction_map.get("controls") or []),"screenshot":shot.get("screenshot")})
            if classification.get("state") != "unknown":
                break
        sess = await context.new_cdp_session(page)
        target_info = await sess.send("Target.getTargetInfo")
        await sess.detach()
        target_id = (target_info.get("targetInfo") or {}).get("targetId")
        deterministic_discovery = None
        access_semantics = {"state":"UNKNOWN","confidence":"low","evidence":["not_probed"]}
        if classification.get("state") in {"ready","auth_ambiguous","login_required"}:
            from core.discovery_engine import discover_page
            from core.blind_discovery import probe_observed_access_semantics
            report = await discover_page(page, candidate_id or _slug_host(urlparse(url).hostname or "candidate"))
            deterministic_discovery = report.__dict__
            access_semantics = await probe_observed_access_semantics(page, (report.backend or {}).get("candidate_endpoints") or [])
            if classification.get("state") == "auth_ambiguous" and str(access_semantics.get("state") or "UNKNOWN").upper() == "UNKNOWN":
                diagnostic_attempts=[]
                for attempt in range(1, 3):
                    await page.wait_for_timeout(1500)
                    state = await visible_page_state(page)
                    classification = classify_user_view_state(state)
                    report = await discover_page(page, candidate_id or _slug_host(urlparse(url).hostname or "candidate"))
                    deterministic_discovery = report.__dict__
                    access_semantics = await probe_observed_access_semantics(page, (report.backend or {}).get("candidate_endpoints") or [])
                    diagnostic_attempts.append({"attempt":attempt,"visual_state":classification.get("state"),"access_state":access_semantics.get("state"),"evidence":access_semantics.get("evidence")})
                    if classification.get("state") != "auth_ambiguous" or str(access_semantics.get("state") or "UNKNOWN").upper() != "UNKNOWN":
                        break
                deterministic_discovery["access_diagnostic_attempts"] = diagnostic_attempts
            unknown_controls = [c for c in (report.frontend.get("controls") or []) if c.get("kind") == "unclassified"][:6]
            behavior_evidence = []
            access_state = str(access_semantics.get("state") or "UNKNOWN").upper()
            interaction_allowed = classification.get("state") == "ready" or (classification.get("state") == "auth_ambiguous" and access_state == "ACCESS_AVAILABLE")
            if interaction_allowed and unknown_controls:
                from core.browser_behavior_probe import run_behavior_probe, BehaviorAction, ProbePolicy
                from core.control_discovery import classify
                for control in unknown_controls:
                    selector = str(control.get("selector") or "").strip()
                    if not selector:
                        continue
                    try:
                        obs = await run_behavior_probe(page, BehaviorAction(kind="hover", selector=selector, purpose="classify unknown control"), ProbePolicy(allow_hover=True, allow_focus=True, allow_click=False, settle_ms=800))
                        item = obs.to_dict()
                        before_lines = {x.strip() for x in str((item.get("before") or {}).get("page_text_tail") or "").splitlines() if x.strip()}
                        after_lines = [x.strip() for x in str((item.get("after") or {}).get("page_text_tail") or "").splitlines() if x.strip()]
                        added = [x for x in after_lines if x not in before_lines][-20:]
                        inferred = classify([{"tag":"tooltip","text":" ".join(added),"aria":"","title":"","testid":"","eid":"","cls":"","role":"","value":"","parent":""}]) if added else []
                        behavior_evidence.append({"selector":selector,"action":"hover","added_visible_text":added,"inferred_controls":[c.__dict__ for c in inferred]})
                    except Exception as exc:
                        behavior_evidence.append({"selector":selector,"action":"hover","error":type(exc).__name__})
            deterministic_discovery["behavior_evidence"] = behavior_evidence
            deterministic_discovery["composer_submit_probe"] = (await probe_composer_submit_candidates(page, deterministic_discovery, access_semantics)) if interaction_allowed else {"status":"blocked","reason":"access_gate","marker_sent":False,"candidates":[]}
        file_inputs = await page.locator('input[type="file"]').count()
        editable = await page.locator('textarea:visible,[contenteditable="true"]:visible,input[type="text"]:visible').count()
        selects = await page.locator('select:visible,[role="combobox"]:visible').count()
        return {
            "schema_version": SCHEMA_VERSION, "final_url": page.url, "title": await page.title(),
            "classification": classification, "access_semantics": access_semantics, "user_view": state, "exploration_trace": trace,
            "interaction_summary": {"controls":len(interaction_map.get("controls") or []),"headings":len(interaction_map.get("headings") or []),"horizontal_overflow":bool(interaction_map.get("horizontal_overflow")),"clipped":len(interaction_map.get("clipped") or []),"file_inputs":file_inputs,"editable_inputs":editable,"selectors":selects},
            "page_left_open": True,
            "target_id": target_id,
            "target_reused": target_reused,
            "preferred_target_id": preferred_target_id,
            "deterministic_discovery": deterministic_discovery,
            "discovery_completed": deterministic_discovery is not None, "autonomous_passes": len(trace),
            "needs_deeper_exploration": classification.get("state") == "unknown",
        }
    finally:
        await pw.stop()



def synthesize_technical_candidate(analysis: dict[str, Any], observation: dict[str, Any] | None) -> dict[str, Any]:
    observation = observation or {}
    classification = observation.get("classification") or {}
    state = str(classification.get("state") or "unknown")
    access_semantics = observation.get("access_semantics") or {}
    access_state = str(access_semantics.get("state") or "UNKNOWN").upper()
    discovery = observation.get("deterministic_discovery") or {}
    frontend = discovery.get("frontend") or {}
    backend = discovery.get("backend") or {}
    capabilities = list(discovery.get("capabilities") or [])
    controls = list(frontend.get("controls") or [])
    if access_state == "LOGIN_REQUIRED" or state in {"login_required", "challenge"}:
        workflow_state = "WAITING_FOR_USER_GATE"
        next_required = "user_complete_login_or_verification"
        user_action_required = True
    elif state == "auth_ambiguous" and access_state == "ACCESS_AVAILABLE":
        workflow_state = "TECHNICAL_CANDIDATE_READY"
        next_required = "transport_and_behavior_qualification"
        user_action_required = False
    elif state == "auth_ambiguous" and access_state == "UNKNOWN":
        workflow_state = "ACCESS_DIAGNOSTIC_REQUIRED"
        next_required = "resolve_authentication_state"
        user_action_required = False
    elif state == "unknown" or observation.get("needs_deeper_exploration"):
        workflow_state = "EXPLORER_DEEPENING"
        next_required = "autonomous_deeper_exploration"
        user_action_required = False
    elif state == "ready" and observation.get("discovery_completed"):
        workflow_state = "TECHNICAL_CANDIDATE_READY"
        next_required = "transport_and_behavior_qualification"
        user_action_required = False
    else:
        workflow_state = "OBSERVATION_IN_PROGRESS"
        next_required = "continue_observation"
        user_action_required = False
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "new_provider_technical_candidate",
        "status": "E1_UNCERTIFIED",
        "workflow_state": workflow_state,
        "next_required": next_required,
        "user_action_required": user_action_required,
        "provider_id": analysis.get("suggested_provider_id"),
        "origin": analysis.get("origin"),
        "home_url": analysis.get("url"),
        "reuse_adapter_type": analysis.get("known_adapter_type"),
        "runtime_key": analysis.get("recommended_runtime_key"),
        "target_id": observation.get("target_id"),
        "access_semantics": access_semantics,
        "composer_selector": frontend.get("composer_selector"),
        "controls": controls,
        "capability_claims": capabilities,
        "upload_surface": frontend.get("upload_surface") or {},
        "backend_hints": {
            "candidate_endpoints": backend.get("candidate_endpoints") or [],
            "stream_transports": backend.get("stream_transports") or [],
        },
        "behavior_evidence": discovery.get("behavior_evidence") or [],
        "submit_candidates": ((discovery.get("composer_submit_probe") or {}).get("candidates") or []),
        "composer_submit_probe": discovery.get("composer_submit_probe") or {},
        "unresolved_controls": [c for c in controls if c.get("kind") == "unclassified"],
    }



async def discover_response_surface_from_marker(page, marker: str) -> dict[str, Any]:
    if not marker:
        return {"status":"blocked","reason":"marker_missing"}
    rows = await page.evaluate(r"""marker => {
      const esc = s => String(s||'').replace(/\\/g,'\\\\').replace(/'/g,"\\'");
      const eph = v => { const z=String(v||''); const parts=z.split(/[-_]/).filter(Boolean); const mixed=parts.filter(x=>x.length>=6&&/[a-z]/i.test(x)&&/\d/.test(x)); return /^f_[0-9a-f-]{20,}$/i.test(z)||/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i.test(z)||/\d{10,}/.test(z)||mixed.length>=2||(z.length>=32&&mixed.length>=1); };
      const selectorOf = cur => {
        const cls=String(cur.className||'').split(/\s+/).filter(Boolean).filter(x=>/^[A-Za-z_][A-Za-z0-9_-]{0,63}$/.test(x));
        const tid=cur.getAttribute('data-testid'); const aria=cur.getAttribute('aria-label'); const role=cur.getAttribute('role');
        let selector='';
        if(cur.id && !eph(cur.id)) selector='#'+CSS.escape(cur.id);
        else if(tid) selector=`[data-testid='${esc(tid)}']`;
        else if(aria) selector=`[aria-label='${esc(aria)}']`;
        else if(cls.length) selector=cur.tagName.toLowerCase()+cls.map(x=>'.'+CSS.escape(x)).join('');
        else if(role) selector=`${cur.tagName.toLowerCase()}[role='${esc(role)}']`;
        return {selector,cls,tid:tid||'',aria:aria||'',role:role||''};
      };
      const all=[...document.querySelectorAll('body *')];
      const matches=all.filter(e => (e.innerText||'').includes(marker));
      const out=[];
      for(const cur of matches.slice(0,160)){
        const meta=selectorOf(cur); if(!meta.selector) continue;
        const text=(cur.innerText||'').trim();
        const depth=(()=>{let d=0,n=cur;while(n&&n!==document.body){d++;n=n.parentElement;}return d;})();
        out.push({tag:cur.tagName,id:cur.id||'',cls:meta.cls,role:meta.role,testid:meta.tid,aria:meta.aria,selector:meta.selector,text:text.slice(0,1800),children:cur.children.length,depth,exact:text===marker});
      }
      return out;
    }""", marker)
    candidates=[]
    for row in rows or []:
        selector=str(row.get("selector") or "").strip()
        classes=[str(x) for x in (row.get("cls") or [])]
        row_id=str(row.get("id") or "").strip()
        if row_id and _is_ephemeral_dom_id(row_id):
            tag=str(row.get("tag") or "div").lower()
            selector=(tag + "".join("."+re.sub(r"[^A-Za-z0-9_-]", "", x) for x in classes if re.match(r"^[A-Za-z_]",x))) if classes else ""
        if not selector:
            continue
        try:
            loc=page.locator(selector)
            count=await loc.count()
            texts=await loc.all_inner_texts()
        except Exception:
            continue
        matching=[str(t).strip() for t in texts if marker in str(t)]
        if not matching:
            continue
        semantic=sum(1 for x in classes if re.search(r"assistant|bot|message|chat|response|markdown|content",x,re.I))
        exact=bool(row.get("exact")) or any(t == marker for t in matching)
        extra=min((max(0,len(t)-len(marker)) for t in matching), default=99999)
        depth=int(row.get("depth") or 0)
        children=int(row.get("children") or 0)
        score=(35 if exact else 0)+(semantic*6)+min(depth,18)-min(max(count-1,0),8)-min(extra//40,15)-min(children,8)
        candidates.append({"selector":selector,"count":count,"score":score,"exact_marker_text":exact,"classes":classes,"tag":row.get("tag"),"children":children,"depth":depth,"extra_text_chars":extra,"evidence":"marker_anchored_dom_surface"})
    if not candidates:
        return {"status":"blocked","reason":"marker_surface_unresolved"}
    candidates.sort(key=lambda x:(x["exact_marker_text"],x["score"],-x["extra_text_chars"]),reverse=True)
    best=candidates[0]
    return {"status":"E2_VERIFIED","evidence_level":"E2","selector":best["selector"],"count":best["count"],"marker":marker,"strategy":"smallest_stable_marker_anchored_surface","exact_marker_text":best["exact_marker_text"],"candidates":candidates[:8]}


async def enrich_existing_e2_response_surface(cdp_url: str, record: dict[str, Any]) -> dict[str, Any]:
    existing = record.get("submit_qualification") or {}
    if existing.get("status") != "E2_VERIFIED":
        return {"status":"blocked","reason":"e2_submit_evidence_missing"}
    current = existing.get("response_surface") or {}
    if current.get("status") == "E2_VERIFIED":
        return {**current,"reused_evidence":True}
    marker = str(existing.get("expected_marker") or "").strip()
    target_id = str(existing.get("target_id") or "").strip()
    if not marker or not target_id:
        return {"status":"blocked","reason":"e2_marker_or_target_missing"}
    from playwright.async_api import async_playwright
    pw = await async_playwright().start()
    try:
        browser = await pw.chromium.connect_over_cdp(cdp_url)
        context = browser.contexts[0] if browser.contexts else None
        if context is None:
            return {"status":"blocked","reason":"browser_context_missing"}
        page = None
        for current_page in context.pages:
            try:
                session = await context.new_cdp_session(current_page)
                info = await session.send("Target.getTargetInfo")
                await session.detach()
                if ((info.get("targetInfo") or {}).get("targetId") == target_id):
                    page = current_page; break
            except Exception:
                continue
        if page is None:
            return {"status":"blocked","reason":"target_not_alive"}
        surface = await discover_response_surface_from_marker(page, marker)
        if surface.get("status") == "E2_VERIFIED":
            existing["response_surface"] = dict(surface)
            record["submit_qualification"] = existing
            technical = record.setdefault("technical_candidate", {})
            technical["response_surface"] = dict(surface)
            if technical.get("workflow_state") == "ROUNDTRIP_QUALIFIED":
                technical["next_required"] = "adapter_candidate_generation"
        return surface
    finally:
        await pw.stop()


def enrich_existing_e2_response_surface_sync(cdp_url: str, record: dict[str, Any]) -> dict[str, Any]:
    return asyncio.run(enrich_existing_e2_response_surface(cdp_url, record))


def _stable_response_selector(response_surface: dict[str, Any]) -> tuple[str, list[str]]:
    rows=[]
    primary=str(response_surface.get("selector") or "").strip()
    if primary:
        rows.append({"selector":primary,"score":10**6,"exact_marker_text":bool(response_surface.get("exact_marker_text"))})
    rows.extend(list(response_surface.get("candidates") or []))
    seen=set(); stable=[]
    for row in rows:
        selector=str(row.get("selector") or "").strip()
        if not selector or selector in seen:
            continue
        seen.add(selector)
        if selector.startswith("#") and _is_ephemeral_dom_id(selector[1:]):
            continue
        stable.append((bool(row.get("exact_marker_text")), int(row.get("score") or 0), selector))
    stable.sort(key=lambda x:(x[0],x[1]), reverse=True)
    selectors=[x[2] for x in stable]
    return (selectors[0] if selectors else ""), selectors


def generate_adapter_candidate(record: dict[str, Any]) -> dict[str, Any]:
    technical = record.get("technical_candidate") or {}
    qualification = record.get("submit_qualification") or {}
    response_surface = technical.get("response_surface") or qualification.get("response_surface") or {}
    if qualification.get("status") != "E2_VERIFIED":
        return {"status":"blocked","reason":"roundtrip_e2_missing"}
    if response_surface.get("status") != "E2_VERIFIED":
        return {"status":"blocked","reason":"response_surface_e2_missing"}
    claims = list(technical.get("capability_claims") or [])
    proven = []
    unresolved = []
    for claim in claims:
        ev = claim.get("evidence") or {}
        row = {"name":claim.get("name"),"supported":bool(claim.get("supported")),"evidence_level":ev.get("type") or "E0","confidence":ev.get("confidence") or "unknown"}
        (proven if row["supported"] else unresolved).append(row)
    response_selector, response_selectors = _stable_response_selector(response_surface)
    if not response_selector:
        return {"status":"blocked","reason":"stable_response_surface_missing"}
    adapter = {
        "schema_version": SCHEMA_VERSION,
        "kind": "browser_ui_adapter_candidate",
        "status": "GENERATED_UNCERTIFIED",
        "provider_id": technical.get("provider_id"),
        "origin": technical.get("origin"),
        "home_url": technical.get("home_url"),
        "runtime_key": technical.get("runtime_key"),
        "transport": {
            "mode": "browser_ui_candidate",
            "target_strategy": "same_origin_live_page",
            "composer": {"selector":technical.get("composer_selector"),"evidence_level":"E1"},
            "submit": {"strategy":"dynamic_after_fill_near_composer","evidence_level":"E2","last_verified_selector":qualification.get("submit_selector")},
            "response": {"selector":response_selector,"selectors":response_selectors,"strategy":"stable_recorded_response_surface","source_strategy":response_surface.get("strategy"),"evidence_level":"E2"},
        },
        "capabilities": {"observed_supported":proven,"unresolved_or_unsupported":unresolved},
        "upload_surface": technical.get("upload_surface") or {},
        "backend_hints": technical.get("backend_hints") or {},
        "unresolved_controls": technical.get("unresolved_controls") or [],
        "evidence_refs": {"submit_marker":qualification.get("expected_marker"),"target_id":qualification.get("target_id"),"response_surface_marker":response_surface.get("marker")},
        "next_required": "adapter_materialization_and_conformance",
    }
    record["adapter_candidate"] = adapter
    technical["workflow_state"] = "ADAPTER_CANDIDATE_GENERATED"
    technical["next_required"] = "adapter_materialization_and_conformance"
    technical["user_action_required"] = False
    return adapter


async def qualify_submit_candidate(cdp_url: str, record: dict[str, Any], timeout_seconds: float = 45.0) -> dict[str, Any]:
    technical = record.get("technical_candidate") or {}
    existing = record.get("submit_qualification") or {}
    if technical.get("workflow_state") == "ROUNDTRIP_QUALIFIED" and existing.get("status") != "E2_VERIFIED":
        technical["workflow_state"] = "TECHNICAL_CANDIDATE_READY"
        technical["next_required"] = "transport_and_behavior_qualification"
        technical["status"] = "E1_UNCERTIFIED"
    if technical.get("workflow_state") != "TECHNICAL_CANDIDATE_READY":
        return {"status":"blocked","reason":"technical_candidate_not_ready","submitted":False}
    if existing.get("status") == "E2_VERIFIED":
        return {**existing, "reused_evidence":True}
    target_id = str(technical.get("target_id") or "").strip()
    composer_selector = str(technical.get("composer_selector") or "").strip()
    candidates = list(technical.get("submit_candidates") or [])
    if not target_id or not composer_selector or not candidates:
        return {"status":"blocked","reason":"qualification_prerequisites_missing","submitted":False}
    from playwright.async_api import async_playwright
    import secrets
    pw = await async_playwright().start()
    try:
        browser = await pw.chromium.connect_over_cdp(cdp_url)
        context = browser.contexts[0] if browser.contexts else None
        if context is None:
            return {"status":"blocked","reason":"browser_context_missing","submitted":False}
        page = None
        for current in context.pages:
            try:
                session = await context.new_cdp_session(current)
                info = await session.send("Target.getTargetInfo")
                await session.detach()
                if ((info.get("targetInfo") or {}).get("targetId") == target_id):
                    page = current; break
            except Exception:
                continue
        if page is None:
            return {"status":"blocked","reason":"target_not_alive","submitted":False}
        # Selectors discovered from modern SPAs are often session-generated.
        # Re-discover the live composer and submit surface immediately before E2;
        # persisted selectors are hints, never durable truth.
        refreshed = False
        composer = page.locator(composer_selector).first if composer_selector else None
        composer_ok = bool(composer_selector) and await composer.count() > 0 and await composer.is_visible()
        if not composer_ok:
            from core.discovery_engine import discover_page
            fresh_report = await discover_page(page, str(technical.get("provider_id") or "candidate"))
            fresh = fresh_report.__dict__
            fresh_frontend = fresh.get("frontend") or {}
            fresh_selector = str(fresh_frontend.get("composer_selector") or "").strip()
            if not fresh_selector:
                return {"status":"blocked","reason":"composer_not_visible_after_rediscovery","submitted":False}
            composer = page.locator(fresh_selector).first
            if await composer.count() == 0 or not await composer.is_visible():
                return {"status":"blocked","reason":"composer_not_visible_after_rediscovery","submitted":False}
            submit_probe = await probe_composer_submit_candidates(page, fresh, technical.get("access_semantics") or {})
            fresh_candidates = list(submit_probe.get("candidates") or [])
            if not fresh_candidates:
                return {"status":"blocked","reason":"submit_candidate_missing_after_rediscovery","submitted":False}
            composer_selector = fresh_selector
            candidates = fresh_candidates
            technical["composer_selector"] = fresh_selector
            technical["submit_candidates"] = fresh_candidates
            technical["composer_submit_probe"] = submit_probe
            refreshed = True
        try:
            current_value = await composer.input_value()
        except Exception:
            current_value = (await composer.inner_text()).strip()
        if current_value:
            return {"status":"blocked","reason":"composer_not_empty","submitted":False}
        from core.visual_discovery import visual_action_gate
        preflight = await visual_action_gate(page, "certification_probe")
        access_state = str((technical.get("access_semantics") or {}).get("state") or "UNKNOWN").upper()
        auth_resolved = str((preflight.get("classification") or {}).get("state") or "") == "auth_ambiguous" and access_state == "ACCESS_AVAILABLE"
        if not preflight.get("allowed") and not auth_resolved:
            return {"status":"blocked","reason":"provider_visual_state","submitted":False,"commitment_state":"not_sent","classification":preflight.get("classification") or {}}
        digits = str(100000 + secrets.randbelow(900000))
        expected = "HWGQ" + digits[::-1]
        prompt = f"Reply with prefix HWGQ followed immediately by the reverse of {digits}. Return only that."
        from core.control_discovery import ENUMERATE_JS
        before_controls = await page.evaluate(ENUMERATE_JS)
        before_signature = {(str(x.get("text") or ""), str(x.get("aria") or ""), str(x.get("title") or ""), str(x.get("role") or ""), str(x.get("tag") or ""), int((x.get("rect") or {}).get("x") or 0), int((x.get("rect") or {}).get("y") or 0)) for x in before_controls}
        before_by_selector = {str(x.get("selector") or ""): x for x in before_controls if str(x.get("selector") or "")}
        requests = []
        def on_request(req):
            if len(requests) >= 80 or req.resource_type not in {"xhr","fetch","websocket"}:
                return
            endpoint = _safe_endpoint(req.url)
            if endpoint:
                requests.append({"method":req.method,"endpoint":endpoint,"resource_type":req.resource_type})
        page.on("request", on_request)
        submitted = False
        started_url = page.url
        try:
            await composer.fill(prompt)
            await page.wait_for_timeout(700)
            live_controls = await page.evaluate(ENUMERATE_JS)
            box = await composer.bounding_box() or {}
            prior_semantics = {(str(x.get("text") or "").strip().lower(), str(x.get("aria") or "").strip().lower(), str(x.get("title") or "").strip().lower()) for x in candidates}
            prior_selectors = {str(x.get("selector") or "").strip() for x in candidates if str(x.get("selector") or "").strip()}
            def near(item):
                r=item.get("rect") or {}
                if not box or not r: return False
                cy=float(box.get("y",0))+float(box.get("height",0))/2
                iy=float(r.get("y",0))+float(r.get("h",0))/2
                left_gap=abs((float(r.get("x",0))+float(r.get("w",0)))-float(box.get("x",0)))
                right_gap=abs(float(r.get("x",0))-(float(box.get("x",0))+float(box.get("width",0))))
                return abs(cy-iy) <= max(90.0,float(box.get("height",0))*3.0) and min(left_gap,right_gap) <= 220.0
            ranked=[]
            for item in live_controls:
                if str(item.get("tag") or "").upper() != "BUTTON" and str(item.get("role") or "").lower() != "button": continue
                if item.get("disabled") is True or not near(item): continue
                text=str(item.get("text") or "").strip().lower(); aria=str(item.get("aria") or "").strip().lower(); title=str(item.get("title") or "").strip().lower()
                r=item.get("rect") or {}; sig=(text,aria,title,str(item.get("role") or ""),str(item.get("tag") or ""),int(r.get("x") or 0),int(r.get("y") or 0))
                selector_now=str(item.get("selector") or "").strip()
                previous=before_by_selector.get(selector_now)
                enabled_transition=bool(previous and previous.get("disabled") is True and item.get("disabled") is not True)
                appeared=sig not in before_signature
                score=0
                if selector_now in prior_selectors: score += 20
                if enabled_transition: score += 12
                if appeared: score += 6
                if (text,aria,title) in prior_semantics and any((text,aria,title)): score += 6
                if re.search(r"send|submit|arrow[_ -]?up", " ".join([text,aria,title]), re.I): score += 5
                if selector_now not in prior_selectors and not enabled_transition and not appeared and not re.search(r"send|submit|arrow[_ -]?up", " ".join([text,aria,title]), re.I):
                    continue
                ranked.append((score,item))
            ranked.sort(key=lambda pair: pair[0], reverse=True)
            if not ranked or ranked[0][0] <= 0:
                await composer.fill("")
                return {"status":"blocked","reason":"live_submit_control_unresolved_after_fill","submitted":False}
            selector = str(ranked[0][1].get("selector") or "").strip()
            submit = page.locator(selector).first if selector else None
            if not selector or await submit.count() == 0 or not await submit.is_visible():
                await composer.fill("")
                return {"status":"blocked","reason":"live_submit_control_not_visible","submitted":False}
            requests_before_click=len(requests)
            activation_strategy="click"
            await submit.click(timeout=5000, no_wait_after=True)
            commitment=await _observe_commitment(page,composer,prompt,expected,started_url,requests,requests_before_click,SUBMIT_COMMITMENT_TIMEOUT_SECONDS)
            commitment_signal=commitment.get("signal")
            if not commitment_signal:
                final_state = await visible_page_state(page)
                transition_observed=bool(commitment.get("transition_observed"))
                prompt_absent_after_navigation=bool(commitment.get("prompt_absent_after_navigation"))
                if page.url != started_url and prompt_absent_after_navigation:
                    status="E2_PRECOMMIT_TRANSITION"; reason="precommit_page_transition"; retry_allowed=True
                elif transition_observed:
                    status="E2_COMMITMENT_AMBIGUOUS"; reason="commitment_not_proven"; retry_allowed=False
                else:
                    status="E2_FAILED_BEFORE_COMMIT"; reason="submit_activation_not_committed"; retry_allowed=True
                return {
                    "status":status, "evidence_level":"E2",
                    "submitted":False, "retry_allowed":retry_allowed, "clicked":True,
                    "activation_strategy":activation_strategy,
                    "reason":reason, "commitment_state":"not_proven", "response_verified":False,
                    "expected_marker":expected, "challenge_kind":"reverse_digits", "challenge_input":digits,
                    "submit_selector":selector, "target_id":target_id,
                    "live_selector_rediscovered":refreshed, "composer_selector":composer_selector,
                    "started_url":started_url, "final_url":page.url,
                    "network_endpoints":requests[-30:],
                    "meaningful_commitment_requests":meaningful_commitment_requests(requests[requests_before_click:]),
                    "final_user_view_classification":classify_user_view_state(final_state),
                }
            submitted = True
            deadline = asyncio.get_running_loop().time() + float(timeout_seconds)
            verified = False
            while asyncio.get_running_loop().time() < deadline:
                await page.wait_for_timeout(500)
                body = await page.locator("body").inner_text()
                if expected in body:
                    verified = True
                    break
            final_state = await visible_page_state(page)
            response_surface = await discover_response_surface_from_marker(page, expected) if verified else {"status":"blocked","reason":"response_not_verified"}
            unique_endpoints=[]; seen=set()
            for item in requests:
                key=(item["method"],item["endpoint"],item["resource_type"])
                if key not in seen:
                    seen.add(key); unique_endpoints.append(item)
            return {
                "status":"E2_VERIFIED" if verified else "E2_FAILED_AFTER_COMMIT",
                "evidence_level":"E2", "submitted":True, "retry_allowed":False,
                "activation_strategy":activation_strategy, "commitment_signal":commitment_signal,
                "response_verified":verified, "expected_marker":expected,
                "challenge_kind":"reverse_digits", "challenge_input":digits,
                "submit_selector":selector, "target_id":target_id,
                "live_selector_rediscovered":refreshed, "composer_selector":composer_selector,
                "started_url":started_url, "final_url":page.url,
                "network_endpoints":unique_endpoints[-30:],
                "response_surface":response_surface,
                "final_user_view_classification":classify_user_view_state(final_state),
            }
        finally:
            page.remove_listener("request", on_request)
            if not submitted:
                try:
                    await composer.fill("")
                except Exception:
                    pass
    finally:
        await pw.stop()


def apply_submit_qualification(record: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    previous = record.get("submit_qualification") or {}
    history = record.setdefault("qualification_history", [])
    if previous:
        fp=(previous.get("status"),previous.get("target_id"),previous.get("submit_selector"),previous.get("expected_marker"))
        if not any((x.get("status"),x.get("target_id"),x.get("submit_selector"),x.get("expected_marker"))==fp for x in history): history.append(dict(previous))
    if previous.get("status") == "E2_VERIFIED" and not result.get("submitted") and result.get("status") != "E2_VERIFIED":
        return record
    record["submit_qualification"] = dict(result)
    technical = record.setdefault("technical_candidate", {})
    if result.get("status") == "E2_VERIFIED":
        selector = result.get("submit_selector")
        for candidate in technical.get("submit_candidates") or []:
            if candidate.get("selector") == selector:
                candidate["status"] = "E2_VERIFIED"
                candidate["confidence"] = "high"
                candidate["evidence_level"] = "E2"
        technical["response_surface"] = dict(result.get("response_surface") or {})
        technical["status"] = "PARTIAL_E2_UNCERTIFIED"
        technical["workflow_state"] = "ROUNDTRIP_QUALIFIED"
        technical["next_required"] = "adapter_candidate_generation" if (result.get("response_surface") or {}).get("status") == "E2_VERIFIED" else "assistant_surface_discovery"
        technical["user_action_required"] = False
    elif result.get("submitted"):
        technical["workflow_state"] = "QUALIFICATION_FAILED_AFTER_COMMIT"
        technical["next_required"] = "explorer_diagnose_failed_roundtrip"
        technical["user_action_required"] = False
    return record


def qualify_submit_candidate_sync(cdp_url: str, record: dict[str, Any], timeout_seconds: float = 45.0) -> dict[str, Any]:
    return asyncio.run(qualify_submit_candidate(cdp_url, record, timeout_seconds=timeout_seconds))


async def diagnose_committed_qualification(cdp_url: str, record: dict[str, Any]) -> dict[str, Any]:
    existing=dict(record.get("submit_qualification") or {})
    if existing.get("status") != "E2_FAILED_AFTER_COMMIT" or existing.get("retry_allowed") is not False:
        return {"status":"blocked","reason":"nonretryable_committed_failure_required"}
    marker=str(existing.get("expected_marker") or "").strip()
    if not marker:
        return {"status":"blocked","reason":"expected_marker_missing"}
    target_id=str(existing.get("target_id") or "").strip()
    origin=urlparse(str((record.get("analysis") or {}).get("url") or (record.get("technical_candidate") or {}).get("home_url") or ""))
    wanted=f"{origin.scheme}://{origin.netloc}" if origin.scheme and origin.netloc else ""
    from playwright.async_api import async_playwright
    pw=await async_playwright().start()
    try:
        browser=await pw.chromium.connect_over_cdp(cdp_url)
        context=browser.contexts[0] if browser.contexts else None
        if context is None:
            return {"status":"blocked","reason":"browser_context_missing"}
        page=None
        for current in context.pages:
            try:
                session=await context.new_cdp_session(current); info=await session.send("Target.getTargetInfo"); await session.detach()
                if target_id and ((info.get("targetInfo") or {}).get("targetId") == target_id): page=current; break
            except Exception:
                continue
        if page is None and wanted:
            pages=[x for x in context.pages if x.url.startswith(wanted)]
            if pages: page=pages[-1]
        if page is None:
            return {"status":"E2_DIAGNOSED","evidence_level":"E2","result":"target_unavailable","marker_found":False,"retry_allowed":False}
        await page.wait_for_timeout(500)
        view=await visible_page_state(page); classification=classify_user_view_state(view)
        surface=await discover_response_surface_from_marker(page,marker)
        if surface.get("status") == "E2_VERIFIED":
            recovered={**existing,"status":"E2_VERIFIED","response_verified":True,"response_surface":surface,"retry_allowed":False,"diagnosis":{"status":"RECOVERED_DELAYED_RESPONSE","visual_state":classification}}
            return {"status":"E2_RECOVERED","evidence_level":"E2","marker_found":True,"retry_allowed":False,"qualification":recovered,"visual_state":classification}
        meaningful=meaningful_commitment_requests(list(existing.get("network_endpoints") or []))
        return {"status":"E2_DIAGNOSED","evidence_level":"E2","result":"marker_not_present_in_current_dom","marker_found":False,"retry_allowed":False,"visual_state":classification,"response_surface":surface,"meaningful_commitment_requests":meaningful[-12:]}
    finally:
        await pw.stop()


def diagnose_committed_qualification_sync(cdp_url: str, record: dict[str, Any]) -> dict[str, Any]:
    return asyncio.run(diagnose_committed_qualification(cdp_url, record))

async def _refine_adapter_response_surface(cdp_url: str, adapter: dict[str, Any], marker: str) -> dict[str, Any]:
    from playwright.async_api import async_playwright
    origin = str(adapter.get("origin") or "").strip()
    pw = await async_playwright().start()
    try:
        browser = await pw.chromium.connect_over_cdp(cdp_url)
        if not browser.contexts:
            return {"status":"blocked","reason":"browser_context_missing"}
        pages = [p for p in browser.contexts[0].pages if origin and p.url.startswith(origin)]
        for page in reversed(pages):
            surface = await discover_response_surface_from_marker(page, marker)
            if surface.get("status") == "E2_VERIFIED":
                return surface
        return {"status":"blocked","reason":"marker_surface_unresolved"}
    finally:
        await pw.stop()


async def refine_adapter_from_existing_conformance(cdp_url: str, record: dict[str, Any]) -> dict[str, Any]:
    conformance = record.get("adapter_conformance") or {}
    adapter = record.get("adapter_candidate") or {}
    marker = str(conformance.get("expected_marker") or "").strip()
    if conformance.get("status") not in {"E2_REFINEMENT_REQUIRED", "E2_FAILED_AFTER_COMMIT"} or not marker:
        return {"status":"blocked","reason":"refinable_conformance_evidence_missing"}
    if marker not in str(conformance.get("response_text") or ""):
        return {"status":"blocked","reason":"marker_not_present_in_committed_response"}
    refined = await _refine_adapter_response_surface(cdp_url, adapter, marker)
    if refined.get("status") != "E2_VERIFIED":
        return refined
    adapter.setdefault("transport", {})["response"] = {
        "selector": refined.get("selector"),
        "strategy": refined.get("strategy"),
        "evidence_level": "E2",
    }
    record["adapter_candidate"] = adapter
    conformance["refined_response_surface"] = refined
    record["adapter_conformance"] = conformance
    technical = record.setdefault("technical_candidate", {})
    technical["workflow_state"] = "ADAPTER_CONFORMANCE_RETEST_REQUIRED"
    technical["next_required"] = "independent_adapter_conformance_retest"
    technical["user_action_required"] = False
    return {"status":"REFINED_FROM_EXISTING_EVIDENCE","response_surface":refined,"replay_performed":False}


def refine_adapter_from_existing_conformance_sync(cdp_url: str, record: dict[str, Any]) -> dict[str, Any]:
    return asyncio.run(refine_adapter_from_existing_conformance(cdp_url, record))


async def qualify_materialized_adapter(cdp_url: str, record: dict[str, Any], timeout_seconds: float = 60.0) -> dict[str, Any]:
    adapter = record.get("adapter_candidate") or {}
    if adapter.get("status") != "GENERATED_UNCERTIFIED":
        return {"status":"blocked","reason":"adapter_candidate_missing"}
    existing = record.get("adapter_conformance") or {}
    if existing.get("status") == "E2_VERIFIED":
        return {**existing,"reused_evidence":True}
    from adapters.discovered_web_provider import create_discovered_web_provider
    import secrets
    provider_id = str(adapter.get("provider_id") or record.get("candidate_id") or "").strip()
    home_url = str(adapter.get("home_url") or "").strip()
    if not provider_id or not home_url:
        return {"status":"blocked","reason":"adapter_identity_missing"}
    provider = create_discovered_web_provider(provider_id, cdp_url=cdp_url, home_url=home_url, adapter_candidate=adapter, timeout_seconds=timeout_seconds)
    marker = f"HWG_DISCOVERED_ADAPTER_E2_{secrets.randbelow(9000)+1000}"
    try:
        from core.providers import ChatCompletionRequest
        response = await provider.chat_completion(ChatCompletionRequest(model=provider_id, messages=[{"role":"user","content":f"Reply exactly: {marker}"}]))
        text = str(response.choices[0].message.content or "").strip()
        passed = text == marker
        result = {
            "status":"E2_VERIFIED" if passed else "E2_FAILED_AFTER_COMMIT",
            "evidence_level":"E2", "submitted":True, "retry_allowed":False,
            "expected_marker":marker, "response_text":text[:500], "response_verified":passed,
            "provider_meta":response.provider_meta or {},
        }
        if not passed and marker in text:
            refined = await _refine_adapter_response_surface(cdp_url, adapter, marker)
            if refined.get("status") == "E2_VERIFIED":
                result["status"] = "E2_REFINEMENT_REQUIRED"
                result["response_marker_present"] = True
                result["refined_response_surface"] = refined
                adapter.setdefault("transport", {})["response"] = {
                    "selector": refined.get("selector"),
                    "strategy": refined.get("strategy"),
                    "evidence_level": "E2",
                }
                record["adapter_candidate"] = adapter
    except Exception as exc:
        result = {"status":"E2_FAILED_OR_BLOCKED","evidence_level":"E2","error":type(exc).__name__,"message":str(exc)[:500]}
    finally:
        await provider.close()
    previous_conformance = record.get("adapter_conformance") or {}
    if previous_conformance:
        history = record.setdefault("adapter_conformance_history", [])
        fingerprint = (previous_conformance.get("status"), previous_conformance.get("expected_marker"), previous_conformance.get("response_text"))
        if not any((x.get("status"), x.get("expected_marker"), x.get("response_text")) == fingerprint for x in history):
            history.append(dict(previous_conformance))
    record["adapter_conformance"] = result
    technical = record.setdefault("technical_candidate", {})
    if result.get("status") == "E2_VERIFIED":
        technical["workflow_state"] = "ADAPTER_CONFORMANCE_VERIFIED"
        technical["next_required"] = "materialize_adapter_profile"
        technical["user_action_required"] = False
    elif result.get("status") == "E2_REFINEMENT_REQUIRED":
        technical["workflow_state"] = "ADAPTER_CONFORMANCE_RETEST_REQUIRED"
        technical["next_required"] = "independent_adapter_conformance_retest"
        technical["user_action_required"] = False
    return result


def qualify_materialized_adapter_sync(cdp_url: str, record: dict[str, Any], timeout_seconds: float = 60.0) -> dict[str, Any]:
    return asyncio.run(qualify_materialized_adapter(cdp_url, record, timeout_seconds=timeout_seconds))


def materialize_adapter_profile(root: Path, record: dict[str, Any]) -> dict[str, Any]:
    conformance = record.get("adapter_conformance") or {}
    adapter = record.get("adapter_candidate") or {}
    if conformance.get("status") != "E2_VERIFIED" or adapter.get("status") != "GENERATED_UNCERTIFIED":
        return {"status":"blocked","reason":"adapter_conformance_e2_required"}
    provider_id = str(record.get("candidate_id") or adapter.get("provider_id") or "").strip()
    if not provider_id:
        return {"status":"blocked","reason":"provider_id_missing"}
    folder = root / "docs" / "profiles" / provider_id
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "adapter_candidate.v1.json"
    artifact = {
        "schema_version":SCHEMA_VERSION, "provider_id":provider_id,
        "status":"E2_CONFORMANT_CANDIDATE",
        "generated_at":datetime.now(timezone.utc).isoformat(),
        "adapter_candidate":adapter,
        "conformance":{"status":conformance.get("status"),"evidence_level":conformance.get("evidence_level"),"expected_marker":conformance.get("expected_marker"),"provider_meta":conformance.get("provider_meta") or {}},
        "source_candidate_id":record.get("candidate_id"),
    }
    path.write_text(json.dumps(artifact,ensure_ascii=False,indent=2),encoding="utf-8")
    record["materialized_adapter_profile"] = {"status":"E2_CONFORMANT_CANDIDATE","path":str(path),"schema_version":SCHEMA_VERSION}
    technical = record.setdefault("technical_candidate", {})
    technical["workflow_state"] = "ADAPTER_PROFILE_MATERIALIZED"
    technical["next_required"] = "register_disabled_provider_and_readiness"
    technical["user_action_required"] = False
    return record["materialized_adapter_profile"]


def load_candidate(root: Path, candidate_id: str) -> dict[str, Any]:
    path = candidate_path(root, candidate_id)
    if not path.exists():
        raise FileNotFoundError(candidate_id)
    return json.loads(path.read_text(encoding="utf-8"))


def persist_candidate(root: Path, record: dict[str, Any]) -> Path:
    path = candidate_path(root, str(record.get("candidate_id") or "candidate"))
    record["updated_at"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _safe_endpoint(url: str) -> str:
    try:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    except Exception:
        return ""

def save_candidate(root: Path, analysis: dict[str, Any], observation: dict[str, Any] | None = None) -> dict[str, Any]:
    candidate_id = analysis["suggested_provider_id"]
    path = candidate_path(root, candidate_id)
    previous = {}
    if path.exists():
        try:
            previous = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            previous = {}
    record = {
        "schema_version": SCHEMA_VERSION,
        "candidate_id": candidate_id,
        "created_at": previous.get("created_at") or datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "state": "OBSERVED" if observation else "ANALYZED",
        "analysis": analysis,
        "observation": observation,
        "technical_candidate": synthesize_technical_candidate(analysis, observation),
        "qualification_history": list(previous.get("qualification_history") or []),
    }
    prior = previous.get("submit_qualification") or {}
    if prior:
        history = record["qualification_history"]
        fingerprint = (prior.get("status"), prior.get("target_id"), prior.get("submit_selector"), prior.get("expected_marker"))
        if not any((x.get("status"), x.get("target_id"), x.get("submit_selector"), x.get("expected_marker")) == fingerprint for x in history):
            history.append(prior)
        selectors = {str(x.get("selector") or "") for x in (record["technical_candidate"].get("submit_candidates") or [])}
        same_target = str(prior.get("target_id") or "") == str((observation or {}).get("target_id") or "")
        same_selector = str(prior.get("submit_selector") or "") in selectors
        nonretryable_commit = bool(prior.get("submitted")) and prior.get("retry_allowed") is False
        if nonretryable_commit or (prior.get("status") == "E2_VERIFIED" and same_target and same_selector):
            apply_submit_qualification(record, prior)
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"candidate": record, "record": str(path)}


def observe_url_sync(url: str, cdp_url: str, preferred_target_id: str | None = None, candidate_id: str | None = None, timeout_seconds: float = 60.0) -> dict[str, Any]:
    async def _bounded_observation():
        return await asyncio.wait_for(
            observe_url(url, cdp_url, preferred_target_id=preferred_target_id, candidate_id=candidate_id),
            timeout=float(timeout_seconds),
        )
    return asyncio.run(_bounded_observation())
