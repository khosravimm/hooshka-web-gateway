# HWG 2.1.0-rc.2 Release Closure Evidence — 2026-09-25

> RC2 supersedes `v2.1.0-rc.1`. RC1 was rejected before production cutover because GitHub verification detected encoding corruption in the canonical START_HERE document. No production deployment occurred from RC1.

## Scope

This record captures the pre-cutover release-candidate closure for Hooshka Web Gateway 2.1.0-rc.2. It does not claim production cutover or E3 reliability certification.

## Accepted source baseline

- Branch: `develop`
- Pre-RC2 parent SHA: `2c37b107f2cf776a84c85fc4ca472cdfda2ef120`
- Release identity after closure: `2.1.0-rc.2`
- Dev Control Plane: `http://127.0.0.1:5080/panel/`
- Visible DOM version gate: PASS (`#meta-version = 2.1.0-rc.2`)

## Release gates

| Gate | Result | Evidence |
|---|---|---|
| Focused release contract | PASS | 3/3 |
| Full deterministic suite | PASS | 608/608 |
| Python compile gate | PASS | `compileall` |
| Control Plane JS syntax | PASS | `node --check control_panel_ui/panel.js` |
| Diff hygiene | PASS | `git diff --check` |
| Secret scan | PASS | 81 files, 0 findings |
| Dependency advisory audit | PASS | OSV, 35 packages, 0 findings |
| Version synchronization | PASS | VERSION / MANIFEST / UI_VERSION synchronized |
| DeepSeek live functional readiness | PASS (E2) | AUTHENTICATED; runtime/page/auth/model/feature/functional_probe all PASS |
| DeepSeek token observability | PASS (E2 bounded) | 10 prompt + 4 completion = 14 total, explicitly `usage_estimated=true` |
| Production cutover on port 5000 | NOT EXECUTED | Production service absent; prior mission forbids touching 5000 without explicit authorization |
| Rollback rehearsal | NOT EXECUTED | Requires controlled production cutover authority |
| E3 reliability certification | NOT CLAIMED | Work register remains in progress |

## Security closure

The release secret scanner previously reported two false positives caused by descriptive evidence field names containing the word `password`. No credential value was stored. The evidence field names were clarified without weakening scanner rules. Re-run result: `findings=0`.

Dependency advisory audit returned zero findings for the resolved dependency closure.

## Release boundary

RC2 passed the complete local release gate and is acceptable as an **E2 operational release candidate** only. It is not yet a Production Stable release because controlled cutover and rollback proof have not been executed, and E3 reliability is not claimed.

## Rollback baseline

Repository inspection shows the latest existing stable-style tag is `v0.7.19`, resolving to:

`ebd971735ff5e8d5a596d4d543c6c66e61de4f89`

A dedicated pre-cutover rollback reference should point to this SHA before any production migration.

## Remaining production gate

Before Production Stable promotion:

1. Obtain explicit owner authorization to touch port 5000 / production runtime.
2. Create/verify production runtime or Windows Service using the accepted RC SHA.
3. Run `/health`, readiness, modes/models/capabilities and bounded provider smoke.
4. Execute rollback rehearsal to the recorded pre-cutover baseline.
5. Record cutover and rollback evidence.
6. Only then promote/tag a stable release.
