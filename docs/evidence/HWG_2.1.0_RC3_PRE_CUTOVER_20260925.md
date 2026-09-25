# HWG 2.1.0-rc.3 Pre-Cutover Release Evidence - 2026-09-25

## Scope

RC3 adds explicit Production deployment-profile isolation and is the candidate authorized for controlled cutover to port 5000. No Production cutover had occurred at the time this record was created.

## Accepted candidate

- Version: `2.1.0-rc.3`
- Branch: `develop`
- Dev Control Plane visible version: `2.1.0-rc.3`
- Development endpoint: `127.0.0.1:5080`
- Production deployment endpoint: `127.0.0.1:5000`
- Production Windows service: `HooshkaWebGateway`
- Production config: `config.production.yaml`
- Shared authenticated browser runtime reused intentionally: CDP `127.0.0.1:9330`

## Pre-cutover gates

| Gate | Result | Evidence |
|---|---|---|
| Deployment profile focused tests | PASS | 11/11 |
| Full deterministic suite | PASS | 612/612 |
| Python compile gate | PASS | compileall |
| Control Plane JS syntax | PASS | node --check |
| Diff hygiene | PASS | git diff --check |
| Secret scan | PASS | 81 files, 0 findings |
| Dependency advisory audit | PASS | OSV, 35 packages, 0 findings |
| Production service dry config | PASS | `HooshkaWebGateway`, `http://127.0.0.1:5000/health` |
| Dev/Prod service identity isolation | PASS | 5080 Dev / 5000 Production |
| Provider runtime contract parity | PASS | production preserves provider IDs/CDP/enabled state |
| Production cutover | AUTHORIZED / NOT YET EXECUTED | Owner authorization received in chat |
| Rollback rehearsal | NOT YET EXECUTED | To be performed after first cutover smoke |

## Rollback baseline

- Ref: `rollback/pre-2.1.0-rc1-cutover-20260925`
- Commit: `ebd971735ff5e8d5a596d4d543c6c66e61de4f89` (`v0.7.19`)

## Release boundary

This record authorizes controlled operational cutover testing only. Stable promotion requires successful Production health/readiness/API/provider smoke, a real rollback rehearsal, restoration to RC3, and post-restoration verification.
