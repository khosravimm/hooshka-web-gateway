# HWG 2.1.0 — E3 Reliability + Full Product/Control Plane Audit Mission

Date: 2026-09-25
Release under audit: `v2.1.0` / `74929915533634956a5db41ba9210d213220e986`
Production: `http://127.0.0.1:5000/panel/`
Development: `http://127.0.0.1:5080/panel/`
Browser/CDP: `http://127.0.0.1:9330`
Work items: `HWG-WORK-013`, `HWG-WORK-025`

## Mission

Audit HWG as a complete operational product after the 2.1.0 release. The audit is not limited to backend correctness or a visual smoke test. It must validate every Control Plane workspace, visible control, state, scenario, layout relationship, operator workflow, evidence claim and recovery path.

No defect is closed from source inspection alone. Visual/runtime evidence is required for UI findings; E3 claims require the predefined multi-window contract.

## Audit layers

### L1 — Complete inventory

For every workspace record:
- navigation entry and domain owner;
- all buttons, links, forms, text fields, selects, checkboxes and destructive actions;
- tables/cards/graphs/log/evidence surfaces;
- enabled/disabled state and prerequisite;
- backing API/action and expected post-condition;
- duplicate/misplaced/missing controls.

### L2 — Visual and layout audit

For every workspace and important state:
- Persian-first / RTL correctness;
- hierarchy, grouping, alignment, spacing and density;
- horizontal overflow, clipping and inaccessible content;
- readable labels and actionable status language;
- loading, empty, stale, ready, blocked, error and success states;
- scrolling and long-content behavior;
- viewport/responsive behavior;
- state colors/badges consistent with measured evidence;
- charts, counters, cards and tables match actual semantics.

Screenshots and machine-readable geometry are evidence, not substitutes for scenario verification.

### L3 — Scenario-driven interaction

Scenarios include at minimum:
1. operator opens Production and understands current system state;
2. Browser Runtime -> Profile -> Account -> Session -> Readiness relationship;
3. authenticated DeepSeek readiness -> Chat -> exact response -> telemetry;
4. stale readiness -> visible block -> probe -> recovery;
5. disabled Provider behavior and forbidden/invalid actions;
6. Provider Wizard discovery/qualification/materialization path;
7. model/capability refresh and certification scope;
8. session refresh and continuity;
9. API-key/auth lifecycle with safe recovery;
10. human config reload/change/diff/restart/recovery/rollback;
11. raw YAML advanced path and validation failures;
12. Service start/stop/restart/recovery state;
13. Runtime repair/open-login behavior;
14. Account validate/open/re-auth/readiness/logout under controlled recovery;
15. telemetry after real Provider dispatch and after control-plane-only traffic;
16. logs/diagnostics versus durable evidence separation;
17. remaining-work register, dependencies, exit criteria and evidence links;
18. theme/navigation/refresh and browser-history/operator ergonomics;
19. error injection / invalid input / timeout / stale evidence;
20. Production/Dev isolation: actions must not silently cross 5000/5080 boundaries.

### L4 — Governance/completeness review

Classify findings as:
- `CORRECT`
- `GAP`
- `MISSING`
- `MISPLACED`
- `REDUNDANT`
- `MISLEADING`
- `UNSAFE`
- `INCONSISTENT`

Each finding must have severity, workspace, scenario, evidence, expected behavior, actual behavior, remediation, and verification state.

## Workspace matrix

1. Overview — operational summary, real Provider traffic, readiness/card semantics, charts.
2. Browser Runtimes — runtime grouping, shared CDP, repair/open behavior.
3. Browser Profiles — storage boundary, sharing/origin/account relationships.
4. Accounts & Session — validate/open/re-auth/readiness/logout lifecycle.
5. Providers — provider management, enablement, Wizard, certification boundary.
6. Models & Capabilities — model list, capability scope, evidence age.
7. Discovery & Certification — deterministic exploration, AI assist, Behavior Lab, review and certification lanes.
8. Interactive Chat — provider/model/account readiness, feature toggles, attachments, send/stop, exact response.
9. Sessions — conversation/session continuity and auditability.
10. Telemetry — HTTP versus Provider dispatch, token measured/estimated, graph semantics.
11. API Keys & Access — auth state, generation, local/non-local semantics, revocation/recovery.
12. Configuration — human form, raw YAML advanced path, diff, validation, restart impact.
13. Service & Restart — actual Production topology, state, restart/recovery, Dev isolation.
14. Remaining Work — dependencies, evidence, exit criteria, anti-forgetting behavior.
15. Diagnostics & Evidence — raw diagnostics versus durable evidence/change/certification records.
16. Provider Form — new Web Chat onboarding outcome and next action chain.

## Interaction safety strategy

- Production 5000: read-only and bounded operational actions first; no destructive logout/auth/config mutation without explicit rollback snapshot.
- Dev 5080: destructive and negative-path interaction laboratory after configuration/runtime snapshots.
- Existing CDP 9330/profile is reused; no second browser profile is introduced unless the scenario specifically tests profile isolation.
- Any product code change requires: VERSION bump -> restart only Dev 5080 -> reload existing panel -> verify `#meta-version` -> tests -> live visual re-audit.

## E3 reliability contract for 2.1.0

Fresh release-specific scope:
`deepseek-web / deepseek-web:default-account / deepseek-web / Production 5000`

- W1: 2026-09-25 — 3/3 PASS.
- W2: scheduled >=30 minutes after W1.
- W3: scheduled >=30 minutes after W2.
- Full E3 claim is forbidden until all three windows pass for this exact scope.

## Current visual baseline

Raw runtime evidence:
`.runtime-prod/control-plane-full-audit-20260925T163504Z/`

At viewport `1402x944`:
- 15 primary workspaces audited;
- horizontal overflow: 0/15;
- horizontal clipping: 0/15;
- console errors: 0;
- page errors: 0;
- screenshots and per-workspace control/geometry inventory captured.

The initial broad `clipped` detector also counted normal content below the viewport. Those vertical-scroll observations are not findings unless a control is inaccessible after scrolling.

## Completion rule

This mission closes only when:
- every workspace and visible control is inventoried;
- safe and destructive scenarios are executed with controlled rollback where applicable;
- visual/layout findings are verified after remediation;
- P0/P1 findings are closed or explicitly accepted with rationale;
- W1/W2/W3 E3 contract is resolved;
- Production/Dev isolation remains proven;
- final evidence, audit register and work register are synchronized.
