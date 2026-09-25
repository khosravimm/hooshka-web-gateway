# HWG 2.1 Full Product / Control Plane Audit - Pass 1 and Remediation

Date: 2026-09-25
Work Item: `HWG-WORK-025`
Release baseline under audit: `v2.1.0`
Remediation build: `2.1.1-dev.full-audit-remediation.20260925-1730`
Production: `127.0.0.1:5000` (unchanged)
Development validation: `127.0.0.1:5080`

## Scope executed

- all 15 primary Control Plane workspaces plus Provider Form internal workspace inventoried;
- Production visual baseline captured with screenshots and machine-readable geometry;
- navigation, visible control inventory, enabled/disabled state, loading states, horizontal overflow, console/page errors audited;
- safe interaction scenarios exercised: Models/Sessions/Telemetry/Config reload, all Diagnostics log sources, Provider Form open/close, global refresh, theme roundtrip;
- relationship chain verified across six Account cards;
- Models capability matrix compared against all six registered Providers;
- responsive geometry checked at 1402px, 1024px and targeted 768px;
- accessibility names rechecked with ancestor-label semantics to avoid false positives.

## Baseline facts

- Production full-panel baseline: 15/15 workspaces, horizontal overflow 0/15 at 1402x944, console errors 0, page errors 0.
- 1024px: body overflow false, 15/15 workspace overflow false.
- Refined accessibility audit: zero visible controls without an accessible name after ancestor-label handling.
- Account relationship chain: 6 accounts / 6 relationship previews.
- Safe interaction sweep: all executed scenarios PASS with zero console/page errors.

## Findings and remediation

| ID | Severity | Workspace | Finding | Remediation | Live verification |
|---|---|---|---|---|---|
| FA-UI-001 | P0 | Service | Start/Stop/Restart were initially enabled before service state returned; fail-open window. | Initial HTML disabled + JS pending-state authority; errors remain fail-closed. | PASS: all three disabled immediately on entry. |
| FA-UI-002 | P1 | Accounts | Readiness Probe could be offered without Browser Runtime readiness (observed Qwen BLOCKED/runtime-down mismatch). | Account action now derives Provider runtime group and disables readiness when runtime is not ready, with reason. | PASS: Qwen disabled; DeepSeek/runtime-ready accounts enabled. |
| FA-UI-003 | P1 | Models | Workspace could appear blank for seconds while four remote data sources loaded. | Explicit accessible loading states for summary, readiness evidence and capability matrix. | PASS: loading visible at 100ms/1s; real data replaces it around 3s. |
| FA-UI-004 | P1 | Models | Text promised complete Provider capability matrix but UI filtered out disabled Providers. | Matrix now includes all registered Providers and marks disabled columns `off`. | PASS: 6 Provider columns rendered from 6 registered Providers. |
| FA-UI-005 | P1 | Overview | At 768px chart canvas exceeded its parent and caused panel overflow; long readiness states also stressed cards. | Responsive chart containment and wrap rules for Provider status states/meta. | PASS: 768px body/panel overflow false; chart entirely inside parent. |
| FA-UI-006 | P2 | Config | Raw YAML advanced controls lacked sufficiently explicit audit-oriented labels/tooltips. | Added `aria-label`/`title` to raw YAML save/reload/editor controls. | PASS in live DOM. |
| FA-UI-007 | P1 | Accounts | Session validation age and Readiness evidence age were visually conflated under one generic Evidence field. | Separate `Session Evidence` and `Readiness Evidence` timestamps are rendered. | PASS: DeepSeek Account card exposes both provenance timestamps independently. |
| FA-UI-008 | P1 | Cross-UI | Persian labels introduced during audit remediation were corrupted to literal question marks by a Windows code-page write path. | Rewrote all introduced Persian UI strings with encoding-safe generation and added source/DOM corruption checks. | PASS: source contains no triple-question corruption; live DOM `visible_triple_question_runs=0`. |

## False positives explicitly rejected

- Broad clipping detector counted normal content below the viewport; vertical scrolling alone is not clipping.
- First accessibility scan treated nested `<label>` controls as unlabeled; refined scan reports zero missing accessible names.
- Initial 768px Logs overflow was not reproducible with offender-level geometry and is not a finding.
- Fixed-sleep Models samples can race the async fetch. Robust DOM-event verification waits for the table and confirms loading text first, then all six Provider columns with no JS/page errors.

## Validation gates

- Visible Dev version: `2.1.1-dev.full-audit-remediation.20260925-1730`.
- Full deterministic suite: `612/612 PASS`.
- Focused version/certification tests: `4/4 PASS`.
- Secret scan: `89 files / 0 findings`.
- OSV dependency audit: `35 packages / 0 findings`.
- `node --check control_panel_ui/panel.js`: PASS.
- Python compileall: PASS.
- `git diff --check`: PASS.
- Production 5000 and shared CDP 9330 were not modified by these UI remediations.

## Remaining audit scope

Audit remains **IN_PROGRESS**. Still required before closure:
- destructive/negative-path scenarios with rollback snapshots: API-key lifecycle, config save/invalid YAML, service actions, runtime repair, Account re-auth/logout, Provider enable/delete/model/default mutations;
- Provider Wizard end-to-end negative and recovery paths after release;
- stale/error/timeout injection and recovery semantics;
- final cross-workspace information architecture review for missing/redundant/misplaced controls;
- final production revalidation only after remediation is promoted through a controlled release;
- E3 clean W2/W3 resolution for `HWG-WORK-013`.

Raw visual baseline: `.runtime-prod/control-plane-full-audit-20260925T163504Z/`.
