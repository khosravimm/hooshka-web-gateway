# HWG 1.0.0-dev.4 Change Record

- Record ID: `HWG-CR-1.0.0-dev.4-20260921`
- Date: 2026-09-21
- Product version: `1.0.0-dev.4`
- Branch: `develop`
- Authority: `HWG-MISSION-NG-001` v1.0.0 + `HWG-KT-WEBCHAT-001` v1.0.0
- Evidence ceiling for this record: E2 where explicitly stated; otherwise E1/E0

## Scope

This record freezes the governance and operational-model transition introduced after the dev.3 baseline. It records the control-plane workflow redesign, runtime-agent contract correction, governance-source registration, requirement traceability and first versioned NG Profile/Account schemas.

## Versioned artifacts

- Application: `VERSION` -> `1.0.0-dev.4`
- Release manifest: `MANIFEST.json` -> `1.0.0-dev.4`
- Control Plane UI: `control_panel_ui/UI_VERSION.json` -> `1.0.0-dev.4`
- Provider Profile schema: `urn:hwg:schema:provider-profile:1.0.0`
- Account Instance schema: `urn:hwg:schema:account-instance:1.0.0`
## Operational changes recorded

- Control Plane workspaces no longer duplicate Runtime `Start/Open` actions in the Provider-management surface.
- Browser/Profile operations are represented as prerequisites for Provider readiness rather than peer controls.
- Desktop Runtime Agent now resolves its listening endpoint from canonical orchestration configuration instead of a conflicting hard-coded port.
- An interactive-user Scheduled Task installation path is present for the Desktop Runtime Agent.
- Profile inventory now distinguishes assigned/shared/managed/legacy state and safe deletion eligibility.

## Governance changes recorded

- Mission and Knowledge Transfer Playbook are canonical repository governance sources.
- Requirement conflicts are tracked rather than silently normalized to current implementation.
- `shared-profile` remains an explicit isolation migration conflict.
- Binary CDP availability is not accepted as final Provider READY.
- Every future architecture/behavior change must update version/history, traceability and evidence in the same change set.
## NG contract projection work unit

- Added `core/profile_contract.py` as a read-only compatibility projection from legacy `config.yaml` to Provider Profile v1 + Account Instance v1.
- Added `/panel/api/ng/inventory` as a machine-readable migration/relationship inventory.
- Current projection: 4 Provider Profiles, 4 Account Instances.
- Current conflict: `.runtime-dev\\shared-profile` is shared by `chatgpt-web`, `zai-web`, and `deepseek-web` and is reported as `CONFLICT` against NG-BRW-003/profile-boundary requirements.
- Projection is explicitly `legacy_config_projection`; it does not claim migration completion or certification.
- Deterministic validation after this work unit: `254 passed`.

## Discovery Engine governed-pipeline work unit

- Reframed `core/discovery_engine.py` / `core/control_discovery.py` as Exploration probes rather than the entire Discovery subsystem.
- Added `core/discovery_orchestrator.py` with explicit Research -> Baseline -> Exploration -> Synthesis -> Update Candidate -> Certification lifecycle.
- Added versioned Discovery Recipe and Discovery Result schemas plus `webchat-standard-v1` recipe.
- Added reconstruction architecture and rebuild records under `docs/governance/`.
- Evidence promotion remains fail-closed: E1 discovery does not become operational capability without scoped E2 certification.
- Added Control Plane `کاوش و گواهی` workspace backed by governed Discovery Run records.
- Added `/panel/api/discovery/runs` GET/POST; new runs are persisted under `.runtime-dev/discovery/<provider>/<run_id>/result.json` and always start at `RESEARCH_REQUIRED`.
- Added run listing/reload support; live Exploration and Interactive Certification remain open and therefore `HWG-WORK-001` stays `IN_PROGRESS`.

## Remaining-work anti-forgetting work unit

- Added `HWG-WORK-REGISTER-001` with 16 tracked work items spanning Discovery, isolation, readiness, Profile/Account persistence, UI, multimodal, SDK, security, reliability, evidence, cutover, repository governance and documentation.
- Each item records source requirement, status, priority, dependencies, target version, required evidence and exit criteria.
- Added validation that rejects malformed status, missing source/evidence/exit criteria, duplicate IDs and unknown dependencies.
- Added `/panel/api/governance/work-register` and a dedicated Control Plane `کارهای باقی‌مانده` workspace.
- Current register baseline: 16 non-DONE items, including 9 open P0 items.
- Deterministic validation after integration: `260 passed`.
- No item may be removed or marked DONE solely to reduce backlog; exit criteria and evidence are mandatory.

## Governed live-read-only Discovery integration

- Added read-only Baseline and Exploration endpoints for persisted Discovery Runs; neither path submits prompts nor changes provider controls.
- Added explicit Update Candidate review (`ACCEPT`, `HOLD`, `REJECT`) and Interactive Certification lifecycle.
- `CERTIFIED/E2` requires an evidence record plus explicit user confirmation; a successful scan alone remains E1/live-read-only evidence.
- Hardened generic frontend enumeration to include visible role/button and keyboard-focusable surfaces rather than adding a DeepSeek-specific selector patch.
- Live DeepSeek observation on the existing development runtime found the composer, `DeepThink`, `Search`, and 7 candidate backend endpoints; no prompt was submitted and no control was changed.
- `HWG-WORK-017` closed only after its exit criteria were met and evidence/completion metadata were recorded. Work Register version is now `1.1.0` with 17 items.
- Anti-forgetting validation now rejects any `DONE` work item that lacks recorded evidence or a completion timestamp.
- Full deterministic validation after this work unit: `267 passed`.
- `HWG-WORK-001` intentionally remains `IN_PROGRESS` until scoped Interactive Certification/E2 is completed with explicit user confirmation.
