"""Read-only Web Chat stop-surface discovery.

This script connects to the existing Chrome CDP instances used by Hooshka Web
Gateway and extracts DOM/runtime/backend surfaces that can support a provider
Stop Contract. It never submits prompts and never clicks controls.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from pathlib import Path
from typing import Any

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".runtime" / "kgwm_webchat_stop_surface_discovery_20260912.json"

PROVIDERS = {
    "zai-web": {"cdp": "http://127.0.0.1:9223", "host": "chat.z.ai"},
    "chatgpt-web": {"cdp": "http://127.0.0.1:9224", "host": "chatgpt.com"},
    "qwen-web": {"cdp": "http://127.0.0.1:9225", "host": "chat.qwen.ai"},
    "deepseek-web": {"cdp": "http://127.0.0.1:9226", "host": "chat.deepseek.com"},
}

RISK_RE = re.compile(r"captcha|human verification|security verification|verify you are human|slider|daily usage|usage limit|quota|too many requests|rate limit|please wait|cloudflare|turnstile", re.I)
STOP_RE = re.compile(r"stop|cancel|interrupt|abort|停止|中止|取消|终止|توقف|لغو", re.I)
SEND_RE = re.compile(r"send|submit|ارسال|发送|提交", re.I)
ACTIVE_RE = re.compile(r"stop responding|stop generating|generating|thinking|reasoning|response|deep think|در حال", re.I)
CHAT_ENDPOINT_RE = re.compile(r"chat|completion|conversation|message|stream|sse|backend|api", re.I)

DOM_JS = r"""() => {
  const visible = (el) => {
    const r = el.getBoundingClientRect();
    const st = window.getComputedStyle(el);
    return r.width > 0 && r.height > 0 && st.visibility !== 'hidden' && st.display !== 'none';
  };
  const rect = (el) => {
    const r = el.getBoundingClientRect();
    return {x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height)};
  };
  const attrs = (el) => {
    const names = ['id','class','role','aria-label','title','type','data-testid','data-state','data-disabled','disabled','aria-disabled','aria-pressed','aria-busy','placeholder','contenteditable'];
    const out = {};
    for (const n of names) {
      const v = el.getAttribute?.(n);
      if (v !== null && v !== undefined && String(v).length) out[n] = String(v).slice(0, 300);
    }
    return out;
  };
  const label = (el) => [
      el.innerText || '',
      el.textContent || '',
      el.getAttribute?.('aria-label') || '',
      el.getAttribute?.('title') || '',
      el.getAttribute?.('data-testid') || '',
      el.getAttribute?.('placeholder') || '',
      String(el.className || '')
    ].join(' ').replace(/\s+/g, ' ').trim().slice(0, 800);
  const selectorOf = (el) => {
    if (!el || !el.tagName) return '';
    const tag = el.tagName.toLowerCase();
    const id = el.id ? '#' + CSS.escape(el.id) : '';
    const dt = el.getAttribute?.('data-testid');
    const role = el.getAttribute?.('role');
    const aria = el.getAttribute?.('aria-label');
    if (dt) return `${tag}[data-testid=${JSON.stringify(dt)}]`;
    if (aria) return `${tag}[aria-label=${JSON.stringify(aria)}]`;
    if (role) return `${tag}[role=${JSON.stringify(role)}]`;
    return tag + id;
  };
  const candidates = [];
  const nodes = Array.from(document.querySelectorAll('button,[role="button"],textarea,input,[contenteditable="true"],form,[aria-label],[title],[data-testid],.ant-btn'));
  for (const el of nodes) {
    if (!visible(el)) continue;
    const lab = label(el);
    const parent = el.closest('form,[role="form"],footer,main,section,article,div');
    candidates.push({
      tag: el.tagName.toLowerCase(),
      selector: selectorOf(el),
      label: lab,
      attrs: attrs(el),
      rect: rect(el),
      disabled: !!el.disabled || el.getAttribute?.('aria-disabled') === 'true' || el.getAttribute?.('disabled') !== null,
      nearest_form: parent ? selectorOf(parent) : '',
      svg_count: el.querySelectorAll?.('svg').length || 0,
      child_button_count: el.querySelectorAll?.('button,[role="button"]').length || 0,
    });
  }
  const resources = performance.getEntriesByType('resource').map(e => ({
    name: e.name,
    initiatorType: e.initiatorType,
    duration: Math.round(e.duration),
    transferSize: e.transferSize || 0,
    responseEnd: Math.round(e.responseEnd || 0)
  })).slice(-400);
  const riskNodes = Array.from(document.querySelectorAll('[role="dialog"],[aria-modal="true"],.captcha,.cf-turnstile,iframe,button,[role="button"],div,section'))
    .filter(el => visible(el))
    .map(el => ({
      tag: el.tagName.toLowerCase(),
      selector: selectorOf(el),
      label: label(el),
      attrs: attrs(el),
      rect: rect(el)
    }))
    .filter(x => /captcha|human verification|security verification|verify you are human|slider|daily usage|usage limit|quota|too many requests|rate limit|please wait|cloudflare|turnstile/i.test(x.label + ' ' + JSON.stringify(x.attrs)))
    .slice(0, 30);
  const text = document.body?.innerText || '';
  const qwenPool = window.__mwbQwenController?.getPool?.();
  const qwenSession = qwenPool?.currentSession;
  return {
    url: location.href,
    title: document.title,
    body_text_tail: text.slice(-2500),
    body_text_length: text.length,
    risk_nodes: riskNodes,
    buttons_and_inputs: candidates,
    resource_entries: resources,
    globals: {
      qwen_controller: !!window.__mwbQwenController,
      qwen_session_state: qwenSession?.sessionState || '',
      zai_history_store: !!window.__mwbZaiHistoryStore,
      zai_config_store: !!window.__mwbZaiConfigStore,
      zai_module: !!window.__mwbZaiModule,
    },
  };
}"""

MODULE_INTROSPECT_JS = r"""() => {
  const out = {
    zai: {hasModule: !!window.__mwbZaiModule, hits: []},
    qwen: {hasController: !!window.__mwbQwenController, controllerKeys: [], poolKeys: [], sessionKeys: []},
    chatgpt: {globals: []},
  };
  try {
    const m = window.__mwbZaiModule || {};
    const keys = Object.keys(m);
    for (const k of keys) {
      const v = m[k];
      const src = typeof v === 'function' ? Function.prototype.toString.call(v).slice(0, 500) : '';
      const hay = (k + ' ' + src).toLowerCase();
      if (/stop|cancel|abort|interrupt|terminate|completion|conversation|message/.test(hay)) {
        out.zai.hits.push({key: k, type: typeof v, source_excerpt: src});
      }
      if (out.zai.hits.length > 80) break;
    }
  } catch (e) { out.zai.error = String(e).slice(0, 300); }
  try {
    const c = window.__mwbQwenController;
    if (c) {
      out.qwen.controllerKeys = Object.keys(c).slice(0, 80);
      const pool = c.getPool?.();
      out.qwen.poolKeys = pool ? Object.keys(pool).slice(0, 80) : [];
      out.qwen.sessionKeys = pool?.currentSession ? Object.keys(pool.currentSession).slice(0, 80) : [];
      out.qwen.sessionState = pool?.currentSession?.sessionState || '';
      out.qwen.knownStopMethods = ['stopResponse','stopAllResponses'].filter(k => typeof c[k] === 'function' || typeof pool?.currentSession?.[k] === 'function');
    }
  } catch (e) { out.qwen.error = String(e).slice(0, 300); }
  try {
    out.chatgpt.globals = Object.keys(window).filter(k => /chat|conversation|stop|abort|gizmo|openai/i.test(k)).slice(0, 100);
  } catch (e) { out.chatgpt.error = String(e).slice(0, 300); }
  return out;
}"""


def classify_dom(items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    stop, send, composer, active = [], [], [], []
    for item in items:
        hay = " ".join([item.get("label") or "", json.dumps(item.get("attrs") or {}, ensure_ascii=False)]).strip()
        slim = {k: item.get(k) for k in ["tag", "selector", "label", "attrs", "rect", "disabled", "svg_count"]}
        if STOP_RE.search(hay):
            stop.append(slim)
        if SEND_RE.search(hay) or item.get("tag") == "form":
            send.append(slim)
        if item.get("tag") in {"textarea", "input"} or item.get("attrs", {}).get("contenteditable") == "true" or "placeholder" in item.get("attrs", {}):
            composer.append(slim)
        if ACTIVE_RE.search(hay):
            active.append(slim)
    return {
        "stop_candidates": stop[:20],
        "send_candidates": send[:20],
        "composer_candidates": composer[:20],
        "active_state_candidates": active[:20],
    }


def classify_backend(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    seen = set()
    for e in entries:
        url = e.get("name", "")
        if not CHAT_ENDPOINT_RE.search(url):
            continue
        safe = re.sub(r"([?&](token|key|auth|signature|sig|access_token|id_token|code)=)[^&]+", r"\1[REDACTED]", url, flags=re.I)
        key = safe.split("?")[0]
        if key in seen:
            continue
        seen.add(key)
        rows.append({
            "url": safe[:500],
            "initiatorType": e.get("initiatorType"),
            "duration": e.get("duration"),
            "transferSize": e.get("transferSize"),
        })
    return rows[-60:]


async def discover_provider(pw, provider_id: str, spec: dict[str, str]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "provider": provider_id,
        "cdp": spec["cdp"],
        "host": spec["host"],
        "pages": [],
        "contract_inputs": {},
        "errors": [],
    }
    try:
        browser = await pw.chromium.connect_over_cdp(spec["cdp"], timeout=5000)
        for ctx in browser.contexts:
            for page in ctx.pages:
                if page.is_closed() or spec["host"] not in (page.url or ""):
                    continue
                try:
                    raw = await page.evaluate(DOM_JS)
                    module = await page.evaluate(MODULE_INTROSPECT_JS)
                    dom = classify_dom(raw.get("buttons_and_inputs") or [])
                    backend = classify_backend(raw.get("resource_entries") or [])
                    body = (raw.get("body_text_tail") or "")
                    page_result = {
                        "url": raw.get("url"),
                        "title": raw.get("title"),
                        "risk_visible": bool(raw.get("risk_nodes")),
                        "risk_nodes": raw.get("risk_nodes") or [],
                        "body_history_risk_text": bool(RISK_RE.search(body)),
                        "globals": raw.get("globals"),
                        "dom": dom,
                        "backend_resources": backend,
                        "module_introspection": module,
                        "body_tail_excerpt": body[-800:],
                    }
                    result["pages"].append(page_result)
                except Exception as exc:
                    result["errors"].append({"page": page.url, "error": type(exc).__name__ + ": " + str(exc)[:500]})
    except Exception as exc:
        result["errors"].append({"connect": type(exc).__name__ + ": " + str(exc)[:500]})

    all_stop = []
    all_send = []
    all_comp = []
    all_backend = []
    risk = False
    history_risk = False
    runtime = []
    for pg in result["pages"]:
        risk = risk or bool(pg.get("risk_visible"))
        history_risk = history_risk or bool(pg.get("body_history_risk_text"))
        all_stop += pg.get("dom", {}).get("stop_candidates", [])
        all_send += pg.get("dom", {}).get("send_candidates", [])
        all_comp += pg.get("dom", {}).get("composer_candidates", [])
        all_backend += pg.get("backend_resources", [])
        runtime.append(pg.get("globals") or {})
    result["contract_inputs"] = {
        "risk_visible": risk,
        "body_history_risk_text": history_risk,
        "stop_candidate_count": len(all_stop),
        "send_candidate_count": len(all_send),
        "composer_candidate_count": len(all_comp),
        "backend_resource_count": len(all_backend),
        "runtime_globals": runtime,
        "recommended_discovery_status": (
            "READY_FOR_STOP_CONTRACT_DRAFT" if result["pages"] and not risk else
            "HOLD_RISK_VISIBLE" if risk else
            "READY_FOR_STOP_CONTRACT_DRAFT_HISTORY_RISK_ONLY" if result["pages"] and history_risk else
            "NO_PROVIDER_PAGE_FOUND"
        ),
    }
    return result


async def main() -> None:
    OUT.parent.mkdir(exist_ok=True)
    async with async_playwright() as pw:
        results = []
        for provider_id, spec in PROVIDERS.items():
            print(f"DISCOVER {provider_id}", flush=True)
            results.append(await discover_provider(pw, provider_id, spec))
    payload = {
        "generated_at_epoch": time.time(),
        "generated_at_local_hint": "2026-09-12 Asia/Tehran",
        "mode": "read_only_no_prompt_no_click",
        "providers": results,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "out": str(OUT),
        "summary": {r["provider"]: r.get("contract_inputs", {}) for r in results},
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
