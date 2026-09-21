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
        ("text", r"^deep.?think$|^thinking$|تفکر", 2),
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
        ("text", r"^web search$|^search$|جستجوی وب", 2),
    ]),
    ("model_selector", [
        ("aria", r"select( a)? model|choose model|انتخاب مدل", 3),
        ("id", r"model.selector|modelselector", 3),
        ("testid", r"model.selector", 3),
        ("cls", r"modelSelector", 2),
        ("text", r"^(glm|gpt|deepseek|qwen|qwen\d)[-\w.]*$", 1),
    ]),
    ("file_upload", [
        ("aria", r"attach|upload( file)?|آپلود|پیوست", 3),
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
  const all = [...document.querySelectorAll('button, a[role=button], [role=switch], [role=checkbox], [role=combobox], [role=listbox], input[type=checkbox], [aria-pressed], [data-testid]')];
  const seen = new Set(); const out = [];
  for (const e of all) {
    const r = e.getBoundingClientRect();
    if (r.width === 0 && r.height === 0) continue;
    const key = (e.outerHTML || '').slice(0, 120);
    if (seen.has(key)) continue; seen.add(key);
    const cls = e.className && e.className.baseVal !== undefined ? '' : String(e.className || '');
    out.push({
      tag: e.tagName,
      eid: e.id || '', testid: e.getAttribute('data-testid') || '',
      text: (e.innerText || '').trim().replace(/\s+/g, ' ').slice(0, 80),
      aria: (e.getAttribute('aria-label') || '').slice(0, 80),
      title: (e.getAttribute('title') || '').slice(0, 80),
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
