# ADR-003: Single Shared Browser Window (NG-BRW-001)

**Status:** Accepted (migration in progress)
**Date:** 2026-09-20
**Deciders:** HWG agent (autonomous) + owner present for login/cutover
**Relates:** NG-BRW-001/002/003, ADR-002, HWG-CTRL-REQ-001 §1

## Context

Each enabled provider owns a full Chrome process (dev CDP 9323/9324/9326,
separate `--user-data-dir`). Checklist §1 demands exactly one browser window
with isolated tabs, no shared cookies/storage/session.

## Key platform fact

One Chrome process = one `--user-data-dir`. One window shows one profile;
different sites in one profile stay isolated by the cookie same-site model
(cookies/storage are per-origin). Same-site multi-account isolation inside a
single window is NOT possible in stock Chrome (separate windows/profiles
required). Therefore:

## Decision

1. **Providers (different origins) → one window, one shared profile.**
   chatgpt.com, chat.z.ai, chat.deepseek.com tabs coexist in a single Chrome
   on one CDP port with native per-origin isolation. This satisfies
   1.1–1.6 for the provider dimension.
2. **Same-provider multi-account → documented exception:** separate window
   per account (only Chrome-level jar isolation is real). Pool already keys
   tabs by (provider, account) so the model is ready; UI will show the
   exception explicitly rather than fake single-window compliance.
3. **Migration without session surgery:** no cookie-DB merging. Fresh shared
   profile; owner logs into the 3 sites once (present); old per-provider
   profiles kept as rollback backup, then retired.
4. **Reversibility:** old `cdp_url`/`profile_dir` values recorded in
   CHANGELOG; `shared_browser.enabled=false` + old chromes = instant rollback.
   Inventory duplicate-port rule relaxed ONLY when shared mode is on and all
   entries share identical cdp+profile (otherwise still an error).

## Consequences

- Positive: 1.1/1.2 true; 1.4–1.6 hold per-origin; FocusGuard story simpler.
- Negative: one-time re-login burden (owner present); orchestration scripts
  that enumerate per-provider runtimes must treat the shared entry as one
  (follow-up); qwen stays disabled/out of scope until enabled.
