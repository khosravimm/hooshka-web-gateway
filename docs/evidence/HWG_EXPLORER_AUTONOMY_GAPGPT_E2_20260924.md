# HWG Explorer Autonomy — GapGPT E2 — 2026-09-24

## Scope
- Real URL-driven onboarding candidate: `https://gapgpt.app/`
- No manual provider facts, selectors, capability values, or state hints were injected.
- Objective: observe Explorer failure, improve the engine, and rerun the same candidate.

## Initial failure
- Candidate persisted as `state=OBSERVED` with user-view classification `unknown`.
- Visible body already contained Persian login text (`ورود`), but the classifier only recognized English login patterns.
- Onboarding observation used one fixed 3.5-second snapshot and terminated even on `unknown`.

## Engine remediation
- User-view login/challenge classification was made multilingual.
- Candidate observation now runs bounded autonomous passes with stable waits, scroll positions, screenshots, interaction maps, and trace evidence.
- `unknown` after autonomous passes is explicitly marked `needs_deeper_exploration`; it is not assigned to the user as a completion task.

## Live rerun result
- Official Wizard observe endpoint returned HTTP 200.
- Classification: `login_required`.
- Evidence: visible Persian text `ورود`.
- `autonomous_passes=1`.
- `needs_deeper_exploration=false`.
- Screenshot evidence showed the rendered login wall from the user's view and matched the classifier result.

## Regression verification
- Targeted Explorer/Provider wizard tests: 15 passed.
- Full Python suite: 495 passed.
- Python compileall: PASS.
- JavaScript syntax check: PASS.
- `git diff --check`: PASS.

This evidence proves the engine improvement on the original failing candidate; it does not certify GapGPT as an operational HWG provider.