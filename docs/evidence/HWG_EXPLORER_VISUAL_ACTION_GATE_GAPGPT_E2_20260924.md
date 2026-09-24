# HWG Explorer Visual Action Gate — GapGPT E2 — 2026-09-24

## Trigger
GapGPT visibly displayed a free-plan file-processing quota message while media qualification was attempted.
The previous flow noticed the message only after entering upload processing.

## Defect
Explorer had a visual classifier, but media qualification did not gate the action before `set_input_files()`.
Also, generic `processing` text could be classified as `upload_busy` before the more important quota state.

## Fix
- Added reusable `visual_action_gate(page, action)`.
- Blocking semantic states are evaluated before generic upload-busy state.
- Added action-aware quota scope: media-only quota blocks media actions but does not block normal text Send.
- Discovered-provider media qualification now performs visual preflight before attaching a file.
- AI click verification also checks the visual gate before approved click probes.

## Live evidence
GapGPT page visibly showed the Persian file-processing quota message.
Live gate result: media qualification `allowed=false`, state `quota_limited`, scope `media`.
Text Send remained `allowed=true` because the quota was media-scoped.
A repeated media qualification returned in about 1.1 seconds with `status=blocked`, `tested=false`, `commitment_state=not_sent`, `retry_allowed=true` and no new certification.

## Evidence level
E2 live user-view state + action gating behavior.

## Remaining limitation
GapGPT media classes remain uncertified until the provider quota becomes available; blocked evidence must not be interpreted as lack of capability.
