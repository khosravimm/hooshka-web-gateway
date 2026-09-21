# ADR-002: Shared-Browser Pool (NG-BRW-001 target)

**Status:** Accepted (implementation: opt-in foundation)
**Date:** 2026-09-20
**Deciders:** HWG agent (autonomous, per HWG-DEV-GUIDE-NG-001 v1.3.0 §4)
**Relates:** NG-BRW-001/002/003, Reuse Report HWG-GAP-20260920

## Context

Each provider currently owns a separate Chrome instance on its own CDP port
(`config.yaml` providers[].runtime: 9323–9326 dev). NG-BRW-001 requires one
browser window with isolated tabs per provider/account. A flag-day migration
would risk the dev gateway (5080) and must never touch production (5000).

## Decision

Introduce `core/browser_pool.py` (`SharedBrowserPool`) as an **opt-in**
foundation, disabled by default:

- One Chrome + one CDP endpoint; one CDP target (tab) per
  `(provider_id, account_id)`. `resolve()` never leaks another account's tab.
- Background ops never activate tabs; `bring_to_front()` raises
  `FocusViolation` outside `FocusGuard.user_initiated()` (NG-BRW-002).
- Reuse only: `requests` over CDP HTTP (`/json/version|list|new|close`),
  existing `FocusGuard`. No new dependencies.
- Enablement: `runtime_orchestration.shared_browser: {enabled, cdp_url,
  profile_dir}`. Absent/disabled → `None` → current behavior unchanged.

## Options considered

1. **Playwright BrowserContext tabs** — rejected for the pool core: heavier,
   new lifecycle to own; Playwright stays for E2E tests only.
2. **Flag-day cutover** — rejected: violates controlled-cutover rule.
3. **Opt-in pool (chosen)** — reversible, testable without live browser
   (mocked CDP HTTP), adapters migrate one by one behind config.

## Consequences

- Positive: single-window UX path unblocked; account isolation enforced in
  code; background focus-stealing structurally impossible.
- Negative: two runtime paths coexist until migration completes; operators
  must not enable `shared_browser` until at least one adapter is tab-bound.
- Follow-up: bind chatgpt-web adapter first (pilot), then Discovery recipe
  update, then RC + user certification before enabling by default.
