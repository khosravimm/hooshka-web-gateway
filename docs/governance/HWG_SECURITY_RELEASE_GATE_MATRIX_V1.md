# HWG Security Release Gate Matrix v1

Status: `PARTIAL`
Work Item: `HWG-WORK-010`
Sources: `NG-AUTH-001..003`, Mission §13, §17, §19

This matrix is release-blocking. A security capability is not accepted because it exists in code; it must have deterministic tests and, where relevant, live evidence.

## Gate Summary

| Gate | Status | Evidence | Notes |
|---|---:|---|---|
| Local Trust boundary | PASS | `tests/test_security_release_gate.py` | Loopback-only trust; LAN/private ranges are not treated as local trust. |
| Remote health/auth bypass | PASS | `tests/test_security_release_gate.py` | Health endpoints bypass auth only for loopback. Non-loopback follows normal auth. |
| Remote exposure startup guard | PASS | `core/security_gate.py`, `main.py`, `tests/test_security_release_gate.py` | Non-loopback bind requires auth, rate limit, audit, explicit remote access, TLS termination declaration and network ACL declaration. |
| API key hashing and bearer-only extraction | PASS | `tests/test_session_key_security.py` | Stored keys are hash refs; query-string API key is rejected. |
| Provider rate limiting | PASS | `tests/test_provider_rate_limit.py` | Provider-scoped limit is enforced after routing. |
| Account/Profile isolation | PASS | `docs/evidence/HWG_SINGLE_WINDOW_ORIGIN_ISOLATION_E2_20260922.md` | Cross-origin shared profile is origin-isolated; same-origin multi-account conflict fails closed. |
| Origin-scoped logout | PASS | `docs/evidence/HWG_ACCOUNT_SESSION_LIFECYCLE_E2_20260922.md` | Logout clears only the target origin, not the whole shared browser context. |
| Secret leakage in persisted account/session store | PASS | `docs/evidence/HWG_ACCOUNT_SESSION_LIFECYCLE_E2_20260922.md` | Account session metadata is allow-listed; token/cookie/secret-like fields are rejected. |
| Safe logging / metadata-first audit | PASS | `core/governance.py`, `tests/test_security_release_gate.py` | Audit sanitizer redacts secret/content/prompt-like fields before persistence; audit remains metadata-first. |
| HTTP request body bounds | PASS | `main.py`, `tests/test_security_release_gate.py` | `MAX_CONTENT_LENGTH` is bounded and oversized JSON requests fail closed. |
| File/multimodal upload validation | OPEN | none | Upload/file endpoints are not operational; future multimodal/file support must be gated before enablement. |
| Challenge/account-risk handling | PARTIAL | `docs/evidence/HWG_BLIND_DISCOVERY_ACCESS_GATING_20260921.md` | Qwen region restriction is classified fail-closed; broader challenge/risk taxonomy remains open. |
| Dependency/supply-chain checks | OPEN | none | No release-blocking dependency audit yet. |
| Rollback linkage | OPEN | `HWG-WORK-014` | Controlled rollback proof is a separate P0 and depends on security completion. |

## Current Decision

`HWG-WORK-010` remains `PARTIAL`. The first remote-exposure gap is fixed with E1 evidence, but the release gate is not complete until the remaining OPEN/PARTIAL rows are closed or explicitly deferred with owner approval.
