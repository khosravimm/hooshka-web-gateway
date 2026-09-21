# HWG Discovery Engine Reconstruction Record — 2026-09-21

- Record ID: HWG-DISC-REBUILD-20260921-001
- Application baseline: 1.0.0-dev.4
- Discovery Engine: 2.0.0-dev.1
- Architecture: HWG-DISC-ARCH-001 v1.0.0
- Mission authority: HWG-MISSION-NG-001 v1.0.0
- Playbook authority: HWG-KT-WEBCHAT-001 v1.0.0

## Trigger

Review showed that the existing `core/discovery_engine.py` was primarily a read-only frontend/backend scanner. It did not embody the complete research-first, baseline, update-candidate, interactive-certification and evidence-promotion lifecycle required by the Mission.

## Change

A governed Discovery orchestration layer was introduced. The existing scanner remains reusable as an Exploration probe rather than being treated as the complete engine. Versioned Discovery Recipe and Discovery Result schemas were added together with a standard Web Chat recipe.## Evidence

- Governed Discovery/anti-forgetting targeted suite: 22 passed in the latest work unit.
- Full deterministic suite after live-read-only integration: 267 passed.
- `compileall`: PASS.
- `node --check control_panel_ui/panel.js`: PASS.
- `git diff --check`: PASS.
- Live read-only DeepSeek observation: composer, DeepThink, Search and 7 candidate backend endpoints observed; no prompt submitted and no feature state changed.
- Generic frontend discovery was corrected to cover role/button and keyboard-focusable surfaces; no DeepSeek-specific selector patch was introduced.
- Evidence level remains E1/live-read-only for Discovery findings; no provider capability E2 certification is claimed by this record.

## Current state

1. Scanner probes are bound to governed Exploration runs.
2. Baseline collection covers runtime/CDP, page targets, account reference and read-only session state where supported.
3. Research-first input is mandatory before Baseline.
4. Update Candidate review supports `ACCEPT/HOLD/REJECT`.
5. Discovery/Certification has a dedicated Control Plane workspace.
6. Interactive Certification lifecycle exists and E2 PASS requires both an evidence record and explicit user confirmation.
7. `HWG-WORK-017` is DONE with recorded evidence; `HWG-WORK-001` remains IN_PROGRESS until scoped E2 certification is completed.

## Open work

1. Perform a governed end-to-end Discovery Run through Interactive Certification with explicit user observation/confirmation.
2. Feed accepted discoveries back into persistent versioned Provider Profile, Account capability snapshot, regression corpus and evidence history.
3. Strengthen Research manifests with structured external/internal source classification and reuse-decision records.