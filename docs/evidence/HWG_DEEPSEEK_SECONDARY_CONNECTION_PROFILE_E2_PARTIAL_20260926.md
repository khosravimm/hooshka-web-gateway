# HWG Connection Profile Multi-Account E2 — DeepSeek Secondary Login Gate

Date: 2026-09-26
Environment: Dev `127.0.0.1:5080` on Safe-Laptop only
Provider: `deepseek-web`
Primary account: `deepseek-web:default-account`
Secondary account: `deepseek-web:e2-secondary-20260926`
Build: `2.1.1-dev.connection-profile-ia.20260926-0105`
Decision: **PARTIAL E2 / HUMAN LOGIN GATE**

## Objective
Prove the real same-origin multi-account path without disturbing Production 5000 or the existing shared DeepSeek session on CDP 9330.

## Live results
- A second Connection Profile was provisioned through the Dev account API.
- Secondary Browser Profile: `.runtime-dev\\accounts\\deepseek-web__e2-secondary-20260926`.
- Secondary Runtime/CDP: `127.0.0.1:9340`.
- The secondary profile directory is physically distinct from `.runtime-dev\\shared-profile`.
- CDP 9330 remained running and the existing default DeepSeek account remained operational.
- Production port 5000, Runtime Agent 5181 and shared CDP 9330 remained unchanged throughout this checkpoint.
- The secondary Browser Profile did **not** inherit the authenticated primary session. It first rendered the DeepSeek sign-in page and then the provider's guest-capable composer.
- Because HWG policy requires authenticated Web Chat sessions, guest composer visibility is not accepted as authenticated evidence.
- Raw structural discovery therefore returns `UNKNOWN` with `user_interaction=login`; Account lifecycle maps that fail-closed state to `LOGIN_REQUIRED`.

## Classifier correction found during E2
The previous generic rule treated a visible composer as `AUTHENTICATED`. This is unsafe for providers such as DeepSeek that expose a guest composer. The rule is now fail-closed: composer-only evidence is `UNKNOWN` and requires login at the Account lifecycle boundary.

## Evidence
- Live secondary session after correction: `LOGIN_REQUIRED`, authenticated=false.
- Screenshot captured from the real secondary CDP target: `.runtime-dev/connection-profile-e2/deepseek-secondary-login-gate.png`.
- Targeted tests: `25 passed`.
- Full canonical suite after Dev service restart: `634 passed`.

## Remaining acceptance step
The user must authenticate a real second DeepSeek account in the already-open isolated 9340 window. After login, HWG must revalidate both accounts, verify the secondary account becomes AUTHENTICATED without changing the default account/session, and then complete the live two-account isolation evidence.

No broader multi-account E2 claim is made yet.
