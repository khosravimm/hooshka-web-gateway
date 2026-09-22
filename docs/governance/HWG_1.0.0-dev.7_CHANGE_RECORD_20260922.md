# HWG 1.0.0-dev.7 Change Record

**Date:** 2026-09-22  
**Status:** Development baseline  
**Scope:** Mission-driven Control Plane semantics and human-test readiness

## Why this version exists

dev.7 treats the Control Plane as an executable representation of Mission, domain model, operational sequence and governance. The goal is not visual polish alone; the UI must let a human operator understand what entity is managed, why the current state exists, what prerequisites apply, and what the next valid action is.

## Governance

- Added `HWG-UI-AUDIT-001` Mission-driven UI/UX Audit Framework.
- UI Audit Register `HWG-UI-AUDIT-REGISTER-001` advanced to v1.3.0.
- Work Register advanced to v1.15.0.
- `HWG-WORK-006` Control Plane relationship redesign is closed with E1+E2 evidence.
- `HWG-WORK-025` remains IN_PROGRESS only for Human Acceptance; automated E1/E2 is not treated as human approval.
## Control Plane corrections

- Runtime keeps only governed Open/Login actions; raw external links are no longer an alternate operational path.
- Account cards expose readiness reason, evidence timestamp and next action, with in-context Readiness Probe.
- Models/Capabilities distinguishes declared capability from Provider/Account/Model readiness evidence.
- Chat is gated by current readiness evidence; STALE/UNKNOWN/BLOCKED paths disable Send and explain why.
- Service workspace renders actual execution topology: direct Gateway process, Windows Service state and Desktop Runtime Agent/task separately.
- Diagnostics logs are separated from structured Evidence/Certification/Change Records.
- Provider provisioning explicitly states that Provider Definition does not create Account Instance and shows Account as the next lifecycle step.
- Browser Profile enumeration excludes internal HWG runtime directories and does not treat metadata-only profile markers as browser data.

## Evidence

- Pass 2 live browser audit on development 5080: zero console errors.
- All 23 registered UI findings are VERIFIED in Audit Register v1.3.0.
- Scoped E2 record: `docs/evidence/HWG_MISSION_DRIVEN_UI_AUDIT_PASS2_E2_20260922.md`.
- Human acceptance remains pending and separate from engineering E1/E2.
- Final deterministic suite: **364 passed**; compileall, JavaScript syntax and `git diff --check` passed.

## Live development cutover

Development 5080 was reloaded after final validation and reported application version `1.0.0-dev.7`; semantic Browser Profile enumeration returned five real profiles with temporary audit profiles removed.
