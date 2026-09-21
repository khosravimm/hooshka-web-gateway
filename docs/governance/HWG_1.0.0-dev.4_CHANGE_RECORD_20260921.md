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
