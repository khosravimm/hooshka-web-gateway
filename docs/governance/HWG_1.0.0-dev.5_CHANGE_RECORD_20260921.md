# HWG 1.0.0-dev.5 Change Record

- Record ID: `HWG-CR-1.0.0-dev.5-20260921`
- Date: 2026-09-21
- Product version: `1.0.0-dev.5`
- Discovery Engine: `2.1.0-dev.1`
- Branch: `develop`
- Authority: `HWG-MISSION-NG-001` + `HWG-KT-WEBCHAT-001`
- Architecture: `HWG-DISC-ARCH-001` + `HWG-DISC-AE-001`
- Work Register: `HWG-WORK-REGISTER-001` v1.4.0
- Status: IN_DEVELOPMENT

## Purpose

dev.5 turns Discovery from a governed read-only scanner pipeline into an assisted exploration platform. Deterministic probes remain primary; interactive browser behavior and AI assistance are bounded secondary mechanisms with explicit approval and evidence rules.

This record does not claim RC readiness, complete provider certification, or E3 reliability.
## Discovery interaction changes

- Added `core/browser_behavior_probe.py` for governed `hover`, `focus` and opt-in `click` observations.
- Click is disabled by default. User confirmation is required and semantic guards block send/submit/delete/logout/payment/destructive surfaces.
- Behavior observations capture target before/after metadata plus bounded request, WebSocket and SSE metadata.
- Added `/panel/api/discovery/runs/<provider>/<run>/behavior` and Control Plane Behavior Lab controls.
- Added live read-only DeepSeek hover validation; no click, prompt submission or feature mutation occurred.

## AI-assisted discovery changes

- Added `core/discovery_ai_assist.py` and `core/discovery_ai_service.py`.
- AI is secondary to deterministic probes and requires explicit user approval.
- AI findings are normalized as `E0 / CANDIDATE / validation_required` and cannot directly mutate Provider Profile, Account Instance or certification state.
- Added `/panel/api/discovery/runs/<provider>/<run>/ai-assist` and approval controls in the Discovery workspace.
## Routing changes

- Added `core/discovery_model_router.py` with `ordered`, `least_loaded` and `weighted_load` policies.
- Eligibility is filtered by enabled/healthy state, required capability and cooldown.
- Exact-provider/model routing is strict; unavailable exact routes fail instead of silently crossing to another provider.
- For generic Discovery AI analysis the router prefers a provider other than the provider being investigated.
- Use of the target provider itself requires an explicit policy choice when no alternative is available.
- Routing is for resilience/capability/load distribution only and must not bypass provider limits, challenges, suspension or access controls.

## Versioned policies

- `discovery/policies/ai-assistance-v1.json`
- `discovery/policies/routing-v1.json`
- `docs/governance/HWG_DISCOVERY_ASSISTED_EXPLORATION_ARCHITECTURE_V1.md`
## Live evidence

DeepSeek development runtime was observed with a read-only hover probe on `.ds-toggle-button`:

- target text: `DeepThink`
- `aria-pressed`: `false` before and after
- network requests observed during the bounded window: 4
- WebSocket events observed: 0
- SSE responses observed: 0
- click performed: no
- prompt submitted: no
- provider feature state intentionally changed: no

The first live Behavior Lab attempt exposed a missing `_host()` helper in `core/discovery_runtime.py`; the defect was fixed and a regression test was added before the successful rerun.
## Work Register state

- `HWG-WORK-018` AI-assisted Discovery: PARTIAL — implementation exists; live model-assisted run still needs certification.
- `HWG-WORK-019` policy routing: PARTIAL — reusable policy core exists; integration with the general Gateway routing plane remains open.
- `HWG-WORK-020` Browser Behavior Lab: IN_PROGRESS — DeepSeek hover is live-validated; multi-provider and broader interaction validation remains open.
- `HWG-WORK-001` Discovery Engine remains IN_PROGRESS and depends on completion of the Behavior Lab plus scoped interactive E2 certification.

## Remaining gates

- Validate Behavior Lab on at least one additional provider.
- Run a user-approved AI-assisted Discovery analysis through an active model and validate the proposed probe deterministically.
- Complete interactive E2 certification of a governed Discovery Run.
- Integrate policy routing into the broader Gateway routing plane without weakening strict provider semantics.
- Continue Provider Profile / Account Instance persistence and remove the shared-profile conflict.

## Target-provider self-use transport qualification

- Added `core/provider_self_use_gate.py` and schema `urn:hwg:schema:provider-self-use-qualification:1.0.0`.
- Explicit user approval is necessary but not sufficient for target-provider self-use.
- Self-use requires deterministic identification of send, receive and completion paths plus a successful controlled nonce round-trip.
- Qualification is bound to a SHA-256 transport fingerprint derived from the current provider transport configuration; transport/profile/config drift invalidates the record.
- AI-derived path guesses cannot satisfy the qualification gate.
- `core/self_use_roundtrip_probe.py` performs source-hashed deterministic adapter-path identification before any live send and validates the round-trip by exact string comparison only.
- Discovery Control Plane exposes current self-use gate status and disables target-provider selection until qualification exists.
- `self-use-qualify` is an automated deterministic validation action; it no longer depends on human confirmation to run engineering tests.
- Live DeepSeek qualification passed and produced the scoped evidence record `docs/evidence/HWG_DEEPSEEK_SELF_USE_QUALIFICATION_20260921.md`.
- `HWG-WORK-021` is DONE with scoped E2 transport evidence; general Discovery certification and E3 remain open.

## Final deterministic and live validation

- Targeted self-use/AI-routing/governance suite: `27 passed` after the automated-validation contract update.
- Full HWG deterministic suite after all dev.5 changes: `309 passed`.
- `compileall`: PASS.
- `node --check control_panel_ui/panel.js`: PASS.
- `git diff --check`: PASS.
- Two controlled exact-token DeepSeek round-trips passed; one through Gateway API and one through the provider adapter qualification harness.
- A target-provider AI-Assisted Discovery call was executed only after transport qualification; its output remained `E0 / CANDIDATE / validation_required=true`.
- Human control remains a separate product-validation/certification concern and is not used to compensate for missing automated engineering tests.

## Blind Discovery and access-state gating

- Added profile-independent `core/blind_discovery.py`; prior Provider Profiles are excluded from the discovery phase and used only for post-run comparison.
- Added access states `WAITING_FOR_LOGIN`, `WAITING_FOR_USER_INTERACTION`, `DIAGNOSTIC_REQUIRED`, and `BLOCKED` to the governed Discovery lifecycle.
- Exploration is fail-closed while an access prerequisite is unresolved; re-baseline is mandatory after login/interaction/restriction state changes.
- Live blind discovery identified ChatGPT, DeepSeek, Z.ai, and Qwen. Qwen was classified `BLOCKED / region_restriction`; no bypass was attempted.
- Corrected transcript-text authentication false positives and static-asset backend-endpoint false positives.
- Evidence: `docs/evidence/HWG_BLIND_DISCOVERY_ACCESS_GATING_20260921.md`.
