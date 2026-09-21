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
- Full deterministic suite: **321 passed**.
- `compileall`, JavaScript syntax and `git diff --check` are release-blocking final checks for this local commit.
- No E2 deployment claim is made for the stale 5080 process until dev.6 is deployed from a clean/controlled runtime checkout.
