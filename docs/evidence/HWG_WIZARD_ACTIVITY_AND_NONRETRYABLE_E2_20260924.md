# HWG Provider Wizard — Activity Visibility & Non-Retryable Qualification Evidence

Date: 2026-09-24 UTC
Scope: Dev Control Plane on `127.0.0.1:5080`; NoteGPT unknown-provider onboarding.
Evidence level: E2 for live Wizard activity behavior; E1+E2 for committed-failure preservation and UI contract.

## Owner finding
After starting the Provider Wizard, the UI did not make it sufficiently clear that HWG was still working or that the user should wait.

## Implemented behavior
- A persistent Wizard activity banner is shown for asynchronous Analyze/Observe/Qualification work.
- The banner shows current stage, explanatory wait message, elapsed time, spinner/progress treatment, and an explicit note that the system is busy.
- Re-entrant Wizard controls are disabled while work is active; URL editing is read-only.
- Observe transitions the same banner to Qualification rather than appearing idle between phases.
- The banner is removed only after the active operation chain terminates.

## Live verification
At ~1.8 s after starting live NoteGPT observation: `activity_visible=true`, stage=`مرحله ۲ از ۳ — مشاهده واقعی صفحه`, elapsed=`00:01`, Observe disabled, Analyze disabled.
Runtime screenshot: `.runtime-dev/wizard-activity-evidence/control-plane/20260924T210134784887Z-wizard-working-live.png`.
The operation later terminated with the activity banner hidden and the result area still visible.

## Qualification safety finding
NoteGPT produced `E2_FAILED_AFTER_COMMIT`: provider network activity proved commitment, but the expected response marker was not verified. The result has `submitted=true` and `retry_allowed=false`.
The Wizard/API now treat this as a domain outcome rather than an HTTP transport error, preserve the non-retryable lock across re-observation/target changes, and surface that automatic retry is forbidden.

## Verification
Targeted suites passed after the change. Final canonical verification: 569 passed; compileall PASS; panel.js syntax PASS; git diff --check PASS. Production port 5000 was not touched; Dev panel remained on 5080.
