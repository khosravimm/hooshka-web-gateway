"""Profile-independent blind discovery and authentication/user-interaction classification."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from urllib.parse import urlparse
import re

PROVIDER_HOST_HINTS = {
    "chatgpt.com": "chatgpt-web",
    "chat.openai.com": "chatgpt-web",
    "chat.deepseek.com": "deepseek-web",
    "chat.qwen.ai": "qwen-web",
    "qwen.ai": "qwen-web",
    "chat.z.ai": "zai-web",
    "z.ai": "zai-web",
}

LOGIN_RE = re.compile(r"^(log ?in|sign ?in|continue with|ورود)$", re.I)
INTERACTION_RE = re.compile(r"captcha|verify (you are|your identity)|human verification|security check|challenge|consent", re.I)
SAFE_ACCESS_ENDPOINT_RE = re.compile(r"(?:^|/)(?:userinfo|session|quota(?:-usage)?|plan-quota|me)(?:$|[/?-])", re.I)
AUTH_REQUIRED_MESSAGE_RE = re.compile(r"login expired|session expired|not logged in|unauthori[sz]ed|authentication required|login required|sign in required|please log ?in", re.I)

@dataclass
class BlindIdentity:
    provider_id: str | None
    confidence: str
    evidence: list[str]

@dataclass
class AuthState:
    state: str
    confidence: str
    evidence: list[str]
    user_interaction: str | None = None
    block_reason: str | None = None
def identify_provider(page_url: str, title: str = "") -> BlindIdentity:
    host = (urlparse(page_url).hostname or "").lower()
    evidence=[]
    for hint, pid in PROVIDER_HOST_HINTS.items():
        if host == hint or host.endswith('.'+hint):
            evidence.append(f"host:{host}")
            return BlindIdentity(pid, "high", evidence)
    t=(title or '').lower()
    for token,pid in (("chatgpt","chatgpt-web"),("deepseek","deepseek-web"),("qwen","qwen-web"),("z.ai","zai-web")):
        if token in t:
            evidence.append(f"title:{title[:120]}")
            return BlindIdentity(pid,"medium",evidence)
    return BlindIdentity(None,"low",[f"host:{host or 'unknown'}"])


def classify_auth_snapshot(snapshot: dict) -> AuthState:
    evidence=[]
    if snapshot.get('provider_restriction'):
        evidence.append('provider_restriction_visible')
        return AuthState('BLOCKED','high',evidence,None,str(snapshot.get('provider_restriction')))
    if snapshot.get('challenge_visible'):
        evidence.append('challenge_surface_visible')
        return AuthState('USER_INTERACTION_REQUIRED','high',evidence,'challenge_or_verification')
    if snapshot.get('password_input') or snapshot.get('email_input') or snapshot.get('credential_input'):
        evidence.append('credential_input_visible')
        return AuthState('LOGIN_REQUIRED','high',evidence,'login')
    if snapshot.get('login_control') and not snapshot.get('composer'):
        evidence.append('login_control_without_composer')
        return AuthState('LOGIN_REQUIRED','high',evidence,'login')
    if snapshot.get('login_control') and snapshot.get('composer'):
        evidence.extend(['login_control_visible','composer_visible'])
        return AuthState('UNKNOWN','medium',evidence,None)
    if snapshot.get('composer') and snapshot.get('account_identity_visible'):
        evidence.extend(['composer_visible','account_identity_visible'])
        return AuthState('AUTHENTICATED','high',evidence,None)
    if snapshot.get('composer'):
        evidence.append('composer_visible_without_strong_auth_evidence')
        return AuthState('UNKNOWN','medium',evidence,'login')
    return AuthState('UNKNOWN','low',['no_strong_auth_signal'],None)
AUTH_SNAPSHOT_JS = r"""() => {
  const visible = e => { const r=e.getBoundingClientRect(); return !!(r.width||r.height); };
  const composer = [...document.querySelectorAll('textarea,[contenteditable=true][role=textbox],[contenteditable=true]')].find(visible);
  const pass = [...document.querySelectorAll('input[type=password]')].find(visible);
  const email = [...document.querySelectorAll('input[type=email],input[autocomplete=username],input[name*=email i]')].find(visible);
  const credentialLike = [...document.querySelectorAll('input')].filter(visible).find(e => /(?:phone|mobile|email|e-mail|password|passcode|username|شماره|ایمیل|رمز)/i.test((e.getAttribute('placeholder')||'')+' '+(e.getAttribute('name')||'')+' '+(e.getAttribute('aria-label')||'')));
  const controls = [...document.querySelectorAll('button,[role=button],a')].filter(visible).slice(0,300);
  const labels = controls.map(e => ((e.innerText||e.getAttribute('aria-label')||e.getAttribute('title')||'').trim())).filter(Boolean);
  const login = labels.find(x => /^(log ?in|sign ?in|continue with|ورود)$/i.test(x));
  const frames = [...document.querySelectorAll('iframe')].filter(visible).map(f => (f.src||'')+' '+(f.title||'')).join(' ');
  const challengeNodes = [...document.querySelectorAll('[id*=captcha i],[class*=captcha i],[data-testid*=captcha i],[aria-label*=captcha i],[id*=challenge i],[class*=challenge i],[role=dialog]')].filter(visible);
  const structuralText = challengeNodes.map(e => ((e.getAttribute('aria-label')||'')+' '+(e.innerText||'')).slice(0,500)).join(' ');
  const challenge = /captcha|verify you are|human verification|security check|challenge/i.test(frames+' '+structuralText);
  const bodyText = (document.body?.innerText||'').trim().replace(/\s+/g,' ').slice(0,12000);
  const accountIdentityVisible = /[A-Z0-9._%+-]{1,24}\*{2,}[A-Z0-9._%+-]*@[A-Z0-9.-]+\.[A-Z]{2,}/i.test(bodyText);
  let providerRestriction = '';
  if (!composer && bodyText.length < 600 && /not available in (your )?(region|country)|service unavailable in (your )?(region|country)/i.test(bodyText)) {
    providerRestriction = 'region_restriction';
  }
  return {composer:!!composer,password_input:!!pass,email_input:!!email,credential_input:!!credentialLike,login_control:login||'',account_identity_visible:accountIdentityVisible,challenge_visible:challenge,provider_restriction:providerRestriction};
}"""

def classify_access_semantic_observations(rows: list[dict]) -> AuthState:
    evidence=[]
    for row in rows or []:
        endpoint=str(row.get('endpoint') or '')
        status=int(row.get('http_status') or 0)
        code=row.get('code')
        message=str(row.get('message') or '')[:160]
        if status in {401,403} or AUTH_REQUIRED_MESSAGE_RE.search(message):
            evidence.append(f"endpoint:{endpoint}")
            if status:
                evidence.append(f"http_status:{status}")
            if code is not None:
                evidence.append(f"code:{code}")
            if message:
                evidence.append(f"message:{message}")
            return AuthState('LOGIN_REQUIRED','high',evidence,'login')
    for row in rows or []:
        endpoint=str(row.get('endpoint') or '')
        status=int(row.get('http_status') or 0)
        if 200 <= status < 300 and re.search(r'(?:^|/)(?:userinfo|session|me)(?:$|[/?-])', endpoint, re.I):
            return AuthState('ACCESS_AVAILABLE','medium',[f'endpoint:{endpoint}',f'http_status:{status}'],None)
    return AuthState('UNKNOWN','low',['no_auth_failure_semantics'],None)


async def probe_observed_access_semantics(page, candidate_endpoints: list[dict]) -> dict:
    paths=[]
    for item in candidate_endpoints or []:
        path=str(item.get('path') or '').strip()
        if path and path.startswith('/') and SAFE_ACCESS_ENDPOINT_RE.search(path) and path not in paths:
            paths.append(path)
        if len(paths) >= 4:
            break
    if not paths:
        return asdict(AuthState('UNKNOWN','low',['no_safe_access_endpoint_observed'],None))
    rows=await page.evaluate(r"""async (paths)=>{
      const out=[];
      for(const endpoint of paths){
        try{
          const r=await fetch(endpoint,{method:'GET',credentials:'include',cache:'no-store'});
          let payload=null; try{ payload=await r.json(); }catch(_){}
          out.push({endpoint,http_status:r.status,code:payload&&payload.code!==undefined?payload.code:null,
            status:payload&&payload.status!==undefined?String(payload.status).slice(0,80):'',
            message:payload?String(payload.message||payload.msg||payload.error||'').slice(0,160):''});
        }catch(e){ out.push({endpoint,error:String(e).slice(0,120)}); }
      }
      return out;
    }""", paths)
    state=classify_access_semantic_observations(rows if isinstance(rows,list) else [])
    result=asdict(state)
    result['observations']=rows if isinstance(rows,list) else []
    result['probe_kind']='same_origin_observed_get_semantics'
    return result


async def blind_discover_page(page, discover_page_fn):
    identity=identify_provider(page.url, await page.title())
    auth_raw=await page.evaluate(AUTH_SNAPSHOT_JS)
    auth=classify_auth_snapshot(auth_raw)
    report=await discover_page_fn(page, identity.provider_id or 'unknown-webchat')
    return {
        'identity': asdict(identity),
        'auth': asdict(auth),
        'page_url': page.url,
        'title': await page.title(),
        'frontend': report.frontend,
        'backend': report.backend,
        'capabilities': report.capabilities,
    }


def compare_blind_to_known(blind: dict, known: dict) -> dict:
    blind_kinds={c.get('kind') for c in (blind.get('frontend') or {}).get('controls',[])}
    known_kinds={c.get('kind') for c in (known.get('frontend') or {}).get('controls',[])}
    blind_eps={e.get('path') for e in (blind.get('backend') or {}).get('candidate_endpoints',[])}
    known_eps={e.get('path') for e in (known.get('backend') or {}).get('candidate_endpoints',[])}
    return {
        'controls': {'match':sorted(blind_kinds & known_kinds), 'missed':sorted(known_kinds-blind_kinds), 'new':sorted(blind_kinds-known_kinds)},
        'endpoints': {'match':sorted(blind_eps & known_eps), 'missed':sorted(known_eps-blind_eps), 'new':sorted(blind_eps-known_eps)},
    }


def matching_provider_pages(pages, home_url: str):
    """Return only pages whose host matches the provider home host.

    Shared CDP runtimes must never fall back to another provider's page;
    absence of a matching page is evidence of no_provider_page.
    """
    host = (urlparse(home_url).hostname or "").lower()
    if not host:
        return list(pages)
    return [p for p in pages if host == (urlparse(getattr(p, "url", "") or "").hostname or "").lower()]


async def probe_auth_cdp(cdp_url: str, home_url: str) -> dict:
    """Classify access/auth state from an owned live browser without prior provider profile knowledge."""
    from playwright.async_api import async_playwright
    host = (urlparse(home_url).hostname or "").lower()
    async with async_playwright() as pw:
        browser = await pw.chromium.connect_over_cdp(cdp_url, timeout=15000)
        if not browser.contexts:
            return asdict(AuthState('UNKNOWN','low',['no_browser_context'],None))
        pages = [p for c in browser.contexts for p in c.pages]
        pages = matching_provider_pages(pages, home_url)
        if not pages:
            return asdict(AuthState('UNKNOWN','low',['no_provider_page'],None))
        states=[]
        for page in pages[:5]:
            raw = await page.evaluate(AUTH_SNAPSHOT_JS)
            state = classify_auth_snapshot(raw)
            states.append((state, page.url))
        priority = {'BLOCKED':5,'USER_INTERACTION_REQUIRED':4,'LOGIN_REQUIRED':3,'AUTHENTICATED':2,'UNKNOWN':1}
        state, page_url = sorted(states, key=lambda x: priority.get(x[0].state,0), reverse=True)[0]
        result = asdict(state)
        result['page_url'] = page_url
        return result
