# HWG Discovered Provider GapGPT — E2 Evidence — 2026-09-24

## Scope
A real unknown web-chat URL (`https://gapgpt.app/`) was used as an autonomous onboarding case. No provider-specific selector, adapter fact, capability fact, or expected response was supplied manually.

## Explorer progression
- Initial visible state was Persian login; multilingual classification corrected `unknown` to `login_required`.
- After the user-side login gate was already satisfied, Explorer re-observed the live page and classified it `ready` from the visible enabled composer.
- Deterministic discovery found composer, model selection, file input, backend hints and unresolved controls.
- A temporary composer fill identified a submit candidate without sending the probe marker.
- Explorer generated its own challenge and performed one committed E2 round trip; exact marker verification passed and hidden retry remained forbidden.

## Adapter and runtime evidence
- Explorer generated a browser UI adapter candidate and independently qualified it with a second exact-marker E2 probe.
- Response surface refinement selected `div.markdown-container` from marker-anchored DOM evidence.
- The adapter profile was materialized under `docs/profiles/gapgpt-web/adapter_candidate.v1.json` with status `E2_CONFORMANT_CANDIDATE`.
- The provider was registered in HWG as `type=custom`, `adapter_kind=discovered_web`, and `enabled=false`.
- Main runtime loading remains fail-closed: profile path must remain under `docs/profiles`, provider id must match, and candidate status must be E2 conformant.

## Readiness reconciliation defect found and fixed
A previously READY record had expired while the Candidate still said `READY_FOR_ENABLE_CONFIRMATION`. Control Plane reconciliation now requires `ready=true`, `state=READY`, and `current=true`; stale evidence returns the Candidate to `readiness_probe_before_enable`.

After the shared browser was restarted, only DeepSeek was present. HWG correctly reported GapGPT `PAGE_NOT_INTERACTIVE`. The official Open Browser path recreated the GapGPT tab, after which a fresh automated readiness probe passed all stages and returned current READY evidence.
