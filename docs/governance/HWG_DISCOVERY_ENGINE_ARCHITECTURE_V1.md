# HWG Discovery Engine Architecture v1.0.0

- Document ID: HWG-DISC-ARCH-001
- Version: 1.0.0
- Status: Candidate architecture aligned to HWG-MISSION-NG-001
- Date: 2026-09-21
- Parent mission: HWG-MISSION-NG-001 v1.0.0
- Technical playbook: HWG-KT-WEBCHAT-001 v1.0.0

## Purpose

Discovery Engine is a first-class governed subsystem. It is not a DOM scanner and it must not patch provider integrations directly. Its job is to research, baseline, explore, classify, detect drift, produce reviewable update candidates, and drive interactive certification with evidence.

## Governed lifecycle

`RESEARCH_REQUIRED -> BASELINE_REQUIRED -> EXPLORATION_READY -> EXPLORING -> SYNTHESIZING -> UPDATE_CANDIDATE|CERTIFICATION_REQUIRED -> CERTIFYING -> CERTIFIED`

Terminal safety states: `HOLD`, `REJECTED`, `FAILED`.

No E1 discovery result is promoted to operational capability without real E2 certification. Drift never mutates a production Provider Profile silently.## Subsystems

1. Research gate: official docs, current internal evidence, mature external implementations, issue history.
2. Baseline collector: owned runtime, CDP identity, account/session, page state and current profile version without mutation.
3. Exploration probes: DOM/Accessibility, frontend controls/controllers, Network, SSE/WebSocket, model/catalog, uploads, errors and session transitions.
4. Synthesizer: normalizes findings while preserving provider-native semantics and provenance.
5. Drift engine: compares current findings against the versioned Provider Profile/Recipe baseline.
6. Update Candidate builder: materializes proposed profile/transport changes for explicit review; no silent patching.
7. Certification orchestrator: applies exact Provider/Account/Model/Feature expectations, runs bounded real probes, records E2, and requires explicit user certification for changed profiles.
8. Knowledge return: accepted discoveries update Provider Profile, Adapter/Transport history, evidence, regression tests and architecture/ADR where required.

## Versioned artifacts

- Discovery Engine version
- Discovery Recipe schema + recipe version
- Discovery Result schema + run record
- Provider Profile / Account Instance targets
- Update Candidate and decision
- Certification/Evidence record

Runtime run records belong under ignored `.runtime-dev/discovery/`; stable recipes, schemas, accepted evidence and architecture belong in tracked repository history.