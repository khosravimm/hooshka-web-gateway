# HWG Security Release Gate Matrix v1

Status: `PASS`
Work Item: `HWG-WORK-010`
Sources: `NG-AUTH-001..003`, Mission Â§13, Â§17, Â§19

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
| File/multimodal enablement gate | PASS | `core/security_gate.py`, `tests/test_security_release_gate.py` | Any declared files/vision capability fails startup unless bounded allow-listed file policy is explicitly enabled. Operational upload validation remains owned by the multimodal work item before capability enablement. |
| Challenge/account-risk handling | PASS | `core/provider_risk.py`, `tests/test_provider_risk.py`, `docs/evidence/HWG_BLIND_DISCOVERY_ACCESS_GATING_20260921.md` | Common taxonomy covers challenge, quota/rate-limit, region restriction, account restriction and auth/session renewal without bypass. |
| Dependency integrity/reproducibility | PASS | `requirements.lock`, `scripts/dependency_integrity_audit.py`, `tests/test_dependency_integrity_audit.py` | Exact direct lock, environment match, no URL/VCS/editable entries and `pip check` pass. |
| Known-vulnerability advisory scan | PASS | `scripts/security_advisory_audit.py`, `docs/evidence/HWG_SECURITY_RELEASE_GATE_E2_20260922.md` | OSV checked the 35-package resolved dependency closure from the validated environment; findings=0. |
| Rollback security contract | PASS | `docs/governance/HWG_SECURITY_ROLLBACK_CONTRACT_V1.md` | Security-sensitive rollback invariants are defined; operational cutover/rollback proof remains owned by WORK-014. |

## Current Decision

`HWG-WORK-010` remains `PARTIAL`. All security/privacy gates for the currently implemented capability set have E1/E2 evidence. Operational cutover/rollback proof remains in WORK-014 by contract, and unsupported multimodal/file capability remains fail-closed until its owning work item enables it with operational validation.
