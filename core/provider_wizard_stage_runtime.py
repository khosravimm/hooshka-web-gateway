from __future__ import annotations

import asyncio
from dataclasses import asdict
from typing import Any

from core.visual_discovery import visible_page_state, classify_user_view_state
from core.discovery_engine import discover_page
from core.blind_discovery import probe_observed_access_semantics
from core.control_discovery import discover_page_controls
from core.model_surface_discovery import discover_model_surface


def classify_auth_transport_failure(snapshot: dict[str, Any]) -> dict[str, Any] | None:
    text = str(snapshot.get("visible_text") or "")
    visible_network_error = any(token in text.lower() for token in (
        "network request failed",
        "check your internet connection",
        "network error",
    ))
    recent = []
    attempted_sign_in = False
    auth_bootstrap_failed = False
    for row in snapshot.get("resources") or []:
        name = str(row.get("name") or "")
        if not any(token in name for token in (
            "identitytoolkit.googleapis.com",
            "www.googleapis.com/identitytoolkit",
            "/__/auth/",
            "firebase.googleapis.com/v1alpha/projects/-/apps/",
            "firebaseinstallations.googleapis.com/",
        )):
            continue
        age_ms = float(row.get("age_ms") or 10**9)
        transfer = int(row.get("transfer_size") or 0)
        status = row.get("response_status")
        if age_ms <= 900000 and transfer == 0 and status in (None, 0):
            if "accounts:signInWith" in name or "accounts:signUp" in name:
                attempted_sign_in = True
            if (
                "/__/auth/iframe" in name
                or "identitytoolkit.googleapis.com/v1/projects" in name
                or "firebase.googleapis.com/v1alpha/projects/-/apps/" in name
            ):
                auth_bootstrap_failed = True
            recent.append({
                "name": name.split("?", 1)[0],
                "age_ms": round(age_ms),
                "response_status": status,
                "transfer_size": transfer,
            })
    if not recent or not (visible_network_error or attempted_sign_in or auth_bootstrap_failed):
        return None
    return {
        "detected": True,
        "kind": "AUTH_PROVIDER_BROKEN",
        "reason": "auth_provider_transport_failure",
        "user_action_required": False,
        "evidence": recent[-6:],
    }


async def _detect_auth_transport_failure(page) -> dict[str, Any] | None:
    snapshot = await page.evaluate("""() => {
      const now=performance.now();
      const resources=performance.getEntriesByType('resource').map(x=>({
        name:x.name,
        response_status:(typeof x.responseStatus==='number' && x.responseStatus>0)?x.responseStatus:null,
        transfer_size:Number(x.transferSize||0),
        age_ms:Math.max(0,now-(Number(x.startTime||0)+Number(x.duration||0)))
      }));
      return {visible_text:(document.body?.innerText||'').slice(-12000),resources};
    }""")
    return classify_auth_transport_failure(snapshot)


async def _firebase_auth_preflight(page) -> dict[str, Any] | None:
    """Run a read-only Firebase Auth transport/config preflight from provider origin.

    The Firebase API key is discovered from already-loaded public auth resources and
    is never returned in evidence.  This is only a transport/config reachability
    check; it does not submit credentials or mutate account state.
    """
    probe = await page.evaluate("""async () => {
      const resources=performance.getEntriesByType('resource').map(x=>String(x.name||''));
      let apiKey='';
      for(const name of resources){
        if(!/identitytoolkit\.googleapis\.com|www\.googleapis\.com\/identitytoolkit|\/__\/auth\/iframe/i.test(name)) continue;
        try{
          const u=new URL(name);
          const k=u.searchParams.get('key') || u.searchParams.get('apiKey');
          if(k){ apiKey=k; break; }
        }catch(_e){}
      }
      if(!apiKey) return {detected:false};
      const endpoint='https://identitytoolkit.googleapis.com/v1/projects?key='+encodeURIComponent(apiKey);
      const timeout=new Promise((_,reject)=>setTimeout(()=>reject(new Error('preflight_timeout')),5000));
      try{
        const r=await Promise.race([fetch(endpoint,{method:'GET',mode:'cors',credentials:'omit'}),timeout]);
        let body='';
        try{ body=(await r.text()).slice(0,220); }catch(_e){}
        return {detected:true,ok:!!r.ok,status:Number(r.status||0),type:String(r.type||''),content_type:r.headers?.get?.('content-type')||'',body};
      }catch(e){
        return {detected:true,ok:false,status:0,error:String(e)};
      }
    }""")
    if not isinstance(probe, dict) or not probe.get("detected"):
        return None
    if probe.get("ok"):
        return None
    status = int(probe.get("status") or 0)
    return {
        "detected": True,
        "kind": "AUTH_PROVIDER_BROKEN",
        "reason": "firebase_auth_preflight_failed",
        "user_action_required": False,
        "evidence": [{
            "endpoint": "https://identitytoolkit.googleapis.com/v1/projects",
            "http_status": status or None,
            "error": str(probe.get("error") or "")[:180] or None,
            "content_type": str(probe.get("content_type") or "")[:120] or None,
        }],
    }


async def _page_for_target(context, target_id: str):
    for page in context.pages:
        try:
            sess = await context.new_cdp_session(page)
            info = await sess.send("Target.getTargetInfo")
            await sess.detach()
            if str((info.get("targetInfo") or {}).get("targetId") or "") == target_id:
                return page
        except Exception:
            continue
    return None


async def access_bootstrap(cdp_url: str, target_id: str, candidate_id: str) -> dict[str, Any]:
    from playwright.async_api import async_playwright
    pw = await async_playwright().start()
    try:
        browser = await pw.chromium.connect_over_cdp(cdp_url)
        context = browser.contexts[0]
        page = await _page_for_target(context, target_id)
        if page is None:
            return {"status":"blocked","stage_id":"S1","stage_state":"FAILED","reason":"target_not_found"}
        trace=[]; state={}; classification={"state":"unknown","evidence":"not_observed"}
        for attempt in range(1, 11):
            state = await visible_page_state(page)
            classification = classify_user_view_state(state)
            visual_now = str(classification.get("state") or "unknown")
            trace.append({"attempt":attempt,"state":visual_now,"evidence":classification.get("evidence")})
            if visual_now not in {"loading","interactive_not_ready","unknown","upload_busy"}:
                break
            await page.wait_for_timeout(900)
        access = {"state":"UNKNOWN","confidence":"low","evidence":["access_semantics_not_probed"]}
        visual = str(classification.get("state") or "unknown")
        composer_usable = bool(state.get("composer_present")) and bool(state.get("composer_enabled"))
        guest_candidate = visual == "auth_ambiguous" and composer_usable
        if visual in {"ready","login_required"} or (visual == "auth_ambiguous" and not guest_candidate):
            report = await discover_page(page, candidate_id)
            access = await probe_observed_access_semantics(page, (report.backend or {}).get("candidate_endpoints") or [])
        if guest_candidate and str(access.get("state") or "UNKNOWN").upper() == "UNKNOWN":
            access = {"state":"LOGIN_REQUIRED","confidence":"high","evidence":["guest_or_anonymous_composer_not_accepted","login_or_signup_control_visible"],"user_interaction":"login","block_reason":"authenticated_session_required"}
        access_state = str(access.get("state") or "UNKNOWN").upper()
        auth_failure = await _detect_auth_transport_failure(page)
        if not auth_failure and (
            visual in {"login_required", "auth_ambiguous"}
            or access_state in {"LOGIN_REQUIRED", "USER_INTERACTION_REQUIRED"}
        ):
            auth_failure = await _firebase_auth_preflight(page)
        if auth_failure:
            stage_state = "BLOCKED"
        elif visual in {"login_required","challenge"} or access_state in {"LOGIN_REQUIRED","USER_INTERACTION_REQUIRED"}:
            stage_state = "USER_GATE"
        elif access_state in {"ACCESS_AVAILABLE","AUTHENTICATED"} and visual in {"ready","auth_ambiguous"}:
            stage_state = "PASSED"
        else:
            stage_state = "USER_GATE"
        result={"status":"observed","stage_id":"S1","stage_state":stage_state,"target_id":target_id,"url":page.url,"title":await page.title(),"classification":classification,"access_semantics":access,"observation_trace":trace}
        if auth_failure:
            result.update({"status":"blocked","reason":auth_failure["reason"],"auth_failure":auth_failure,"user_action_required":False})
        return result
    finally:
        await pw.stop()


async def model_entitlement_discovery(cdp_url: str, target_id: str) -> dict[str, Any]:
    from playwright.async_api import async_playwright
    pw = await async_playwright().start()
    try:
        browser = await pw.chromium.connect_over_cdp(cdp_url)
        context = browser.contexts[0]
        page = await _page_for_target(context, target_id)
        if page is None:
            return {"status":"blocked","stage_id":"S2","stage_state":"FAILED","reason":"target_not_found"}
        state = await visible_page_state(page)
        classification = classify_user_view_state(state)
        visual=str(classification.get("state") or "unknown")
        if visual != "ready":
            return {"status":"blocked","stage_id":"S2","stage_state":"BLOCKED","classification":classification,"reason":"visual_preflight_not_ready"}
        controls = await discover_page_controls(page)
        surface = await discover_model_surface(page, [asdict(c) for c in controls])
        passed = surface.get("status") == "observed"
        return {"status":"observed" if passed else "incomplete","stage_id":"S2","stage_state":"PASSED" if passed else "INCOMPLETE","target_id":target_id,"classification":classification,"model_surface":surface}
    finally:
        await pw.stop()


def access_bootstrap_sync(cdp_url: str, target_id: str, candidate_id: str, timeout_seconds: float = 30.0) -> dict[str, Any]:
    async def run():
        return await asyncio.wait_for(access_bootstrap(cdp_url, target_id, candidate_id), timeout_seconds)
    return asyncio.run(run())


def model_entitlement_discovery_sync(cdp_url: str, target_id: str, timeout_seconds: float = 30.0) -> dict[str, Any]:
    async def run():
        return await asyncio.wait_for(model_entitlement_discovery(cdp_url, target_id), timeout_seconds)
    return asyncio.run(run())
