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
    if snapshot.get('password_input') or snapshot.get('email_input'):
        evidence.append('credential_input_visible')
        return AuthState('LOGIN_REQUIRED','high',evidence,'login')
    if snapshot.get('login_control') and not snapshot.get('composer'):
        evidence.append('login_control_without_composer')
        return AuthState('LOGIN_REQUIRED','high',evidence,'login')
    if snapshot.get('composer'):
        evidence.append('composer_visible')
        return AuthState('AUTHENTICATED','medium',evidence,None)
    return AuthState('UNKNOWN','low',['no_strong_auth_signal'],None)
AUTH_SNAPSHOT_JS = r"""() => {
  const visible = e => { const r=e.getBoundingClientRect(); return !!(r.width||r.height); };
  const composer = [...document.querySelectorAll('textarea,[contenteditable=true][role=textbox],[contenteditable=true]')].find(visible);
  const pass = [...document.querySelectorAll('input[type=password]')].find(visible);
  const email = [...document.querySelectorAll('input[type=email],input[autocomplete=username],input[name*=email i]')].find(visible);
  const controls = [...document.querySelectorAll('button,[role=button],a')].filter(visible).slice(0,300);
  const labels = controls.map(e => ((e.innerText||e.getAttribute('aria-label')||e.getAttribute('title')||'').trim())).filter(Boolean);
  const login = labels.find(x => /^(log ?in|sign ?in|continue with|ورود)$/i.test(x));
  const frames = [...document.querySelectorAll('iframe')].filter(visible).map(f => (f.src||'')+' '+(f.title||'')).join(' ');
  const challengeNodes = [...document.querySelectorAll('[id*=captcha i],[class*=captcha i],[data-testid*=captcha i],[aria-label*=captcha i],[id*=challenge i],[class*=challenge i],[role=dialog]')].filter(visible);
  const structuralText = challengeNodes.map(e => ((e.getAttribute('aria-label')||'')+' '+(e.innerText||'')).slice(0,500)).join(' ');
  const challenge = /captcha|verify you are|human verification|security check|challenge/i.test(frames+' '+structuralText);
  const bodyText = (document.body?.innerText||'').trim().replace(/\s+/g,' ').slice(0,1500);
  let providerRestriction = '';
  if (!composer && bodyText.length < 600 && /not available in (your )?(region|country)|service unavailable in (your )?(region|country)/i.test(bodyText)) {
    providerRestriction = 'region_restriction';
  }
  return {composer:!!composer,password_input:!!pass,email_input:!!email,login_control:login||'',challenge_visible:challenge,provider_restriction:providerRestriction};
}"""

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


async def probe_auth_cdp(cdp_url: str, home_url: str) -> dict:
    """Classify access/auth state from an owned live browser without prior provider profile knowledge."""
    from playwright.async_api import async_playwright
    host = (urlparse(home_url).hostname or "").lower()
    async with async_playwright() as pw:
        browser = await pw.chromium.connect_over_cdp(cdp_url, timeout=15000)
        if not browser.contexts:
            return asdict(AuthState('UNKNOWN','low',['no_browser_context'],None))
        pages = [p for c in browser.contexts for p in c.pages]
        pages = [p for p in pages if host and host == (urlparse(p.url).hostname or '').lower()] or pages
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
