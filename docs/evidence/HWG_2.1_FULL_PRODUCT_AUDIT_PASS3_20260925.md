# HWG 2.1 Full Product / Control Plane Audit - Pass 3

Date: 2026-09-25
Work Item: `HWG-WORK-025`
Dev build: `2.1.1-dev.full-audit-remediation.20260925-1736`
Production `2.1.0` remained unchanged.

## Provider lifecycle governance bypass - P0 / CLOSED on Dev

A temporary known-provider fixture was created on Dev against the existing shared Browser Runtime. Creation correctly persisted it disabled and declared `login_discovery_certification_before_enable`. The fixture had no readiness record. Before remediation, `PUT /panel/api/providers/<id>/settings` with `enabled=true` returned HTTP 200 and enabled the Provider, proving that the backend could bypass the UI Current-READY gate. The fixture was deleted and the original `config.yaml` restored byte-for-byte.

Remediation: disabled-to-enabled transitions in `api_provider_settings` now require Current READY evidence (`state=READY`, `ready=true`, `current=true`) for known providers. Custom discovered-web providers retain their stricter activation lane. Disable operations and idempotent already-enabled requests are not blocked by this transition gate.

Verification after mandatory version/restart/DOM gate:
- visible Dev version: `2.1.1-dev.full-audit-remediation.20260925-1736`;
- focused provider lifecycle/version tests: 10/10 PASS;
- full suite: 614/614 PASS;
- live temporary Provider re-test: create=201/disabled; enable without readiness=409 `provider_enable_requires_current_readiness`; readiness state returned `UNKNOWN`, `ready=false`, `current=false`; delete=200; final config restored byte-for-byte.

## E3 orchestration hygiene

The accepted W2 is the clean replacement beginning `2026-09-25T17:16:00.0466675Z` and passing exactly 3/3. The earlier six-probe W2 remains invalid and excluded. Duplicate W2 and the earlier W3 runner were disabled; only the no-replay `W3 Clean` task remains scheduled, preserving the predefined window contract.

## Remaining destructive audit scope

Runtime repair/open recovery, Account re-auth/logout with recoverable isolation, Service action recovery, model/default mutation rollback, Provider Wizard negative/recovery paths, stale/error/timeout injection, and final information-architecture redundancy/misplacement review remain open.
