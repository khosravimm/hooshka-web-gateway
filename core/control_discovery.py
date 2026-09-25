"""Feature-control discovery engine for Web Chat providers.

Read-only by default: enumerates interactive elements on a live provider page,
classifies feature controls (thinking toggle/level, search toggle, model
selector, upload, send/stop) and stores them in a versioned provider profile.
State-changing actions live in ``core/feature_controls.py`` and always
consume a discovered profile (never ad-hoc selectors).

Reuse: same config-driven provider map and read-only CDP pattern as
``tools/discover_webchat_stop_surfaces.py``. No new dependencies.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

PROFILE_VERSION = "1.0.0"


@dataclass
class Control:
    control_id: str
    kind: str  # thinking_toggle|thinking_level|search_toggle|model_selector|file_upload|send|stop|unknown
    selector: str  # preferred CSS locator
    text: str = ""
    state: dict = field(default_factory=dict)
    confidence: str = "medium"  # high|medium|low
    evidence: str = ""


# (kind, [(field, pattern, weight)])
PATTERNS: list[tuple[str, list[tuple[str, str, int]]]] = [
    ("thinking_toggle", [
        ("aria", r"deep.?think|thinking|reasoning", 3),
        ("title", r"deep.?think|thinking|reasoning", 3),
        ("testid", r"think|reasoning", 3),
        ("id", r"think|reasoning", 3),
        ("text", r"^deep.?think$|^thinking$|تفکر", 3),
        ("cls", r"think|reasoning", 1),
    ]),
    ("thinking_level", [
        ("aria", r"thinking (level|mode|strength)|reasoning (effort|level)", 3),
        ("text", r"\bmax\b|\bhigh\b|\bmedium\b|\blow\b|حداکثر|متوسط", 1),
    ]),
    ("search_toggle", [
        ("aria", r"web.?search|search( the)? web|جستجو", 3),
        ("title", r"web.?search|search( the)? web", 3),
        ("testid", r"\bsearch\b", 3),
        ("text", r"^web search$|^search$|جستجوی وب", 3),
    ]),
    ("model_selector", [
        ("aria", r"^model select$|select( a)? model|choose model|انتخاب مدل", 5),
        ("id", r"model[-_]?select[-_]?trigger|model.selector|modelselector", 5),
        ("testid", r"model.selector", 3),
        ("cls", r"modelSelector", 2),
        ("text", r"^(?!(?:grok\s+bot)$)(?:gpt|claude|gemini|deepseek|qwen|grok|llama|mistral|glm|kimi|minimax|perplexity|yi)(?:[ ._\-/A-Za-z0-9]{0,48})$", 3),
        ("role", r"^combobox$", 1),
        ("value", r"(?:gpt|claude|gemini|llama|mistral|qwen|deepseek|glm|model|مدل)|(?:[A-Za-z][A-Za-z0-9 ._-]{1,30}\d(?:\.\d+)?)", 2),
        ("parent", r"model|مدل", 2),
    ]),
    ("file_upload", [
        ("aria", r"attach|upload( file)?|add (file|attachment)|آپلود|پیوست|افزودن فایل|فایل یا ابزار", 3),
        ("title", r"attach|upload", 2),
        ("testid", r"attach|upload", 3),
    ]),
    ("send", [
        ("aria", r"^send( message| prompt)?$|ارسال", 3),
        ("testid", r"send|submit|composer.submit", 3),
    ]),
    ("stop", [
        ("aria", r"^stop( generating| streaming| answering| responding)?$", 3),
        ("testid", r"\bstop\b", 3),
    ]),
]


def _fallback_selector(el: dict) -> str:
    if el.get("selector"):
        return str(el["selector"])
    tokens = (el.get("cls") or "").split()[:3]
    base = el.get("tag", "button").lower()
    if tokens:
        return base + "." + ".".join(t.replace(":", "\\:") for t in tokens)
    return base


def classify(elements: list[dict]) -> list[Control]:
    """Classify raw element dicts into Controls (pure function, no browser)."""
    compiled = [(k, [(f, re.compile(p, re.I), w) for f, p, w in rules])
                for k, rules in PATTERNS]
    controls: list[Control] = []
    used: set[int] = set()
    for idx, el in enumerate(elements):
        best: tuple[str, int, int] | None = None  # (kind, score, strong_hits)
        for kind, rules in compiled:
            score, strong = 0, 0
            for fname, rx, weight in rules:
                if rx.search(el.get(fname) or ""):
                    score += weight
                    if weight >= 3:
                        strong += 1
            if score >= 3 and (best is None or score > best[1]):
                best = (kind, score, strong)
        if best is None:
            # Icon-only controls (no text/aria/testid/id) are surfaced as
            # unclassified candidates for interactive follow-up, not dropped.
            if idx not in used and not any(el.get(f) for f in ("text", "aria", "testid", "eid", "title")):
                used.add(idx)
                controls.append(Control(
                    control_id=f"unclassified-{len([c for c in controls if c.kind == 'unclassified']) + 1}",
                    kind="unclassified", selector=_fallback_selector(el),
                    text="", state={}, confidence="low",
                    evidence="icon-only clickable without labels; needs hover/menu probing",
                ))
            continue
        if idx in used:
            continue
        kind, score, strong = best
        used.add(idx)
        selector = (
            f"#{el['eid']}" if el.get("eid")
            else f"[data-testid='{el['testid']}']" if el.get("testid")
            else f"[aria-label='{el['aria']}']" if el.get("aria")
            else f"text={el.get('text', '')[:40]}"
        )
        state = {k: el[k] for k in ("pressed", "checked", "expanded", "disabled", "state") if el.get(k) is not None}
        controls.append(Control(
            control_id=f"{kind}-{len([c for c in controls if c.kind == kind]) + 1}",
            kind=kind, selector=selector, text=(el.get("text") or "")[:80],
            state=state,
            confidence="high" if strong >= 1 else "medium",
            evidence=f"matched {kind} (score={score})",
        ))
    return controls


ENUMERATE_JS = r"""() => {
  const cssSel = (e) => {
    const ephemeralId = v => /^f_[0-9a-f-]{20,}$/i.test(v||'') || /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i.test(v||'');
    if (e.id && !ephemeralId(e.id)) return '#' + CSS.escape(e.id);
    const tid=e.getAttribute('data-testid'); if (tid) return `[data-testid='${String(tid).replace(/'/g,"\\'")}']`;
    const aria=e.getAttribute('aria-label'); if (aria) return `[aria-label='${String(aria).replace(/'/g,"\\'")}']`;
    const role=e.getAttribute('role'); const name=e.getAttribute('name');
    if (role && name) return `${e.tagName.toLowerCase()}[role='${String(role).replace(/'/g,"\\'")}'][name='${String(name).replace(/'/g,"\\'")}']`;
    const parts=[]; let cur=e; let depth=0;
    while(cur && cur.nodeType===1 && cur!==document.body && depth<5){
      const tag=cur.tagName.toLowerCase(); const sib=[...cur.parentElement?.children||[]].filter(x=>x.tagName===cur.tagName);
      const n=sib.indexOf(cur)+1; parts.unshift(`${tag}:nth-of-type(${Math.max(1,n)})`); cur=cur.parentElement; depth++;
    }
    return parts.join(' > ');
  };
  const all = [...document.querySelectorAll('button, select, input[type=text], [role=button], [tabindex="0"], [role=switch], [role=checkbox], [role=combobox], [role=listbox], input[type=checkbox], [aria-pressed], [data-testid]')];
  const out = [];
  for (const e of all) {
    const r = e.getBoundingClientRect();
    if (r.width === 0 && r.height === 0) continue;
    const cls = e.className && e.className.baseVal !== undefined ? '' : String(e.className || '');
    out.push({
      tag: e.tagName,
      eid: e.id || '', testid: e.getAttribute('data-testid') || '',
      text: (e.innerText || '').trim().replace(/\s+/g, ' ').slice(0, 80),
      aria: (e.getAttribute('aria-label') || '').slice(0, 80),
      title: (e.getAttribute('title') || '').slice(0, 80),
      role: (e.getAttribute('role') || '').slice(0, 40),
      value: String(e.value || '').slice(0, 120),
      placeholder: (e.getAttribute('placeholder') || '').slice(0, 120),
      parent: ((e.parentElement?.innerText || e.parentElement?.textContent || '')).trim().replace(/\s+/g, ' ').slice(0, 160),
      selector: cssSel(e),
      rect: {x:Math.round(r.x), y:Math.round(r.y), w:Math.round(r.width), h:Math.round(r.height)},
      cls: cls.slice(0, 80),
      pressed: e.getAttribute('aria-pressed'), checked: e.getAttribute('aria-checked'),
      expanded: e.getAttribute('aria-expanded'),
      disabled: e.disabled === true ? true : null,
      state: e.getAttribute('data-state')
    });
    if (out.length >= 400) break;
  }
  return out;
}"""


async def discover_page_controls(page) -> list[Control]:
    """Run read-only enumeration on a live Playwright page and classify."""
    elements = await page.evaluate(ENUMERATE_JS)
    return classify(elements)


def save_controls_profile(provider_id: str, controls: list[Control],
                          page_url: str = "", root: Path | None = None) -> Path:
    """Write versioned controls profile under docs/profiles/<id>/."""
    from pathlib import Path as _P
    root = _P(root) if root else _P(__file__).resolve().parents[1]
    d = root / "docs" / "profiles" / provider_id
    d.mkdir(parents=True, exist_ok=True)
    existing = sorted(d.glob("controls.v*.json"))
    version = "1.0"
    # bump minor when a previous version exists
    if existing:
        last = existing[-1].stem  # controls.vX.Y
        try:
            major, minor = last.split(".v")[1].split(".")
            version = f"{major}.{int(minor) + 1}"
        except Exception:
            version = "1.0"
    payload = {
        "profile_version": version,
        "provider_id": provider_id,
        "discovered_at": datetime.now(timezone.utc).isoformat(),
        "page_url": page_url,
        "engine": "core/control_discovery",
        "controls": [asdict(c) for c in controls],
    }
    path = d / f"controls.v{version}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
