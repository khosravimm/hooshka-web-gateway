# HWG Security Release Gate — E1/E2 Closure Evidence

Date: 2026-09-22
Work Item: `HWG-WORK-010`
Scope: current `1.0.0-dev.7` development baseline.

## Deterministic security gates
- Loopback-only local trust; private/LAN addresses are not trusted as local.
- Remote health endpoints do not bypass authentication.
- Non-loopback startup fails closed unless auth, rate limiting, audit, explicit remote access, TLS termination and network ACL are declared.
- Audit events redact secret/content/prompt-like fields before persistence.
- HTTP request bodies are bounded.
- File/vision capability declarations fail startup unless bounded allow-listed upload policy is explicitly enabled.
- API keys are stored as hash references; query-string API keys are rejected.
- Account/Profile isolation and origin-scoped logout have prior E2 evidence.
- Provider risk taxonomy covers challenge, quota/rate limit, region restriction, account restriction and auth renewal.

## Dependency / supply-chain evidence
- Direct dependency lock: 10 packages.
- Resolved dependency closure checked against OSV: 35 packages.
- OSV findings: 0.
- `pip check`: PASS.
- Lock contains no URL/VCS/editable entries and matches the validated environment.

## Controlled runtime E2
A live loopback health check against `127.0.0.1:5080` returned HTTP 200.

The actual startup security validator was then exercised without opening a LAN socket:
- unsafe `0.0.0.0` configuration without remote policy was refused;
- refusal explicitly required remote_access enablement, TLS termination and network ACL/firewall;
- a non-loopback configuration with complete declared controls passed validation.

## Rollback linkage
Security-sensitive rollback invariants are defined in `HWG_SECURITY_ROLLBACK_CONTRACT_V1.md`.
Actual cutover and rollback execution/proof remain owned by `HWG-WORK-014` and are not claimed here.

## Decision
The security/privacy gate for the current implemented capability set is PASS at E1/E2. Unsupported file/multimodal capability remains fail-closed until its owning work item supplies operational validators. This record does not claim production cutover or rollback proof.
