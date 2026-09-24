"""WebChat discovery engine: frontend + backend capability discovery.

Covers NG-DISC-001..005 (research-first, evidence ladder, drift detection):
- FRONTEND (read-only DOM): feature controls via core/control_discovery
  (thinking/search/model/upload/send/stop) + composer detection.
- BACKEND (read-only runtime signals): observed XHR/fetch endpoints (via
  Performance API), streaming transports (SSE/WebSocket URL patterns),
  storage namespaces (KEY NAMES ONLY — never values/secrets), client-side
  config flags (key names only).
- EVIDENCE LADDER: every property carries evidence type + confidence.
  E0 static < E1 observed < E2 live-tested (promotion only via e2 run).
- DRIFT: new reports are diffed against the stored profile; changes become
  explicit drift entries, never silent patches.
- NEW WEBCHATS: run against any CDP + home host; emits a draft provider
  profile usable for onboarding (see scripts/discover_provider.py).

No new dependencies. Never submits prompts, never clicks state-changing
controls, never reads secret values.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from core.control_discovery import classify, ENUMERATE_JS
from core.media_qualification import observe_file_upload_surface

ENGINE_VERSION = "1.1.0"
PROFILE_ROOT = Path(__file__).resolve().parents[1] / "docs" / "profiles"


@dataclass
class Evidence:
    type: str  # E0|E1|E2
    confidence: str  # low|medium|high
    source: str
    detail: str = ""


@dataclass
class Capability:
    name: str
    supported: bool
    evidence: Evidence
    meta: dict = field(default_factory=dict)


@dataclass
class DiscoveryReport:
    provider_id: str
    page_url: str
    engine_version: str
    discovered_at: str
    frontend: dict
    backend: dict
    capabilities: list[dict]
    drift: list[dict]


ENDPOINT_RE = re.compile(r"api|v\d|graphql|trpc|stream|sse|socket|completion|conversation|message|chat|invoke|query", re.I)
STATIC_ASSET_RE = re.compile(r"\.(?:js|mjs|css|svg|png|jpe?g|gif|webp|ico|woff2?|ttf|map)(?:$|\?)", re.I)
WS_RE = re.compile(r"wss?://[^\s\"']+|/socket\.?io|/ws\b|/websocket|eventsource|text/event-stream", re.I)
SECRET_KEY_RE = re.compile(r"token|secret|password|cookie|auth|session|credential|api.?key", re.I)


def _host(url: str) -> str:
    try:
        return urlparse(url).hostname or ""
    except Exception:
        return ""


def analyze_backend(signals: dict, home_host: str) -> dict:
    """Classify backend signals into endpoint/transport/storage findings (pure)."""
    endpoints: dict[str, dict] = {}
    for url in signals.get("resource_urls", []) or []:
        host = _host(url)
        if not url.startswith("http") or (home_host and host != home_host
                                          and not host.endswith("." + home_host)):
            continue
        parsed = urlparse(url)
        haystack = (parsed.path or "/") + ("?" + parsed.query if parsed.query else "")
        if STATIC_ASSET_RE.search(haystack):
            continue
        if ENDPOINT_RE.search(haystack):
            path = parsed.path or "/"
            entry = endpoints.setdefault(path, {"path": path, "hits": 0, "methods": []})
            entry["hits"] += 1
    transports = sorted({m for m in (signals.get("stream_hints") or []) if WS_RE.search(m or "")})
    storage_names = [k for k in (signals.get("storage_keys") or [])
                     if k and not SECRET_KEY_RE.search(k)][:50]
    secret_like = sum(1 for k in (signals.get("storage_keys") or []) if k and SECRET_KEY_RE.search(k))
    return {
        "candidate_endpoints": sorted(endpoints.values(), key=lambda e: -e["hits"])[:30],
        "stream_transports": transports,
        "storage_namespaces": storage_names,
        "secret_like_key_count": secret_like,  # count only, names withheld
        "config_flags": (signals.get("config_flags") or [])[:50],
    }


def build_capabilities(frontend: dict, backend: dict) -> list[Capability]:
    """Derive capability claims with evidence (pure)."""
    controls = {(c.get("kind"), c.get("confidence")) for c in frontend.get("controls", [])}
    has = lambda k: any(kind == k for kind, _ in controls)
    conf = lambda k: next((c for kk, c in controls if kk == k), "medium")
    composer = bool(frontend.get("composer"))
    caps = [
        Capability("chat", composer,
                   Evidence("E1" if composer else "E0",
                            "high" if composer else "low",
                            "composer observed" if composer else "composer not observed"),
                   {"composer": frontend.get("composer"), "send_control": has("send")}),
        Capability("model_selection", has("model_selector"),
                   Evidence("E1" if has("model_selector") else "E0",
                            conf("model_selector") if has("model_selector") else "low",
                            "model selector control")),
        Capability("thinking_control", has("thinking_toggle"),
                   Evidence("E1" if has("thinking_toggle") else "E0",
                            conf("thinking_toggle") if has("thinking_toggle") else "low",
                            "thinking toggle control")),
        Capability("web_search", has("search_toggle"),
                   Evidence("E1" if has("search_toggle") else "E0",
                            conf("search_toggle") if has("search_toggle") else "low",
                            "search toggle control")),
        Capability("file_upload", bool((frontend.get("upload_surface") or {}).get("input_present")) or has("file_upload"),
                   Evidence("E1" if (bool((frontend.get("upload_surface") or {}).get("input_present")) or has("file_upload")) else "E0",
                            "high" if (frontend.get("upload_surface") or {}).get("input_present") else "medium",
                            "file input observed" if (frontend.get("upload_surface") or {}).get("input_present") else "upload control"),
                   {"surface": frontend.get("upload_surface") or {}}),
        Capability("streaming", bool(backend.get("stream_transports")),
                   Evidence("E1" if backend.get("stream_transports") else "E0",
                            "medium" if backend.get("stream_transports") else "low",
                            "transport hints", {"hints": backend.get("stream_transports", [])})),
        Capability("backend_api", bool(backend.get("candidate_endpoints")),
                   Evidence("E1" if backend.get("candidate_endpoints") else "E0",
                            "medium" if backend.get("candidate_endpoints") else "low",
                            "observed endpoints",
                            {"count": len(backend.get("candidate_endpoints", []))})),
    ]
    return caps


def diff_drift(old: dict, new: dict) -> list[dict]:
    """Diff stored profile vs fresh findings into explicit drift entries (pure)."""
    drift = []
    old_ctls = {c.get("selector"): c.get("kind") for c in (old.get("controls") or [])}
    new_ctls = {c.get("selector"): c.get("kind") for c in (new.get("controls") or [])}
    for sel, kind in new_ctls.items():
        if sel not in old_ctls:
            drift.append({"type": "control_added", "kind": kind, "selector": sel})
    for sel, kind in old_ctls.items():
        if sel not in new_ctls:
            drift.append({"type": "control_missing", "kind": kind, "selector": sel})
    old_eps = {e.get("path") for e in (old.get("candidate_endpoints") or [])}
    new_eps = {e.get("path") for e in (new.get("candidate_endpoints") or [])}
    for ep in sorted(new_eps - old_eps):
        drift.append({"type": "endpoint_added", "path": ep})
    for ep in sorted(old_eps - new_eps):
        drift.append({"type": "endpoint_missing", "path": ep})
    old_up = old.get("upload_surface") or {}
    new_up = new.get("upload_surface") or {}
    old_classes = old_up.get("advertised_classes") or {}
    new_classes = new_up.get("advertised_classes") or {}
    for name in sorted(set(old_classes) | set(new_classes)):
        if bool(old_classes.get(name)) != bool(new_classes.get(name)):
            drift.append({"type": "upload_class_changed", "class": name, "old": bool(old_classes.get(name)), "new": bool(new_classes.get(name))})
    if bool(old_up.get("input_present")) != bool(new_up.get("input_present")):
        drift.append({"type":"upload_surface_changed","old":bool(old_up.get("input_present")),"new":bool(new_up.get("input_present"))})
    return drift


BACKEND_JS = r"""() => {
  const res = (performance.getEntriesByType('resource') || []).map(r => r.name).slice(0, 300);
  const html = document.documentElement.outerHTML.slice(0, 400000);
  const hints = new Set();
  const ws = html.match(/wss?:\/\/[^\\"'\s]+|\/socket\.?io[^\\"'\s]*|\/ws\b[^\\"'\s]*|text\/event-stream/gi) || [];
  ws.slice(0, 20).forEach(w => hints.add(w));
  let storageKeys = [];
  try { storageKeys = Object.keys(localStorage).slice(0, 100); } catch (e) {}
  let flags = [];
  try {
    for (const k of Object.keys(window)) {
      if (/^(NEXT_|NUXT_|__APP|APP_|FEATURE_|FLAG)/.test(k)) flags.push(k);
      if (flags.length >= 30) break;
    }
  } catch (e) {}
  return {resource_urls: res, stream_hints: [...hints],
          storage_keys: storageKeys, config_flags: flags};
}"""

FRONTEND_JS = r"""() => {
  const comp = document.querySelector('textarea, [contenteditable=true][role=textbox], [contenteditable=true]');
  const esc = (v) => String(v || '').replace(/\\/g, '\\\\').replace(/'/g, "\\'");
  let selector = null;
  if (comp) {
    const ephemeralId = (v) => /^f_[0-9a-f-]{20,}$/i.test(v||'') || /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i.test(v||'');
    const unique = (s) => { try { const nodes=document.querySelectorAll(s); return nodes.length===1 && nodes[0]===comp; } catch (_) { return false; } };
    const structural = (el) => {
      const parts=[]; let cur=el;
      for (let depth=0; cur && cur.nodeType===1 && depth<7; depth++, cur=cur.parentElement) {
        let part=cur.tagName.toLowerCase();
        if (cur.id && !ephemeralId(cur.id)) part='#'+CSS.escape(cur.id);
        else if (cur.parentElement) {
          const same=[...cur.parentElement.children].filter(x=>x.tagName===cur.tagName);
          if (same.length>1) part += `:nth-of-type(${same.indexOf(cur)+1})`;
        }
        parts.unshift(part); const candidate=parts.join(' > ');
        if (unique(candidate)) return candidate;
        if (part.startsWith('#')) break;
      }
      return null;
    };
    const tag=comp.tagName.toLowerCase();
    const aria = comp.getAttribute('aria-label');
    const placeholder = comp.getAttribute('placeholder');
    const name = comp.getAttribute('name');
    const role = comp.getAttribute('role');
    const candidates=[];
    if (comp.id && !ephemeralId(comp.id)) candidates.push('#' + CSS.escape(comp.id));
    if (aria) candidates.push(`${tag}[aria-label='${esc(aria)}']`);
    if (placeholder) candidates.push(`${tag}[placeholder='${esc(placeholder)}']`);
    if (name) candidates.push(`${tag}[name='${esc(name)}']`);
    if (role) candidates.push(`${tag}[role='${esc(role)}']`);
    if (comp.getAttribute('contenteditable')==='true') candidates.push(`${tag}[contenteditable='true']`);
    selector = candidates.find(unique) || structural(comp);
  }
  const assistantSelectors = [
    "[data-message-author-role='assistant']",
    "[data-markdown-text-style='assistant-message']",
    "[data-content-search-unit-key*='assistant']"
  ];
  let assistantNodes = [];
  for (const s of assistantSelectors) assistantNodes.push(...document.querySelectorAll(s));
  assistantNodes = [...new Set(assistantNodes)];
  const latest = assistantNodes.length ? assistantNodes[assistantNodes.length - 1] : null;
  const bodyText = document.body?.innerText || '';
  const responding = /chatgpt is responding|thinking|generating/i.test(bodyText.slice(-1500));
  return {
    composer: comp ? (comp.tagName + '#' + (comp.id || '')) : null,
    composer_selector: selector,
    assistant_surface: {
      count: assistantNodes.length,
      selectors: assistantSelectors,
      latest_text_length: latest ? String(latest.innerText || latest.textContent || '').trim().length : 0,
      responding_visible: responding
    }
  };
}"""


async def discover_page(page, provider_id: str) -> DiscoveryReport:
    """Full read-only discovery run on a live Playwright page."""
    url = page.url
    front_raw = await page.evaluate(FRONTEND_JS)
    elements = await page.evaluate(ENUMERATE_JS)
    backend_raw = await page.evaluate(BACKEND_JS)
    controls = classify(elements)
    upload_surface = await observe_file_upload_surface(page)
    frontend = {"composer": front_raw.get("composer"),
                "composer_selector": front_raw.get("composer_selector"),
                "assistant_surface": front_raw.get("assistant_surface") or {},
                "controls": [c.__dict__ for c in controls],
                "upload_surface": upload_surface}
    backend = analyze_backend(backend_raw, _host(url))
    caps = build_capabilities(frontend, backend)
    return DiscoveryReport(
        provider_id=provider_id, page_url=url, engine_version=ENGINE_VERSION,
        discovered_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        frontend=frontend, backend=backend,
        capabilities=[{"name": c.name, "supported": c.supported,
                       "evidence": asdict(c.evidence), "meta": c.meta} for c in caps],
        drift=[],
    )


def load_stored_profile(provider_id: str, root: Path | None = None) -> dict:
    root = root or PROFILE_ROOT
    d = root / provider_id
    if not d.exists():
        return {}
    files = sorted(d.glob("controls.v*.json"))
    if not files:
        return {}
    try:
        return json.loads(files[-1].read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_report(report: DiscoveryReport, root: Path | None = None) -> Path:
    root = root or PROFILE_ROOT
    d = root / report.provider_id
    d.mkdir(parents=True, exist_ok=True)
    old = load_stored_profile(report.provider_id, root)
    old_flat = {"controls": [], "candidate_endpoints": [], "upload_surface": {}}
    for f in sorted(d.glob("discovery.v*.json")):
        try:
            prev = json.loads(f.read_text(encoding="utf-8"))
            old_flat = {"controls": prev.get("frontend", {}).get("controls", []),
                        "candidate_endpoints": prev.get("backend", {}).get("candidate_endpoints", []),
                        "upload_surface": prev.get("frontend", {}).get("upload_surface", {})}
        except Exception:
            pass
    new_flat = {"controls": report.frontend.get("controls", []),
                "candidate_endpoints": report.backend.get("candidate_endpoints", []),
                "upload_surface": report.frontend.get("upload_surface", {})}
    report.drift = diff_drift(old_flat, new_flat)
    existing = sorted(d.glob("discovery.v*.json"))
    version = "1.0"
    if existing:
        try:
            major, minor = existing[-1].stem.split(".v")[1].split(".")
            version = f"{major}.{int(minor) + 1}"
        except Exception:
            pass
    path = d / f"discovery.v{version}.json"
    payload = {"profile_version": version, **report.__dict__}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
