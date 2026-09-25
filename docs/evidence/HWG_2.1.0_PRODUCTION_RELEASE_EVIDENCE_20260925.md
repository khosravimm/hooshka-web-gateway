# HWG 2.1.0 Production Release Evidence - 2026-09-25

## Release claim

`2.1.0` is an **E2 operational release**. It is not an E3 reliability certification.

## Local release gates

- RC4 preflight full suite: 612/612 PASS.
- RC4 secret scan: 0 findings.
- RC4 OSV dependency audit: 35 packages / 0 findings.
- Compileall / Node syntax / diff hygiene: PASS.
- Exact stable `2.1.0` focused release gates: 5/5 PASS.
- Exact stable `2.1.0` full suite: 612/612 PASS.
- Exact stable secret scan: 85 files / 0 findings.
- Exact stable OSV dependency audit: 35 packages / 0 findings.
- Exact stable compileall / Node syntax / diff hygiene: PASS.

## Controlled production cutover evidence

- Production Windows service: `HooshkaWebGateway`, Automatic.
- Production config: `config.production.yaml`; endpoint `127.0.0.1:5000`.
- Dev endpoint `5080` and browser CDP `9330` remained available through cutover/rollback/restart.
- RC3 production health: PASS.
- RC3 production readiness: AUTHENTICATED; runtime/page/auth/model/feature/functional stages all PASS.
- RC3 exact-marker smoke: `HWG_PROD_RC3_563756` PASS.
- Rollback to `v0.7.19` / `ebd971735ff5e8d5a596d4d543c6c66e61de4f89`: health PASS, version `0.7.19`, models API PASS.
- Restore to RC3: readiness PASS; exact marker `HWG_PROD_RC3_RESTORE_711480` PASS.
- Production gateway scheduled restart: task result 0; log `success=True`; post-restart readiness PASS; exact marker `HWG_PROD_RESTART_604280` PASS.
- Production Control Plane UI rendered RC3 version and DeepSeek `READY ???????` using the existing browser tab; the tab was returned to 5080 afterward.

## Rollback reference

`rollback/pre-2.1.0-rc1-cutover-20260925` -> `ebd971735ff5e8d5a596d4d543c6c66e61de4f89`.

## Governance boundary

`HWG-WORK-014` remains PARTIAL because the registry requires E3 evidence and depends on `HWG-WORK-013`. E2 cutover/rollback proof is complete; no E3 claim is promoted.

## Exact stable deployment verification

Pending after local `2.1.0` full-suite PASS and Production restart to the final accepted commit.
