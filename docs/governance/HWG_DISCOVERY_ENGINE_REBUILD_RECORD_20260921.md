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

- Targeted Discovery tests: 12 passed.
- Full deterministic suite after reconstruction: 257 passed.
- `compileall`: PASS.
- `git diff --check`: PASS.
- Evidence level: E1 only; no live provider certification is claimed by this record.

## Open work

1. Bind current scanner probes into governed Exploration runs.
2. Add baseline collectors for runtime/CDP identity/account/session/page state.
3. Add explicit research manifest input and reuse-decision record.
4. Add Update Candidate review/accept/hold/reject workflow.
5. Build Discovery/Certification Control Plane workspace.
6. Add bounded interactive E2 certification with explicit user confirmation.
7. Feed accepted discoveries back into versioned Provider Profile, Account capability snapshot, regression corpus and evidence history.