# HWG Control Plane Dynamic Visual Audit — E2

Date: 2026-09-24
Work item: `HWG-WORK-025`
Scope: all 15 Control Plane workspaces on Dev runtime `127.0.0.1:5080`.

## Method

The prior fast audit was rejected because the Control Plane is dynamic. The replacement audit uses the HWG User-View/Visual Observer and waits for a dynamic readiness gate before judging a workspace.

A workspace is not considered settled until:
- fetch/XHR activity is quiet,
- visible loading indicators are gone,
- rendered text/control counts remain stable,
- a minimum dwell time has elapsed,
- a second confirmation pass remains stable.

For each workspace the audit captured entered, settled, pre-interaction, scroll-sweep and post-interaction screenshots. Safe selects/buttons were exercised and re-gated after each interaction. Long-running Probe/Test actions use extended observation windows.
## Findings and remediation

The slower audit exposed issues hidden by the earlier pass:
- `profiles`: horizontal overflow and 8 clipped elements.
- `accounts`: horizontal overflow and 6 clipped elements.
- `providers`: horizontal overflow and 14 clipped elements.
- `service`: data was present after settling; the earlier `-` values were premature capture, not backend absence.
- `chat`: Readiness Probe can outlive a short generic timeout; STALE gating needed clearer visible semantics.
- `telemetry`: HTTP request breakdown and Provider dispatch counts were visually ambiguous.

Remediation applied:
- relationship-card grids now use wider responsive minimums and safe wrapping,
- Profile/Account/Provider cards no longer force dense multi-column internals,
- Embedded Chat distinguishes capability availability from checkbox state,
- STALE Chat shows `ارسال (نیازمند READY)` as visibly disabled,
- Telemetry labels now distinguish HTTP panel/API counts from actual Provider dispatches.
## Revalidation

Targeted live re-audit after remediation:
- `profiles`: `horizontal_overflow=false`, `clipped=0`.
- `accounts`: `horizontal_overflow=false`, `clipped=0`.
- `providers`: `horizontal_overflow=false`, `clipped=0`.
- Chat STALE state: `chat-send.disabled=true` and label `ارسال (نیازمند READY)`.
- Chat capability text: `قابلیت تفکر/جستجو: دارد|ندارد`.
- Telemetry: scope labels are explicit and no longer imply that HTTP counters equal Provider sends.

Durable machine-readable summary:
`docs/evidence/HWG_CONTROL_PLANE_DYNAMIC_VISUAL_AUDIT_E2_20260924.json`

Raw visual evidence remains under `.runtime-dev/control-plane-visual-audit-20260923T223818Z/` and targeted re-audit folders.

## Remaining human-facing gaps

This audit does not close Human Acceptance. Remaining UX work includes Persian-first simplification of technical relationship text, search/filter ergonomics for large Evidence collections, and additional user-journey refinement where terminology is still engineering-centric.
