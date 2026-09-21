# HWG 1.0.0-dev.6 Change Record

**Date:** 2026-09-22  
**Status:** Development baseline  
**Scope:** Control Plane relationship model and governed Provider provisioning

## Why this version exists

The previous UI mixed Provider, Browser Runtime and Browser Profile concepts. A shared Browser Runtime could appear as multiple independent Runtime cards, while the Add Provider form exposed raw CDP/Profile fields and could persist runtime data under the wrong config level.

## Architectural corrections

- Browser Runtime is now grouped by `(CDP URL + Browser Profile)` and Provider pages are represented as child tabs.
- Single-window/multi-tab intent is preserved instead of reverting to one browser window per Provider.
- Add Provider is a three-step governed workflow: Provider Definition → existing Browser Runtime → review/save.
- Raw CDP/Profile text inputs were removed from Provider creation.
- New Providers are always created disabled and must pass Login/Discovery/Certification before Enable & Test.
## Backend contract

- `providers[].runtime` is persisted at the canonical top level.
- Adapter-required values are derived into `providers[].config` from the selected Browser Runtime.
- The hidden default `9330 + shared-profile` was removed from the creation path.
- Provider type and Provider ID are validated; runtime selection must reference an existing Browser Runtime.
- The response explicitly returns `login_discovery_certification_before_enable` as the next required stage.

## UI/UX

- Provider type is a controlled select, not free text.
- Browser Runtime choices are loaded from `/panel/api/browser-runtimes`.
- A relationship preview shows Provider → Browser Runtime → Profile → Home URL before save.
- Runtime control cards now distinguish Browser/CDP readiness from Agent/Login readiness.

## Governance

This work advances `HWG-WORK-002` and `HWG-WORK-006`. It does not claim final account-isolation or full Control Plane completion; those remain governed work until E2 validation of the redesigned UI and account lifecycle is complete.

## Evidence

- Targeted Provider provisioning / Browser Runtime grouping / Profile management tests: PASS.
- Full deterministic suite: **338 passed**.
- `compileall`, JavaScript syntax and `git diff --check` are release-blocking final checks for this local commit.
- No E2 deployment claim is made for the stale 5080 process until dev.6 is deployed from a clean/controlled runtime checkout.

## Live development cutover evidence

The development checkout was safely fast-forwarded to `feb23f4` after preserving the prior local state in both a named Git stash and an external backup. The 5080 gateway was then restarted from the dev.6 checkout.

Live validation confirmed version `1.0.0-dev.6`, commit `feb23f4`, two Browser Runtime groups, Desktop Runtime Agent reachability on 5181, and the new runtime-key-based Provider provisioning contract. See `docs/evidence/HWG_DEV6_CONTROL_PLANE_E2_20260922.md`.

This is scoped E2 for development Control Plane deployment/serving. It is not an E3 reliability claim and does not close account-isolation or full UX acceptance.

## Account-centric session lifecycle

HWG-WORK-005 is closed with scoped E1+E2 evidence. Session validation now runs structural access classification before provider-specific checkers, account state persists to explicit Account Instances, and login/open, re-auth/open and logout are available through account-centric endpoints.

Shared-browser logout was corrected from global context cookie clearing to origin-scoped `Storage.clearDataForOrigin`. A temporary two-origin Chrome E2 test verified that the target origin was cleared while the neighboring origin retained its cookie and LocalStorage state. Persisted Account Instance session records were audited and contained no secret-like keys. See `docs/evidence/HWG_ACCOUNT_SESSION_LIFECYCLE_E2_20260922.md`.

## Functional readiness state machine

HWG-WORK-003 is closed with E1+E2 evidence. `/ready` no longer treats registration or CDP reachability as operational readiness. A TTL-bound readiness record is produced only after ordered runtime/CDP, page-interactive, account access, model, live feature-state and exact-token functional-probe stages.

DeepSeek passed all six stages and caused `/ready` to transition from HTTP 503 to HTTP 200 only after evidence was saved. Qwen had a healthy CDP but stopped fail-closed at `BLOCKED / region_restriction`; model and functional-message stages were not executed. See `docs/evidence/HWG_FUNCTIONAL_READINESS_E2_20260922.md`.
