# HWG Explorer AI Blocker Diagnosis — NoteGPT E2 Evidence

Date: 2026-09-24
Scope: Dev Control Plane `127.0.0.1:5080`; target candidate `notegpt-web`; production port 5000 untouched.

## Problem
The Explorer could use AI for unresolved controls, but the main Wizard state machine returned from blockers such as `QUALIFICATION_DIAGNOSIS_COMPLETE` without invoking AI. The user therefore saw a passive dead end even though governed AI-assistance capability already existed.

## Architecture change
The Wizard now uses this sequence for blocker states:

`Deterministic diagnosis -> AI blocker diagnosis (E0/CANDIDATE) -> deterministic safe-plan verification -> success or explicit Human Gate`

AI cannot directly promote a capability, click, login, solve CAPTCHA, accept terms, or resend a probe. Side-effect actions stay approval-gated.

Automatic read-only diagnosis scope is recorded in `discovery/policies/ai-assistance-v1.json` v1.2.0.

## Live NoteGPT result
Initial state: `QUALIFICATION_DIAGNOSIS_COMPLETE`, current probe `E2_FAILED_AFTER_COMMIT`, `retry_allowed=false`.

AI route selected `deepseek-web` as analyst and avoided target provider `notegpt-web`.

After correcting history input, AI observed four prior `E2_VERIFIED` NoteGPT attempts and classified the current blocker as a per-attempt response-surface verification gap rather than a global access failure.

AI recommendation: `continue_readonly`.

Auto-safe proposals included recorded-network inspection, response-surface correlation, current DOM inspection, visual-state inspection, and bounded wait/reobserve. `resend_probe` was separately classified as approval-required.

## Deterministic verification
The Explorer executed the read-only plan without resend:
- recorded network metadata inspected;
- bounded wait/reobserve performed;
- committed qualification rechecked;
- visual state remained `ready`;
- expected marker remained absent;
- prior E2 verified count = 4;
- prior response strategy = `smallest_stable_marker_anchored_surface`.

Final state:
- `workflow_state = AI_DIAGNOSIS_HUMAN_GATE`
- `next_required = approve_new_instrumented_probe`
- `user_action_required = true`

No new provider message was sent during AI diagnosis or deterministic verification.

## Evidence improvement
Future synthetic qualification probes now capture bounded same-origin chat response evidence (`status`, content type, bounded body snippet, exact marker presence) for chat/agent-stream endpoints. This is implemented but not promoted to E2 until a new explicitly approved live probe exercises it.

## Safety
AI output remains E0/CANDIDATE. Read-only verification is deterministic. A new instrumented probe requires an explicit user click in the Wizard. Existing automatic resend lock remains intact.

## Wizard visual verification
The Dev Wizard was exercised end-to-end on NoteGPT without approving a new probe. The integrated Provider view remained visible beside the Wizard and the final card rendered an explicit Human Gate rather than a passive dead end.

Observed UI state:
- status: process is not successful yet and is waiting for the user's decision for one new controlled test;
- visual state: `ready` / `visible enabled chat composer`;
- the Human Gate explains that AI and deterministic read-only checks are exhausted;
- automatic resend remains prohibited;
- a separate explicit approval control is shown for a new test with full evidence capture;
- no approval click was performed during this verification.

Screenshot: `.runtime-dev/wizard-activity-evidence/ai-blocker-human-gate-notegpt.png`.
