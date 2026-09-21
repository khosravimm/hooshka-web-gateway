# HWG Account Session Lifecycle — E2 Evidence

- Date: 2026-09-22
- Scope: `HWG-WORK-005` / NG-ACC-001/002
- Runtime: Development `127.0.0.1:5080`
- Application line: `1.0.0-dev.6`
- Evidence class: E1 + scoped E2

## Implemented contract

Account session state is normalized as:

`UNKNOWN | LOGIN_REQUIRED | USER_INTERACTION_REQUIRED | AUTHENTICATED | BLOCKED | EXPIRED`

Provider-specific session checks are no longer the first gate. Structural browser access classification runs first and may fail closed before an expensive provider checker.

Account-centric endpoints now cover session validation, login/open, re-auth/open and logout. Provider-oriented endpoints remain compatibility paths.
## Live validation

- ChatGPT account: `AUTHENTICATED`, persisted in `persistent_ng_store`.
- DeepSeek account: `AUTHENTICATED`, persisted; account login/open and re-auth/open succeeded through Desktop Runtime Agent.
- Z.ai account: `AUTHENTICATED`, persisted.
- Qwen account: structural-first validation returned `BLOCKED / region_restriction`; the post-change request completed in about 0.6–2.3 seconds instead of timing out on the provider checker.

Qwen account logout was executed on its dedicated browser profile. The account state first became `LOGIN_REQUIRED` because of explicit logout; immediate revalidation then correctly restored the observed `BLOCKED / region_restriction` state.

## Shared-browser logout isolation

A separate temporary Chrome profile was used with two local origins. Origin A and Origin B each received independent LocalStorage and cookies. `Storage.clearDataForOrigin` was executed only for Origin A.

Result: target Origin A storage/cookie data was cleared while Origin B retained both its LocalStorage value and cookie. No authenticated ChatGPT/DeepSeek/Z.ai session was used for this isolation experiment.
## Secret-persistence audit

The four persisted Account Instance session records were scanned for secret-like keys. No `token`, `cookie`, `secret`, `api_key`, or `authorization` key was present. Persistence now uses an allow-list for lifecycle fields and selected evidence fields only.

## Scope limits

This evidence proves account-centric lifecycle behavior and origin-scoped session clearing for the current development baseline. It does not prove same-provider multi-account isolation, which remains under `HWG-WORK-002`, and it is not an E3 reliability claim.
