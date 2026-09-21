# HWG Discovery Assisted Exploration Architecture v1

- Record ID: `HWG-DISC-AE-001`
- Date: 2026-09-21
- Parent: `HWG-DISC-ARCH-001`
- Authority: `HWG-MISSION-NG-001` + `HWG-KT-WEBCHAT-001`
- Status: Governed architecture baseline

## Principle

Discovery is deterministic-first. Functions, procedures, DOM/accessibility inspection, runtime/session checks, network metadata and protocol observations are attempted before asking an AI model to interpret ambiguity.

AI is a secondary investigator, not an authority. AI output is always a candidate with provenance and cannot directly mutate Provider Profile, Account Instance, selectors, routing, readiness or certification state.

## Three execution layers

1. Deterministic Probes — default and preferred path.
2. Interactive Browser Behavior Lab — bounded hover/focus/click observation with DOM/network/WebSocket/SSE evidence.
3. AI-Assisted Investigator — approval-gated use of an active HWG model when deterministic evidence leaves unresolved questions.

## Behavior Lab safety contract

Hover and focus are low-risk observations. Click is disabled by default and requires explicit user confirmation plus a non-destructive target. Send, submit, delete, logout, purchase/payment and destructive controls are blocked by semantic guards.

Observations are metadata-first and bounded. A behavior record contains action provenance, target before/after state, bounded network request metadata, WebSocket URLs and SSE response metadata. Secret/storage values are not collected.

A Behavior Probe is evidence for Discovery only; it does not by itself certify a capability.

## AI assistance contract

AI assistance can be `disabled`, `explicit`, or covered by a scoped `session_grant`. Deterministic evidence and unresolved questions must be supplied to the model. The selected provider/model, purpose and result provenance must be recorded.

Model output starts at E0/CANDIDATE. It must be checked by deterministic probes or governed live evidence before it can influence a Provider Profile or certification decision.

## Routing contract

When multiple eligible models exist, the Discovery AI Router may use ordered, least-loaded or weighted-load policies. Eligibility filters include enabled state, health, required capability and cooldown state.

Exact-provider or exact-model requests are never silently cross-routed. Routing is for resilience, capability fit and load distribution while respecting provider limits; it must not bypass rate limits, CAPTCHA/challenges, suspension, access controls or provider policy.

## Evidence and history

Every AI-assisted or interactive behavior action must be attributable to a Discovery Run. Decisions and findings are appended to run history/evidence and then returned to Provider Profile, Account capability snapshot, regression corpus and governance records only after review.

## Open implementation gates

- Bind active-provider inventory to AI Router candidates.
- Add two-stage AI request/approval/execute API and UI.
- Add behavior-delta summarization and selector-candidate generation.
- Add WebSocket frame metadata observation with bounded capture where Playwright/provider permits it.
- Validate the Behavior Lab against at least two provider UIs before marking `HWG-WORK-020` DONE.

## Target-provider self-use transport gate

User approval is necessary but is not sufficient for using the provider under investigation as its own AI-assisted analyst. The target provider is eligible for self-use only after a deterministic transport qualification record proves all of the following:

- send path identified by non-AI probes/functions;
- receive path identified by non-AI probes/functions;
- completion detection identified by non-AI probes/functions;
- one controlled deterministic round-trip passed with evidence;
- the qualification matches the current transport fingerprint.

The router fails closed when the qualification is missing, incomplete, stale or AI-derived. A transport/profile/config change invalidates the previous qualification. The controlled qualification round-trip requires explicit human authorization and uses an exact nonce comparison; no semantic AI judgment determines pass/fail.
