# HWG Human Acceptance Script v1

**ID:** HWG-HUMAN-ACCEPT-001  
**Version:** 1.0.0  
**Purpose:** Human validation of the Control Plane as an executable representation of Mission, domain relationships and operational sequence.

## Rules

This gate is not a substitute for E1/E2 engineering tests. The operator evaluates whether the system is understandable, correctly sequenced, truthful about evidence, and usable without undocumented project knowledge.

For every scenario record: `PASS / FAIL / HOLD`, observation, unexpected behavior, and screenshot/evidence reference when useful.

## Acceptance principle

A human should be able to answer from the UI itself: What am I managing? What is its parent/child relationship? What prerequisite is missing? Why is this state shown? What is the next valid action? Was the action verified after execution?
## Scenarios 1–5

1. **Overview / Health** — Identify which Provider is operationally usable now and explain why Browser-ready is not the same as Functional READY.
2. **Browser Runtimes** — Explain why ChatGPT/Z.ai/DeepSeek may share one Browser Runtime while Qwen may be separate; locate the governed Open/Login action.
3. **Browser Profiles** — Identify shared versus exclusive storage boundaries and explain why same-origin multi-account needs isolation.
4. **Accounts & Sessions** — For each Account, identify Session state, Readiness state, Evidence freshness, and the next valid action.
5. **Providers** — Explain Provider Definition versus Account versus Browser Runtime; verify enablement cannot bypass readiness requirements.

Expected result: relationships and prerequisites are understandable without reading source code or external documentation.## Scenarios 6–10

6. **Discovery / Certification** — Starting from a fresh Run, identify Research, Baseline, Exploration, assisted investigation, Candidate review and Certification lanes; explain what stops on Login/Verification/Block.
7. **Models / Capabilities** — Distinguish declared capability from certified/current evidence and identify the Provider/Account/Model scope of evidence.
8. **Embedded Chat** — Verify Send is unavailable when readiness is stale/unknown/blocked; explain the displayed reason and run the offered readiness action when appropriate.
9. **Telemetry** — Distinguish operational traffic from synthetic/test traffic and verify the page does not imply provider dispatch from unrelated panel polling.
10. **Sessions / Conversations** — Locate active conversation state and relate it to Provider/Account rather than legacy execution terminology.

Expected result: the UI never requires the operator to infer certification or readiness from configuration alone.## Scenarios 11–15

11. **API Keys / Access** — Confirm one-time key display, metadata listing, revocation semantics and the distinction between loopback trust and remote access.
12. **Configuration** — Verify common settings are human-readable and Browser ownership is not edited through raw CDP/Profile fields; advanced YAML is clearly marked as advanced.
13. **Services / Recovery** — Identify the actual execution topology: direct Gateway process or Windows Service, Desktop Runtime Agent and its Scheduled Task; verify unavailable actions are disabled.
14. **Diagnostics / Evidence** — Distinguish raw diagnostic logs from structured E2/Certification/Change evidence.
15. **Remaining Work** — Identify current P0/P1 blockers, dependencies, required Evidence and Exit Criteria without consulting chat history.

## Acceptance closure

Human Acceptance is complete only when all scenarios are `PASS` or an explicitly accepted `HOLD` is linked to a Work Register item. Any new semantic defect becomes a new Audit Register finding before acceptance can close.