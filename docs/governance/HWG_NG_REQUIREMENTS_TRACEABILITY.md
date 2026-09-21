# HWG Next Generation Requirements Traceability

- Baseline date: 2026-09-21
- Normative mission: `HWG-MISSION-NG-001` v1.0.0
- Technical playbook: `HWG-KT-WEBCHAT-001` v1.0.0
- Purpose: keep every Mission/Playbook requirement visible until implemented, evidenced, or formally changed.

## Status semantics

- `IMPLEMENTED`: code/config exists, but evidence level is stated separately.
- `PARTIAL`: some required behavior exists; Mission requirement is not yet fully satisfied.
- `OPEN`: requirement is not yet implemented as a complete production capability.
- `CONFLICT`: current implementation contradicts a normative requirement and requires migration or an approved governance change.
- Evidence remains E0/E1/E2/E3; status alone never implies certification.

## Authority rule

Mission/Architecture define **what must be true**. Code/config/tests define **what is currently true**. Scoped evidence defines **what has been proven**. A current implementation difference is a tracked gap, not an implicit waiver.

## Mission traceability baseline

| Requirement | Baseline status | Current evidence / gap |
|---|---|---|
| Standard HWG contract for consumers | PARTIAL | OpenAI-adjacent API exists; full versioned contract/conformance remains open. |
| Versioned Provider Profile schema | PARTIAL | `schemas/hwg-provider-profile-v1.schema.json` establishes schema v1; provider migration/passport population and certification remain open. |
| Multi-account per Provider | OPEN | Current runtime/config remains primarily one logical account/profile path per provider. |
| Research/Reuse before custom development | PARTIAL | Playbooks/research exist; must become enforced ADR/gate for every subsystem change. |
| Discovery Engine / research-baseline-exploration-drift-certification pipeline | PARTIAL | Governed orchestrator, Control Plane, live read-only Exploration, Behavior Lab, Update Candidate review and approval-gated AI assistance exist; multi-provider behavior validation and interactive E2 certification remain open. |
| Functional Readiness | PARTIAL | CDP/runtime checks exist; full Page/Auth/Model/Feature/functional-probe state machine is not complete. |
| Version/change history for major artifacts | PARTIAL | dev.4 established synchronized VERSION/MANIFEST/UI and drift gates; dev.5 records Discovery-assisted exploration policies and behavior/AI routing work, while persistent per-profile/account history remains open. |
| Evidence/traceability | PARTIAL | E0-E3 model, Work Register anti-forgetting gate, Discovery run history and DONE-with-evidence validation exist; full requirement-to-release-evidence closure remains open. |
| Professional Management UI + embedded chat | PARTIAL | Control plane and chat exist; IA/readiness/account/profile workflows are under active redesign. |
| SDK + machine-readable contract | PARTIAL | Existing SDK/API artifacts exist; NG Python+TS contract/conformance coverage remains incomplete. |
| Security/Privacy/Audit/Rollback release gates | PARTIAL | Controls/tests exist; full RC gate and rollback proof remain open. |
## Browser / Profile / Account traceability

| Requirement | Baseline status | Current evidence / gap |
|---|---|---|
| Unified visible browser UX without isolation loss | PARTIAL | Visible runtime exists; one-window/multi-account isolation design study is not complete. |
| No focus stealing in background operations | PARTIAL | Focus-guard concepts exist; full automated/no-focus certification gate remains open. |
| Per-account session/storage isolation | CONFLICT | Current `shared-profile` is assigned to ChatGPT, Z.ai and DeepSeek. Mission/Playbook require account/profile isolation; migrate away or approve a versioned architecture change. |
| Provider Profile separate from Account Instance | PARTIAL | Separate Provider Profile v1 and Account Instance v1 schemas plus a read-only legacy projection now exist; persistent runtime migration to real instances remains open. |
| Profile as runtime security boundary | PARTIAL | Explicit profile paths/ownership exist, but shared profile violates the target boundary. |
| Login/Logout/Re-auth/Session Validation UI | PARTIAL | Some provider session endpoints exist; complete account-centric workflow is open. |

## Runtime / readiness lifecycle

Target lifecycle from the Mission and Playbook:

`RUNTIME_ABSENT -> RUNTIME_STARTING -> CDP_REACHABLE -> PAGE_LOADING -> PAGE_INTERACTIVE -> AUTH_REQUIRED|AUTHENTICATED -> MODEL_STATE_VALIDATING -> FEATURE_STATE_VALIDATING -> FUNCTIONAL_PROBE_RUNNING -> READY | DEGRADED | BLOCKED | FAILED`

Current control-plane work must converge on this model. `CDP ready` alone is not `Provider READY`.

## Provider integration invariants inherited from the playbook

- Exact fail-closed provider/model routing; no silent cross-provider fallback.
- Provider Profile + Account Instance + Transport + Evidence is the durable integration unit.
- Browser/profile ownership must be explicit and cleanup must target owned profiles only.
- Retry must respect `not_sent -> maybe_sent -> committed -> terminal` commitment state.
- Stream provenance must be truthful: native, captured, reconstructed/buffered as applicable.
- Provider-native controls and semantics remain provider-specific behind normalized meaning/lifecycle.
- Live Web Chat tests are bounded/rate-aware; CAPTCHA/WAF/suspension bypass is prohibited.
- Capability claims are evidence-scoped; a historical success does not become a permanent capability claim.
- Every defect/fix must return knowledge to Profile/Adapter/Evidence/regression docs.

## Release-gate baseline

The following Mission gates remain mandatory for RC: static/config/schema, unit, regression, API conformance, SDK contracts, runtime/profile isolation, no-focus-stealing, multi-account isolation, startup/readiness, UI functional, security/secret leakage, failure/retry/commitment, rollback, targeted provider E2, and interactive user certification.

As of this baseline, existing E1/E2 evidence may satisfy portions of individual gates, but **no statement in this document marks the complete NG Release Candidate as passed**.

## Immediate architecture debts exposed by governance alignment

1. Replace `shared-profile` usage with an account/profile model consistent with isolation requirements.
2. Replace binary CDP readiness in the UI with the full readiness state machine and functional probe.
3. Migrate provider config into the new Provider Profile v1 and Account Instance v1 contracts; preserve explicit version/history for each instance.
4. Make Profile -> Account -> Runtime -> Provider relationships explicit in the control plane.
5. Add requirement IDs/evidence links to new tests and operational changes.
6. Keep this matrix updated in the same change set whenever a Mission requirement, architecture contract or evidence status changes.

## Anti-forgetting execution register

The machine-readable execution register is `docs/governance/HWG_REMAINING_WORK_REGISTER.json` (`HWG-WORK-REGISTER-001`). Traceability records requirement compliance; the Work Register records the executable remediation plan, dependencies, target version, required evidence and exit criteria. Silent removal of unfinished work is prohibited. The Control Plane exposes the register through `/panel/api/governance/work-register` and a dedicated `کارهای باقی‌مانده` workspace.

## Discovery AI self-use invariant

When the provider under investigation is also considered as the AI helper, explicit user approval alone is insufficient. The target provider must have a current deterministic transport qualification proving send-path identification, receive-path identification, completion detection, and a successful controlled round-trip. Qualification is bound to the current transport fingerprint and fails closed on missing, stale, incomplete, or AI-derived evidence. Until the live human-confirmed round-trip is executed, target-provider self-use remains blocked.
