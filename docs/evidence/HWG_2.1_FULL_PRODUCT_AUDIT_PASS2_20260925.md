# HWG 2.1 Full Product / Control Plane Audit - Pass 2

Date: 2026-09-25
Work Item: `HWG-WORK-025`
Release baseline: `v2.1.0`
Dev remediation build: `2.1.1-dev.full-audit-remediation.20260925-1727`
Production 5000 remained unchanged.

## Negative-path and safety scenarios

### Raw YAML invalid-input path - PASS

A malformed YAML payload was submitted to Dev `PUT /panel/api/config`. Result: HTTP 400 with explicit `YAML parse error`. SHA-256 of `config.yaml` was identical before and after (`0a04e521161fef6f6baff9b55c0d9b2c1f9bca4d99331b6ca95a3bd9f31c6402`). No config write occurred.

### API key create/revoke lifecycle - PASS

A temporary Dev API key was generated through the governed endpoint. Only its hash/reference was persisted; the secret was neither printed nor stored by the audit. The new reference was observed, revoked, and the initial key set plus `auth.enabled` state were restored. Final full `config.yaml` SHA-256 matched the pre-test hash.

### Service deployment isolation - P0 finding / remediated

Production `/panel/api/service/status` exposed contradictory evidence before remediation: structured service state correctly identified `HooshkaWebGateway` as Running, while the subprocess `output`/`success` came from `service_manager.ps1` using its default Dev config and reported `HooshkaHWGNGDevGateway` missing. The same helper is used for start/stop, creating a cross-environment action risk.

Root cause: `_run_service_manager()` did not pass the active `CONFIG_PATH` to `service_manager.ps1`, despite the script supporting `-ConfigPath`.

Remediation: `_run_service_manager()` now resolves the active `CONFIG_PATH` and passes it explicitly with `-ConfigPath` for status/start/stop. A deployment-contract regression test enforces the binding.

Verification after mandatory version gate:
- visible Dev version: `2.1.1-dev.full-audit-remediation.20260925-1727`;
- focused deployment/version tests: 4/4 PASS;
- full suite: 612/612 PASS;
- direct production-profile status through the remediated helper: `manager_ok=true`, service `HooshkaWebGateway`, Running, and no Dev service name in command output.

## E3 reliability status

- W1 Production 2.1.0: PASS 3/3.
- First W2 attempt: functionally 6/6 exact but procedurally INVALID because orchestration replay produced six probes; preserved and excluded.
- Clean W2 replacement started `2026-09-25T17:16:00.0466675Z`, more than 30 minutes after W1, and passed exactly 3/3 with terminal commitment and retry=false.
- W3 remains pending; no E3 claim is made in this pass.

## Remaining scope

Provider mutation/delete/model-default scenarios, Account re-auth/logout recovery, Runtime repair, Service action recovery, stale/error/timeout injection, Provider Wizard negative/recovery, and final cross-workspace redundancy/misplacement review remain open. Destructive scenarios continue on Dev with rollback snapshots.
