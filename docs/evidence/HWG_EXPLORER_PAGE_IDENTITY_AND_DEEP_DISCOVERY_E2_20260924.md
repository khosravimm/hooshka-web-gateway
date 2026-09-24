# HWG Explorer — Page Identity and Deep Discovery E2

Date: 2026-09-24
Scope: URL-driven Provider onboarding / Explorer runtime
Candidate: `gapgpt-web`
URL: `https://gapgpt.app/`

## Rule of this test

No provider facts, selectors, capability values, or adapter hints were manually injected into the Candidate.
Only generic Explorer logic was changed after weaknesses were observed on the live page.

## Weaknesses observed

1. Re-observation could create a new tab instead of continuing the same page.
2. Readiness depended too strongly on a visible Send control.
3. Custom model selectors exposed useful evidence through `role/value/context` that the classifier ignored.
4. Icon-only controls lacked unique selectors for safe behavior probing.
5. Hover probes only captured the target element and could miss tooltip text rendered elsewhere.

## Generic engine changes

- CDP `targetId` is now persisted as page identity and reused on re-observation while alive.
- A visible enabled `textarea`/contenteditable composer can establish `ready` even when Send is lazy-rendered.
- Control discovery now uses `role`, `value`, nearby context and unique structural selectors.
- Persian file/upload labels are recognized by the generic classifier.
- Ready onboarding automatically runs deterministic Discovery on the same page.
- Unclassified controls receive bounded read-only hover probes; page-wide visible-text deltas are recorded.

## Live E2 result

Two consecutive Wizard observations used the same target:

- classification: `ready`
- evidence: `visible enabled chat composer`
- second observation: `target_reused=true`
- deterministic discovery: completed
- chat: E1 high
- model selection: E1 medium
- file upload: E1 high
- backend API signals: E1 medium

Behavior probing preserved uncertainty correctly:

- one icon-only control revealed no additional evidence;
- one icon-only control revealed visible text `جست‌وجو در گفت‌وگوها` on hover;
- it was **not** promoted to Web Search because the generic classifier did not have sufficient matching evidence.

This is intentional fail-closed behavior: behavior evidence may improve classification, but ambiguous controls remain unclassified.

## Boundary

No message was submitted and no capability was promoted to E2 provider certification in this slice. This evidence covers live Explorer/onboarding behavior only.
